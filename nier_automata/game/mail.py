"""Messagerie du jeu (Courrier des points d'acces) : mails Archipelago (checks a faire, indices).

Verifie en jeu (v1.04, 2026-11-23) :
- table des mails : objet global RVA 0xF5EE10 ; [+0x18] tableau trie d'entrees de 0xA4 octets, [+0x20] nombre,
  [+0x28] capacite (128). Entree : +0 numero, +4 destinataires (0x80000000 = 2B), +0xC identifiant d'expediteur
  (16 octets). On AJOUTE des mails (numeros 31..34 : textes "No Message", aucune entree d'origine) ;
- envoi : 0x80BCC0(objet, numero) -> boite de 2B = [objet+8] + 0x57C0 (128 x 16 octets :
  numero, drapeaux (0xC0000000 = lu, 0 = non lu), heure (minute << 16 | heure), -1) ;
- texte : table UTF-16 "PAUSE_MAIL_BODY_%03d" ; enregistrement (hachage, cle, decalage u32 depuis la base de
  la table, longueur en caracteres + 1, tampon de destination) ; le menu copie le texte dans le tampon ;
- titre : cle MCD "PAUSE_MAIL_%03d" (fichier recharge a chaque ouverture du terminal) ;
- expediteur : table de noms RVA 0xFC2E20, une tranche (0x30 octets) par langue, entrees triees
  (CRC32 minuscule 31 bits de l'identifiant, structure) ; nom affiche = UTF-8 pointe par [structure+0x28].
"""
from __future__ import annotations

from .spawner import near_addresses  # noqa: E402

import re
import struct
import time
from typing import Optional

MAIL_OBJ_RVA = 0xF5EE10
SEND_MAIL_RVA = 0x80BCC0
ENTRY = 0xA4
SENDER_OFFSET = 0xC
BOX_OFFSET = 0x57C0
BOX_SLOTS = 0x80
NAME_MAP_RVA = 0xFC2E20
NAME_SHARD = 0x30
NAME_SHARDS = 9
TEMPLATE_MAIL = 1            # mail de bienvenue (expediteur "Responsable serveur")
TEMPLATE_SENDER = "servermanager"
CHECKS_MAIL, HINTS_MAIL = 31, 32
TEXT_MGR_RVA = 0x176D7E8     # conteneurs DAT de texte charges (slots de 3 qwords)


# --- logique pure ----------------------------------------------------------------------------

def sender_id(name: str) -> str:
    sid = re.sub(r"[^A-Za-z0-9_]", "_", name)[:15]
    return sid or "Archipelago"


def insert_entry(entries: list[bytes], template: bytes, no: int, sender: str) -> list[bytes]:
    nos = [struct.unpack_from("<i", e, 0)[0] for e in entries]
    if no in nos:
        return entries
    new = bytearray(template)
    struct.pack_into("<i", new, 0, no)
    new[SENDER_OFFSET:SENDER_OFFSET + 16] = sender_id(sender).encode().ljust(16, b"\0")
    out = list(entries) + [bytes(new)]
    return sorted(out, key=lambda e: struct.unpack_from("<i", e, 0)[0])


def insert_name(entries: list[tuple[int, int]], h: int, ptr: int) -> list[tuple[int, int]]:
    if any(e[0] & 0xFFFFFFFF == h for e in entries):
        return entries
    return sorted(list(entries) + [(h, ptr)], key=lambda e: e[0] & 0xFFFFFFFF)


def unread_entry(raw: bytes, hour: int, minute: int) -> bytes:
    no, _flags, _t, x = struct.unpack("<iIII", raw)
    return struct.pack("<iIII", no, 0, (minute << 16) | hour, x)


KIND_ORDER = ["Chest", "AP Item", "Story", "Access Point", "Quest", "Ending", "Shop", "Level", "Weapon Found", "Pod Program Found", "Item"]


def check_kinds(names) -> list[tuple[str, int]]:
    """Nombre de checks par type, dans un ordre fixe (le jeu n'affiche nulle part ce qu'il reste)."""
    out = {}
    for n in names:
        kind = next((k for k in KIND_ORDER if n.startswith(k)), "Other")
        out[kind] = out.get(kind, 0) + 1
    return [(k, out[k]) for k in KIND_ORDER + ["Other"] if k in out]


def checks_body(remaining: list[str], total: int, lang: str = "fr") -> str:
    from .i18n import t
    lines = [t(lang, "checks_head", n=len(remaining), total=total)]
    counts = check_kinds(remaining)
    if counts:
        lines.append(" | ".join(f"{k} {n}" for k, n in counts))
    lines.append("")
    lines += [f"- {n}" for n in sorted(remaining)]
    return "\n".join(lines)


def hints_body(hints: list[tuple[str, str, str]], lang: str = "fr") -> str:
    """hints : [(objet, pour qui, emplacement)] dans l'ordre d'arrivee ; le plus recent en premier."""
    from .i18n import t
    lines = [t(lang, "hints_head"), ""]
    for item, who, where in reversed(hints):
        lines.append(t(lang, "hint_line", item=item, who=who, where=where))
    return "\n".join(lines)


# --- acces memoire -----------------------------------------------------------------------------

def _alloc_after(mem, base: int, size: int = 0x10000) -> Optional[int]:
    """Zone libre APRES `base` (a moins de 4 Go) : les decalages de la table de textes sont des u32."""
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    addr, out = base, None
    while addr < base + 0xF0000000 and not out:
        mbi = _MBI()
        if not k.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        b = mbi.BaseAddress or 0
        st = (b + 0xFFFF) & ~0xFFFF
        if mbi.State == 0x10000 and b + mbi.RegionSize - st >= size:
            out = k.VirtualAllocEx(h, ctypes.c_void_p(st), size, 0x3000, 0x04)
        addr = b + mbi.RegionSize
    k.CloseHandle(h)
    return out


class Mailer:
    """Mails Archipelago dans un processus du jeu."""

    def __init__(self, mem):
        self.mem = mem
        self.obj = mem.base + MAIL_OBJ_RVA
        remove_title_hooks(mem)
        self._records: dict[int, tuple] = {}     # no -> (enregistrement, base de table, zone)
        self._names: set[str] = set()
        self._titles: dict[int, str] = {}
        self._title_file = None
        self._title_retry = 0.0
        self._title_lines: dict[int, bytes] = {}

    # table des mails
    def ensure_mail(self, no: int, sender: str) -> None:
        mem = self.mem
        arr, cnt, cap = struct.unpack("<QQQ", mem.read(self.obj + 0x18, 24))
        ents = [mem.read(arr + i * ENTRY, ENTRY) for i in range(cnt)]
        template = next((e for e in ents if struct.unpack_from("<i", e, 0)[0] == TEMPLATE_MAIL), None)
        if template is None:
            return
        new = insert_entry(ents, template, no, sender)
        if len(new) != len(ents) and len(new) <= cap:
            mem.write(arr, b"".join(new))
            mem.write(self.obj + 0x20, struct.pack("<Q", len(new)))
        self.set_sender(no, sender)

    def set_sender(self, no: int, name: str) -> None:
        mem = self.mem
        sid = sender_id(name)
        self._ensure_name(sid, name)
        arr, cnt = struct.unpack("<QQ", mem.read(self.obj + 0x18, 16))
        for i in range(cnt):
            if struct.unpack("<i", mem.read(arr + i * ENTRY, 4))[0] == no:
                mem.write(arr + i * ENTRY + SENDER_OFFSET, sid.encode().ljust(16, b"\0"))

    def _ensure_name(self, sid: str, display: str) -> None:
        """Nom affiche pour l'identifiant `sid` dans toutes les langues."""
        from .mcd_text import key_hash
        from .spawner import alloc
        if sid in self._names:
            return
        mem = self.mem
        h = key_hash(sid)
        th = key_hash(TEMPLATE_SENDER)
        text = display[:30].encode("utf-8") + bytes(1)   # coupe sur des caracteres (UTF-8 valide)
        for s in range(NAME_SHARDS):
            hdr = mem.base + NAME_MAP_RVA + s * NAME_SHARD
            _vt, arr, cnt, cap = struct.unpack("<QQQQ", mem.read(hdr, 32))
            if not (0 < cnt <= cap <= 4096):
                continue
            raw = mem.read(arr, cnt * 16)
            ents = [struct.unpack_from("<QQ", raw, j * 16) for j in range(cnt)]
            tpl = next((p for k, p in ents if k & 0xFFFFFFFF == th), None)
            if tpl is None or cnt >= cap:
                continue
            st = bytearray(mem.read(tpl, 0x60))
            buf = alloc(mem, bytes(0x80) + text)
            struct.pack_into("<Q", st, 0x28, buf + 0x80)
            struct.pack_into("<Q", st, 0x30, 1000)   # compteur de references : jamais libere
            mem.write(buf, bytes(st))
            new = insert_name(ents, h, buf)
            if len(new) != len(ents):
                mem.write(arr, b"".join(struct.pack("<QQ", k, p) for k, p in new))
                mem.write(hdr + 0x10, struct.pack("<Q", len(new)))
        self._names.add(sid)

    # boite de 2B
    def _box(self) -> int:
        save = struct.unpack("<Q", self.mem.read(self.obj + 8, 8))[0]
        return save + BOX_OFFSET

    def in_box(self, no: int) -> Optional[int]:
        raw = self.mem.read(self._box(), BOX_SLOTS * 16)
        for i in range(BOX_SLOTS):
            if struct.unpack_from("<i", raw, i * 16)[0] == no:
                return self._box() + i * 16
        return None

    def send(self, no: int) -> None:
        from .spawner import remote_call
        if self.in_box(no) is None:
            remote_call(self.mem, self.mem.base + SEND_MAIL_RVA, self.obj, no)

    def mark_unread(self, no: int) -> None:
        a = self.in_box(no)
        if a is not None:
            t = time.localtime()
            self.mem.write(a, unread_entry(self.mem.read(a, 16), t.tm_hour, t.tm_min))

    # texte
    def _text_record(self, no: int):
        """(adresse de la cle UTF-16, enregistrement) du texte PAUSE_MAIL_BODY_<no>."""
        from .notify import _scan
        key = f"PAUSE_MAIL_BODY_{no:03d}".encode("utf-16-le") + bytes(2)
        for a in _scan(self.mem, [key])[key]:
            for r in _scan(self.mem, [struct.pack("<Q", a)])[struct.pack("<Q", a)]:
                return a, r - 8, len(key)
        return None

    def set_body(self, no: int, text: str) -> bool:
        mem = self.mem
        if no not in self._records:
            ref = self._text_record(TEMPLATE_MAIL)      # jamais modifie : donne la base de la table
            own = self._text_record(no)
            if not ref or not own:
                return False
            ka, rec1, klen = ref
            base = ka + klen + 4 - struct.unpack("<I", mem.read(rec1 + 0x10, 4))[0]
            pool = _alloc_after(mem, base)
            if not pool:
                return False
            self._records[no] = (own[1], base, pool)
        rec, base, pool = self._records[no]
        if struct.unpack("<Q", self.mem.read(rec + 8, 8))[0] == 0:
            del self._records[no]          # enregistrement libere : on le recherchera
            return False
        text = text[:0x3F00]
        mem.write(pool, text.encode("utf-16-le") + bytes(2))
        mem.write(rec + 0x20, struct.pack("<Q", pool + 0x8000))   # tampon de destination (32 Ko)
        mem.write(rec + 0x18, struct.pack("<Q", len(text) + 1))
        mem.write(rec + 0x10, struct.pack("<I", pool - base))
        return True

    # titre : le fichier des titres (MCD) est recharge SUR PLACE a chaque ouverture du terminal, ce qui efface
    # nos lignes. Verifie : il reste a la meme adresse. On le localise une fois (lent, en arriere-plan :
    # locate_titles), puis check_titles() (tres leger : 4 octets par titre) est appele toutes les 15 ms.
    def set_title(self, no: int, title: str) -> None:
        if self._titles.get(no) != title:
            self._titles[no] = title
            self._title_lines.pop(no, None)

    def locate_titles(self) -> bool:
        from .mcd_text import MenuTexts
        if self._title_file is not None or not self._titles:
            return self._title_file is not None
        if time.monotonic() < self._title_retry:
            return False
        self._title_retry = time.monotonic() + 10.0
        texts = MenuTexts(self.mem, keys=tuple(f"PAUSE_MAIL_{no:03d}" for no in self._titles))
        f = next((x for x in texts.files if f"PAUSE_MAIL_{min(self._titles):03d}" in x.keys), None)
        if f is None:
            return False
        self._title_file = (f, self.mem.read(f.base, 40))
        self._title_lines = {}
        return True

    def check_titles(self) -> None:
        if self._title_file is None:
            return
        f, head = self._title_file
        mem = self.mem
        try:
            if mem.read(f.base, 40) != head:
                return          # fichier pas (encore) charge : on reessaie au prochain passage
            for no, title in list(self._titles.items()):
                key = f"PAUSE_MAIL_{no:03d}"
                lines = f._lines(key)
                if not lines:
                    continue
                if self._title_lines.get(no) != mem.read(lines[0], 4):
                    f.set_text(key, title, font_from="PAUSE_MAIL_001")
                    self._title_lines[no] = mem.read(lines[0], 4)
        except OSError:
            pass

    def poll_titles(self) -> None:
        self.locate_titles()
        self.check_titles()


# --- titres : deviation du code (le fichier des titres est recharge a chaque ouverture du terminal) ----
# Le menu calcule le hachage de la cle "PAUSE_MAIL_%03d" puis cherche le texte par ce hachage. Pour nos
# mails, on remplace le hachage par celui d'une cle du fichier CORE (jamais recharge, toutes les lettres).
VIEW_SITE_RVA = 0x8EC4B4          # mov ebp,eax ; mov rbx,[r15+0x230]   (numero du mail : r14d)
VIEW_SITE_ORIGINAL = bytes.fromhex("8be8498b9f30020000")
VIEW_RETURN_RVA = 0x8EC4BD
LIST_SITE_RVA = 0x8ED0BB          # mov ebp,eax ; mov edx,[r14]         (numero du mail : [r14])
LIST_SITE_ORIGINAL = bytes.fromhex("8be8418b16")
LIST_RETURN_RVA = 0x8ED0C0
TITLE_KEYS = {CHECKS_MAIL: "CORE_ITEM_NAME_955", HINTS_MAIL: "CORE_ITEM_NAME_956"}  # skins de Pod inutilises


def _swap_hash(reg_cmp: bytes, mapping: dict[int, int]) -> bytearray:
    """Pour chaque (numero, hachage) : cmp <reg>,numero ; jne suivant ; mov eax,hachage."""
    c = bytearray()
    for no, h in mapping.items():
        c += reg_cmp + struct.pack("<B", no)          # cmp reg, imm8
        c += bytes([0x75, 0x05])                      # jne +5
        c += bytes([0xB8]) + struct.pack("<I", h)     # mov eax, h
    return c


def title_cave_view(cave: int, base: int, mapping: dict[int, int]) -> bytes:
    c = _swap_hash(bytes([0x41, 0x83, 0xFE]), mapping)        # cmp r14d, imm8
    c += VIEW_SITE_ORIGINAL                                    # mov ebp,eax ; mov rbx,[r15+0x230]
    c += bytes([0xE9]) + struct.pack("<i", base + VIEW_RETURN_RVA - (cave + len(c) + 5))
    return bytes(c)


def title_cave_list(cave: int, base: int, mapping: dict[int, int]) -> bytes:
    c = bytearray(bytes.fromhex("418b16"))                    # mov edx,[r14]
    c += _swap_hash(bytes([0x83, 0xFA]), mapping)              # cmp edx, imm8
    c += bytes.fromhex("8be8")                                 # mov ebp,eax
    c += bytes([0xE9]) + struct.pack("<i", base + LIST_RETURN_RVA - (cave + len(c) + 5))
    return bytes(c)


def remove_title_hooks(mem) -> None:
    """Retire les deviations de titre si une ancienne version les a installees (elles vident les titres)."""
    for rva, original in ((VIEW_SITE_RVA, VIEW_SITE_ORIGINAL), (LIST_SITE_RVA, LIST_SITE_ORIGINAL)):
        site = mem.base + rva
        if mem.read(site, 1)[0] == 0xE9:
            mem.write_code(site, original)


def install_title_hooks(mem) -> bool:
    """ABANDONNE (verifie en jeu) : le menu ne cherche ses titres que dans son propre fichier."""
    import ctypes
    from ctypes import wintypes
    from .mcd_text import key_hash
    mapping = {no: key_hash(k) for no, k in TITLE_KEYS.items()}
    sites = [(VIEW_SITE_RVA, VIEW_SITE_ORIGINAL, title_cave_view),
             (LIST_SITE_RVA, LIST_SITE_ORIGINAL, title_cave_list)]
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    ok = True
    for rva, original, make in sites:
        site = mem.base + rva
        cur = mem.read(site, len(original))
        if cur[0] == 0xE9:
            continue
        if cur != original:
            ok = False
            continue
        h = k.OpenProcess(0x1F0FFF, False, mem.pid)
        cave = None
        for near in near_addresses(mem.base):
            cave = k.VirtualAllocEx(h, ctypes.c_void_p(near), 0x1000, 0x3000, 0x40)
            if cave:
                break
        k.CloseHandle(h)
        if not cave:
            ok = False
            continue
        mem.write(cave, make(cave, mem.base, mapping))
        jmp = bytes([0xE9]) + struct.pack("<i", cave - (site + 5))
        mem.write_code(site, jmp + bytes([0x90]) * (len(original) - 5))
    return ok
