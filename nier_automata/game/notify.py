"""Notifications dans le jeu : "De Niicotine : Grappin", "Pour Fifi : Grappin".

Verifie en jeu (v1.04) :
- le message de ramassage est le modele de texte HUD_LOG_TXT_01 = "Objet récupéré : <ITEM NAME>"
  (28 caracteres, 2 copies en memoire) ;
- <ITEM NAME> est le nom de l'objet donne ; on utilise l'objet porteur 959 ("Tête d'amazarashi",
  17 caracteres max) dont on reecrit le nom ;
- on reecrit le modele (meme longueur max), on donne le porteur avec la fonction du jeu 0x8006F0
  (message affiche), on retire le porteur de l'inventaire et on restaure le modele.
"""
from __future__ import annotations

import struct
from typing import Optional

CARRIER_ITEM = 959
CARRIER_KEY = "ITEM_NAME_959"
MAX_LEN = 17
TEMPLATE = "Objet récupéré : <ITEM NAME>"
TEMPLATE_LEN = len(TEMPLATE)
PLACEHOLDER = "<ITEM NAME>"
TEMPLATE_KEY = "HUD_LOG_TXT_01"
GIVE_ITEM_RVA = 0x8006F0


def encode_fixed(text: str, units: int) -> bytes:
    """UTF-16LE sur exactement `units` unites (octets = 2*units), jamais plus : coupe sur une limite
    d'unite sans separer une paire de substitution (emoji), retire les caracteres de controle."""
    clean = "".join(ch for ch in text if ch.isprintable())
    raw = clean.encode("utf-16-le", "surrogatepass")[:units * 2]
    if len(raw) >= 2 and 0xD800 <= int.from_bytes(raw[-2:], "little") <= 0xDBFF:
        raw = raw[:-2]  # moitie haute d'une paire coupee
    return raw.ljust(units * 2, bytes(1))


_SEND_WORDS, _RECV_WORDS = ("For", "Pour"), ("From", "De")


def template_for(prefix: str, length: int = TEMPLATE_LEN) -> str:
    """Modele "<prefixe><ITEM NAME>" tenant dans `length` caracteres (longueur du modele d'origine, plus
    courte en anglais). Si "For Niicotine: " ne tient pas : forme compacte ">Niicoti: " (envoi) ou
    "<Niicoti: " (reception)."""
    room = length - len(PLACEHOLDER)
    if len(prefix) > room:
        word, _, rest = prefix.partition(" ")
        who = rest.rstrip(" :")
        if word in _SEND_WORDS + _RECV_WORDS and who and room >= 5:
            sign = ">" if word in _SEND_WORDS else "<"
            prefix = f"{sign}{who[:room - 3]}: "
        else:
            prefix = prefix[:max(0, room - 3)].rstrip() + " : "
    return prefix + PLACEHOLDER


def _fit(text: str, limit: int = MAX_LEN) -> str:
    """Tronque en gardant le numero final (" #12")."""
    if len(text) <= limit:
        return text
    head, sep, num = text.rpartition(" #")
    if sep and num.isdigit():
        tail = " #" + num
        return head[:limit - len(tail)].rstrip() + tail
    return text[:limit]


def short_location(location: str, lang: str = "fr", limit: int = MAX_LEN) -> str:
    """Nom de check court pour la notification (17 caracteres max dans le fil du jeu)."""
    from .i18n import short_place, t
    if location.startswith("Story ") and ": " in location:
        return _fit(location.split(": ", 1)[1], limit)     # titre du chapitre
    if location.startswith("Shop "):
        place, _, num = location[5:].rpartition(" #")
        return _fit(t(lang, "shop_short", place=short_place(lang, place), n=num), limit)
    for prefix in ("Chest: ", "AP Item: ", "Access Point: ", "Quest: "):
        if location.startswith(prefix):
            return _fit(location[len(prefix):], limit)
    return _fit(location, limit)


# Messages affiches par le mod (dinput8.dll) : en couleur, a part du fil du jeu, sans la limite de 17 caracteres.
OP_NOTE = 10
NOTE_MOD_VERSION = 7
NOTE_LIMIT = 60
NOTE_MS = 7000
NOTE_COLORS = {"check": 0xFFD34D, "mine": 0x7CE38B, "other": 0x6FB6FF, "trap": 0xFF6B6B}   # jaune, vert, bleu, rouge
NOTE_COLORS["chat"] = 0xF2F2F2                                              # blanc : message d'un joueur
CHAT_MARK = "\x01"            # debut du prefixe d'un message de joueur (non imprimable : jamais affiche)
CHAT_MAX_LINES = 3
JAM_START_PREFIX = "SYSTEM FAILURE: "
JAM_END_PREFIX = "Restored: "


def chat_notes(name: str, message: str) -> list:
    """Message d'un joueur -> lignes a afficher (au plus CHAT_MAX_LINES, NOTE_LIMIT caracteres chacune).
    Les commandes ("!hint ...") ne sont pas affichees."""
    import textwrap
    message = " ".join(str(message).split())
    if not message or message.startswith("!"):
        return []
    prefix = f"{name}: "[:24]
    lines = textwrap.wrap(message, max(10, NOTE_LIMIT - len(prefix)))[:CHAT_MAX_LINES]
    return [(CHAT_MARK + prefix, line) for line in lines]


def jam_notes(events) -> list:
    """Messages a l'ecran pour le debut et la fin d'une panne de systeme (traps.Jams.pop_events)."""
    return [(JAM_START_PREFIX, f"{a} ({int(s)} s)") if kind == "start" else (JAM_END_PREFIX, a)
            for kind, a, s in events]


def note_kind(prefix: str, lang: str = "en") -> str:
    """"check" (un check que j'ai fait), "mine" (un objet pour moi) ou "other" (un objet pour quelqu'un d'autre)."""
    from .i18n import t
    if prefix.startswith(CHAT_MARK):
        return "chat"
    if prefix == JAM_START_PREFIX:
        return "trap"
    if prefix == JAM_END_PREFIX:
        return "mine"
    if prefix == t(lang, "check"):
        return "check"
    if prefix == t(lang, "for_you") or prefix.split(" ", 1)[0] in _RECV_WORDS:
        return "mine"
    return "other"


def mod_can_note(mem) -> bool:
    return getattr(mem, "mod_version", 0) >= NOTE_MOD_VERSION


def send_note(mem, text: str, rgb: int, ms: int = NOTE_MS) -> bool:
    raw = "".join(ch for ch in text if ch.isprintable()).encode("utf-8")[:159]
    raw = raw.decode("utf-8", "ignore").encode("utf-8")              # ne coupe pas un caractere en deux
    return mem._ask(struct.pack("<BII", OP_NOTE, rgb, ms) + raw.ljust(160, b"\0"), 1) == b"\x01"


def messages_for_item_send(me: int, sender: int, receiver: int, item: str,
                           sender_name: str, receiver_name: str, location: str,
                           lang: str = "fr", limit: int = MAX_LEN) -> list[tuple[str, str]]:
    """(prefixe, texte) a afficher pour "sender a envoye item a receiver depuis location".
    Check valide par moi : "Check : <location>" puis "Pour <qui> : <objet>". Recu : "De <qui> : <objet>"."""
    from .i18n import t
    item = item[:limit]
    if sender == me:
        check = (t(lang, "check"), short_location(location, lang, limit)[:limit])
        to = t(lang, "for_you") if receiver == me else t(lang, "for", who=receiver_name)
        return [check, (to, item)]
    if receiver == me:
        return [(t(lang, "from", who=sender_name), item)]
    return []


def _scan(mem, patterns: list[bytes]) -> dict[bytes, list[int]]:
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI
    out: dict[bytes, list[int]] = {p: [] for p in patterns}
    SCAN_STATS[0] += 1
    import time as _time
    _t0 = _time.monotonic()
    try:
        return _scan_regions(mem, patterns, out)
    finally:
        SCAN_STATS[1] += _time.monotonic() - _t0


SCAN_STATS = [0, 0.0]          # nombre de recherches en memoire et secondes passees (diagnostic du demarrage)


def _scan_regions(mem, patterns, out):
    fast = getattr(mem, "scan", None)          # mod recent : il cherche lui-meme (0,5 s au lieu de 16 s)
    if fast is not None:
        found = {p: fast(p) for p in patterns}
        if all(v is not None for v in found.values()):
            return found
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    addr = 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000:
            try:
                data = mem.read(base, size)
            except OSError:
                data = b""
            for p in patterns:
                i = data.find(p)
                while i != -1:
                    if i % 2 == 0:
                        out[p].append(base + i)
                    i = data.find(p, i + 1)
        addr = base + size
    return out


def _remember_template(pid: int, current: bytes) -> bytes:
    """Texte d'origine du modele pour ce processus du jeu (lu une fois, garde sur disque)."""
    import os
    from pathlib import Path
    d = Path(os.environ.get("LOCALAPPDATA", ".")) / "NierAutomataAP"
    f = d / f"notify_template_{pid}.bin"
    try:
        data = f.read_bytes()
        if len(data) == len(current):
            return data
    except OSError:
        pass
    try:
        d.mkdir(parents=True, exist_ok=True)
        f.write_bytes(current)
    except OSError:
        pass
    return current


class Notifier:
    """Adresses des textes a modifier (cherchees une fois par processus)."""

    def __init__(self, mem, carrier_key: str = CARRIER_KEY, carrier_item: int = CARRIER_ITEM):
        self.mem = mem
        self.carrier_item = carrier_item
        key = carrier_key.encode("utf-16-le") + bytes(2)
        tkey = TEMPLATE_KEY.encode("utf-16-le") + bytes(2)
        found = _scan(mem, [key, tkey])
        self.carrier: Optional[int] = None
        for a in found[key]:
            length = struct.unpack("<I", mem.read(a + len(key), 4))[0]
            if 2 <= length <= 64:
                self.carrier = a + len(key) + 4
                self.carrier_orig = mem.read(self.carrier, (length - 1) * 2)
                break
        # modele retrouve par sa CLE, quelle que soit la langue (sa longueur varie). Son texte d'origine est
        # garde dans un fichier par processus : une session precedente a pu le laisser modifie.
        self.templates = []
        self.tlen = TEMPLATE_LEN
        self.orig_template = TEMPLATE.encode("utf-16-le")
        for a in found[tkey]:
            length = struct.unpack("<I", mem.read(a + len(tkey), 4))[0]
            if 10 <= length <= 80:
                value = a + len(tkey) + 4
                self.tlen = length - 1
                current = mem.read(value, self.tlen * 2)
                self.orig_template = _remember_template(mem.pid, current)
                copies = _scan(mem, [current + bytes(2)])[current + bytes(2)]
                self.templates = sorted(set(copies) | {value})
                self.restore()
                break

    @property
    def ok(self) -> bool:
        return self.carrier is not None and bool(self.templates)

    def show(self, prefix: str, item: str) -> bool:
        from .spawner import remote_call
        tpl = encode_fixed(template_for(prefix, self.tlen), self.tlen)
        for a in self.templates:
            self.mem.write(a, tpl)
        self.mem.write(self.carrier, encode_fixed(item, min(MAX_LEN, len(self.carrier_orig) // 2)))
        return remote_call(self.mem, self.mem.base + GIVE_ITEM_RVA, self.carrier_item, 1, 1, 1, e=1) & 0xFF == 1

    def prepare(self, prefix: str, item: str) -> None:
        """Ecrit modele + nom du porteur sans donner l'objet (le joueur va le ramasser)."""
        tpl = encode_fixed(template_for(prefix, self.tlen) if prefix else PLACEHOLDER, self.tlen)
        for a in self.templates:
            self.mem.write(a, tpl)
        self.mem.write(self.carrier, encode_fixed(item, min(MAX_LEN, len(self.carrier_orig) // 2)))

    def restore(self) -> None:
        for a in self.templates:
            self.mem.write(a, self.orig_template)
        if self.carrier is not None:
            self.mem.write(self.carrier, self.carrier_orig)
