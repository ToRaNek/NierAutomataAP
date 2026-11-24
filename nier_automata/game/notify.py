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


def template_for(prefix: str, length: int = TEMPLATE_LEN) -> str:
    """Modele "<prefixe><ITEM NAME>" tenant dans `length` caracteres (longueur du modele d'origine)."""
    room = length - len(PLACEHOLDER)
    if len(prefix) > room:
        prefix = prefix[:room - 3].rstrip() + " : "
    return prefix + PLACEHOLDER


def short_location(location: str, lang: str = "fr") -> str:
    """Nom de check court pour la notification (17 caracteres max)."""
    from .i18n import short_place, t
    if location.startswith("Story: "):
        return location[7:]
    if location.startswith("Shop "):
        place, _, num = location[5:].rpartition(" #")
        return t(lang, "shop_short", place=short_place(lang, place), n=num)
    return location


def messages_for_item_send(me: int, sender: int, receiver: int, item: str,
                           sender_name: str, receiver_name: str, location: str,
                           lang: str = "fr") -> list[tuple[str, str]]:
    """(prefixe, texte) a afficher pour "sender a envoye item a receiver depuis location".
    Check valide par moi : "Check : <location>" puis "Pour <qui> : <objet>". Recu : "De <qui> : <objet>"."""
    from .i18n import t
    item = item[:MAX_LEN]
    if sender == me:
        to = t(lang, "for_you") if receiver == me else t(lang, "for", who=receiver_name)
        return [(t(lang, "check"), short_location(location, lang)[:MAX_LEN]), (to, item)]
    if receiver == me:
        return [(t(lang, "from", who=sender_name), item)]
    return []


def _scan(mem, patterns: list[bytes]) -> dict[bytes, list[int]]:
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI
    out: dict[bytes, list[int]] = {p: [] for p in patterns}
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
