"""Textes affiches par les menus (fichier de messages MCD "CORE", v1.04).

Verifie en jeu (2026-11-23) : le magasin affiche CORE_ITEM_NAME_<id> / CORE_ITEM_HELP_<id> depuis un MCD :
- en-tete : 10 u32 (messages, symboles, glyphes, polices, evenements : offset + nombre) ;
- evenement (0x28 octets) : hachage, indice du message, nom de cle ;
- message (16) : offset des paragraphes, nombre, ... ; paragraphe (20) : offset des lignes, nombre, ... ;
- ligne (24) : offset des lettres, 0, nombre, nombre, largeur (float), 0 ;
- lettres : paires (indice de symbole, crenage) ; 0x8001 = espace (+ crenage), 0x8000 = fin ;
- symbole (8) : police, caractere UTF-16, glyphe.
Les nouvelles lettres sont ecrites dans une zone allouee apres le fichier (offsets u32 relatifs au debut
du fichier) : le fichier d'origine n'est jamais modifie, restore() remet les lignes d'origine.
"""
from __future__ import annotations

import struct
import unicodedata
from typing import Optional

SPACE_KERNING = 36
LINE_MAX = 256  # lettres u16 par ligne (zone dediee)
EXTRA_KEYS = 64
POOL_SIZE = 0x100000


def key_hash(key: str) -> int:
    """Hachage des cles (verifie : CORE_ITEM_NAME_931 -> 0x11F3487D) : CRC32 de la cle en minuscules, 31 bits."""
    import zlib
    return zlib.crc32(key.lower().encode()) & 0x7FFFFFFF
END, SPACE = 0x8000, 0x8001


def encode_pairs(text: str, symbols, font: int) -> list[int]:
    """Texte -> lettres (paires) avec les symboles de la police `font`. Accents retires si absents,
    caractere inconnu -> '?'."""
    idx: dict[str, int] = {}
    for i, (f, ch, _g) in enumerate(symbols):
        if f == font:
            idx.setdefault(chr(ch), i)
    out: list[int] = []
    for c in text:
        if c == " ":
            out += [SPACE, SPACE_KERNING]
            continue
        if c not in idx:
            base = unicodedata.normalize("NFKD", c)[0]
            for alt in (base, base.lower(), base.upper(), "?"):
                if alt in idx:
                    c = alt
                    break
        if c in idx:
            out += [idx[c], 0]
    return out + [END]


SPARE_SYMBOLS = "[]+ÀÉêâàè"
WANTED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def glyph_plan(symbols, donor_symbols, font: int, wanted: str = WANTED, spare: str = SPARE_SYMBOLS):
    """Lettres absentes de `font` : (indice de symbole sacrifie, lettre, glyphe du donneur).
    Verifie en jeu : un glyphe designe sa texture par hachage, on peut donc copier celui d'un autre fichier."""
    have = {chr(c) for f, c, _ in symbols if f == font}
    donor = {}
    for f, c, g in donor_symbols:
        if f == font:
            donor.setdefault(chr(c), g)
    spares = [i for i, (f, c, _) in enumerate(symbols) if f == font and chr(c) in spare]
    out = []
    for ch in wanted:
        if ch in have or ch not in donor or not spares:
            continue
        out.append((spares.pop(0), ch, donor[ch]))
    return out


def wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur); cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines[:max_lines]


# --- acces memoire -----------------------------------------------------------------------------

def _find(mem, needle: bytes) -> list[int]:
    from .notify import _scan
    return _scan(mem, [needle])[needle]


class CoreText:
    """Fichier MCD des menus en memoire ; set_text() remplace le texte d'une cle (restaurable)."""

    def __init__(self, mem, probe_key: str = "CORE_ITEM_NAME_931"):
        self.mem = mem
        self.base: Optional[int] = None
        self._orig: dict[int, bytes] = {}
        self._pool: Optional[int] = None
        self._pool_used = 0
        self._bufs: dict[int, int] = {}
        self._relocated = False
        self._hidden: dict[int, int] = {}
        self._added = 0
        self._hdr_orig: Optional[bytes] = None
        for k in _find(mem, probe_key.encode() + b"\0"):
            b = self._header_for(k - 8)
            if b:
                self.base = b
                break
        if self.base is None:
            return
        h = struct.unpack("<10I", mem.read(self.base, 40))
        self.mo, self.mc, so, sc, _, _, _, _, self.eo, self.ec = h
        raw = mem.read(self.base + so, sc * 8)
        self.symbols = [struct.unpack_from("<HHI", raw, i * 8) for i in range(sc)]
        ev = mem.read(self.base + self.eo, self.ec * 0x28)
        self.keys = {}
        for i in range(self.ec):
            _h, msg = struct.unpack_from("<II", ev, i * 0x28)
            name = ev[i * 0x28 + 8:i * 0x28 + 0x28].split(b"\0")[0].decode("ascii", "replace")
            self.keys[name] = msg

    def _header_for(self, entry: int) -> Optional[int]:
        mem = self.mem
        p = entry
        for _ in range(5000):  # debut de la table des evenements
            k = mem.read(p - 0x28 + 8, 4)
            if not (65 <= k[0] <= 90 and all(32 < c < 127 for c in k)):
                break
            p -= 0x28
        span = 0x200000
        try:
            d = mem.read(p - span, span)
        except OSError:
            return None
        for off in range(len(d) - 0x28, -1, -4):
            so, sc, go, gc, fo, fc, o, _c = struct.unpack_from("<8I", d, off + 8)
            if o == span - off:
                return p - span + off          # table des cles d'origine
            # table deja recopiee par une session precedente : champs fixes (symboles, glyphes, polices)
            if 0 < sc == gc and so < go < fo and abs(go - so - sc * 8) < 16 and fc < 64 \
                    and 0 <= span - off - fo < 0x1000:
                return p - span + off
        return None

    @property
    def ok(self) -> bool:
        return self.base is not None

    def _lines(self, key: str):
        msg = self.keys.get(key)
        if msg is None:
            return []
        po, pc, _, _ = struct.unpack("<4I", self.mem.read(self.base + self.mo + msg * 16, 16))
        out = []
        for j in range(pc):
            lo, lc, *_ = struct.unpack("<5I", self.mem.read(self.base + po + j * 20, 20))
            for n in range(lc):
                out.append(self.base + lo + n * 24)
        return out

    def _alloc(self, size: int) -> Optional[int]:
        """Zone apres le fichier (offset u32 positif)."""
        import ctypes
        from ctypes import wintypes
        if self._pool is None:
            k = self.mem._k
            k.OpenProcess.restype = wintypes.HANDLE
            h = k.OpenProcess(0x1F0FFF, False, self.mem.pid)
            k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD,
                                         wintypes.DWORD]
            k.VirtualAllocEx.restype = ctypes.c_void_p
            from .spawner import _MBI
            k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
            k.VirtualQueryEx.restype = ctypes.c_size_t
            addr = self.base
            while addr < self.base + 0xF0000000 and not self._pool:
                mbi = _MBI()
                if not k.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                    break
                start = ((mbi.BaseAddress or 0) + 0xFFFF) & ~0xFFFF
                end = (mbi.BaseAddress or 0) + mbi.RegionSize
                if mbi.State == 0x10000 and end - start >= POOL_SIZE:  # MEM_FREE
                    self._pool = k.VirtualAllocEx(h, ctypes.c_void_p(start), POOL_SIZE, 0x3000, 0x04)
                addr = end
            k.CloseHandle(h)
        if not self._pool or self._pool_used + size > POOL_SIZE:
            return None
        a = self._pool + self._pool_used
        self._pool_used += (size + 15) & ~15
        return a

    def set_text(self, key: str, text: str, width: int = 0) -> bool:
        """Remplace le texte d'une cle. width>0 : coupe en lignes (au plus le nombre de lignes d'origine)."""
        lines = self._lines(key)
        if not lines:
            return False
        parts = wrap(text, width, len(lines)) if width else [text]
        font = None
        for i, la in enumerate(lines):
            raw = self.mem.read(la, 24)
            if la not in self._orig:
                self._orig[la] = raw
            to = struct.unpack_from("<I", self._orig[la])[0]
            if font is None:
                first = struct.unpack("<H", self.mem.read(self.base + to, 2))[0]
                font = self.symbols[first][0] if first < len(self.symbols) else self.symbols[0][0]
            letters = encode_pairs(parts[i] if i < len(parts) else "", self.symbols, font)[:LINE_MAX - 1]
            if letters[-1] != END:
                letters.append(END)
            dest = self._bufs.get(la)
            if dest is None:
                dest = self._alloc(LINE_MAX * 2)
                if dest is None:
                    return False
                self._bufs[la] = dest
            self.mem.write(dest, struct.pack(f"<{len(letters)}H", *letters))
            line = bytearray(self._orig[la])
            struct.pack_into("<I", line, 0, dest - self.base)
            struct.pack_into("<II", line, 8, len(letters), len(letters))
            self.mem.write(la, bytes(line))
        return True

    def add_key(self, key: str, template_key: str) -> bool:
        """Cree une cle absente du fichier (ex. objet coupe du jeu) en copiant la mise en page d'un message
        modele. La table des messages et celle des cles sont recopiees (une fois) dans la zone allouee,
        agrandies, et l'en-tete pointe dessus."""
        if key in self.keys:
            return True
        tmsg = self.keys.get(template_key)
        if tmsg is None:
            return False
        mem, B = self.mem, self.base
        if not self._relocated:
            msgs = mem.read(B + self.mo, self.mc * 16)
            evs = mem.read(B + self.eo, self.ec * 0x28)
            ma = self._alloc((self.mc + EXTRA_KEYS) * 16)
            ea = self._alloc((self.ec + EXTRA_KEYS) * 0x28)
            if ma is None or ea is None:
                return False
            mem.write(ma, msgs); mem.write(ea, evs)
            self._hdr_orig = mem.read(B, 40)
            self.mo, self.eo = ma - B, ea - B
            self._seq = max(struct.unpack_from("<I", msgs, i * 16 + 8)[0] for i in range(self.mc)) + 1
            self._relocated = True
        if self._added >= EXTRA_KEYS:
            return False
        po, pc, _seq, _h = struct.unpack("<4I", mem.read(B + self.mo + tmsg * 16, 16))
        new_pars = self._alloc(pc * 20)
        for j in range(pc):
            par = bytearray(mem.read(B + po + j * 20, 20))
            lo, lc = struct.unpack_from("<II", par, 0)
            new_lines = self._alloc(lc * 24)
            mem.write(new_lines, mem.read(B + lo, lc * 24))
            struct.pack_into("<I", par, 0, new_lines - B)
            mem.write(new_pars + j * 20, bytes(par))
        idx = self.mc
        h = key_hash(key)
        mem.write(B + self.mo + idx * 16, struct.pack("<4I", new_pars - B, pc, self._seq, h))
        entry = struct.pack("<II", h, idx) + key.encode()[:0x1F].ljust(0x20, bytes(1))
        mem.write(B + self.eo + self.ec * 0x28, entry)
        self._seq += 1
        self.mc += 1; self.ec += 1; self._added += 1
        mem.write(B, struct.pack("<II", self.mo, self.mc))
        mem.write(B + 0x20, struct.pack("<II", self.eo, self.ec))
        self.keys[key] = idx
        return True

    def borrow_glyphs(self, donor: "CoreText", font: int = 36) -> int:
        """Toutes les lettres de `font` utilisent les glyphes du fichier donneur (meme caractere) : le jeu
        dessine une ligne avec une seule texture, on ne doit donc pas melanger les deux fichiers.
        Les lettres absentes prennent la place de symboles rares (glyph_plan)."""
        h = struct.unpack("<10I", self.mem.read(self.base, 40))
        hd = struct.unpack("<10I", self.mem.read(donor.base, 40))
        size = (h[6] - h[4]) // h[5] if h[5] else 40
        dsize = (hd[6] - hd[4]) // hd[5] if hd[5] else 40
        donor_g = {}
        for f, c, g in donor.symbols:
            if f == font:
                donor_g.setdefault(c, g)
        n = 0
        for i, ch, dg in glyph_plan(self.symbols, donor.symbols, font):
            g = self.symbols[i][2]
            self.mem.write(self.base + h[2] + i * 8, struct.pack("<HHI", font, ord(ch), g))
            self.symbols[i] = (font, ord(ch), g)
        for i, (f, c, g) in enumerate(self.symbols):
            if f == font and c in donor_g:
                self.mem.write(self.base + h[4] + g * size,
                               self.mem.read(donor.base + hd[4] + donor_g[c] * dsize, size))
                n += 1
        return n

    def hide_key(self, key: str) -> bool:
        """Rend une cle introuvable dans ce fichier (le jeu passe alors au fichier suivant)."""
        for i in range(self.ec):
            a = self.base + self.eo + i * 0x28
            if self.mem.read(a + 8, 0x20).split(bytes(1))[0] == key.encode():
                h = struct.unpack("<I", self.mem.read(a, 4))[0]
                if h == key_hash(key):
                    self._hidden[a] = h
                    self.mem.write(a, struct.pack("<I", h ^ 0x40000000))
                return True
        return False

    def restore(self) -> None:
        for a, h in self._hidden.items():
            self.mem.write(a, struct.pack("<I", h))
        for la, raw in self._orig.items():
            self.mem.write(la, raw)
        if self._hdr_orig is not None:
            self.mem.write(self.base, self._hdr_orig)


class MenuTexts:
    """Le jeu consulte plusieurs fichiers MCD (CORE + additionnel : ex. noms des teintures 880..).
    set_text() modifie la cle dans chaque fichier qui la contient."""

    def __init__(self, mem, probes=("CORE_ITEM_NAME_931", "CORE_ITEM_NAME_880")):
        self.files: list[CoreText] = []
        for p in probes:
            f = CoreText(mem, p)
            if f.ok and all(f.base != g.base for g in self.files):
                self.files.append(f)
        for f in self.files[1:]:
            f.borrow_glyphs(self.files[0])

    @property
    def ok(self) -> bool:
        return bool(self.files)

    def set_text(self, key: str, text: str, width: int = 0) -> bool:
        """Ecrit la cle dans chaque fichier qui la contient. Un fichier ne contient que les lettres de ses
        propres textes : lettre absente -> autre casse, sans accent, sinon '?'.
        (Verifie : le jeu garde en cache ses tables de cles, add_key/hide_key ne sont pas pris en compte.)"""
        done = False
        for f in self.files:
            if key in f.keys:
                done = f.set_text(key, text, width) or done
        return done

    def restore(self) -> None:
        for f in self.files:
            f.restore()
