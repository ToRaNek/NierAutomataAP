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
GIVE_ITEM_RVA = 0x8006F0


def template_for(prefix: str) -> str:
    room = TEMPLATE_LEN - len(PLACEHOLDER)
    if len(prefix) > room:
        prefix = prefix[:room - 3].rstrip() + " : "
    return prefix + PLACEHOLDER


def messages_for_item_send(me: int, sender: int, receiver: int, item: str,
                           sender_name: str, receiver_name: str) -> list[tuple[str, str]]:
    """(prefixe, nom d'objet) a afficher pour "sender a envoye item a receiver"."""
    item = item[:MAX_LEN]
    if receiver == me and sender == me:
        return [("Trouvé : ", item)]
    if receiver == me:
        return [(f"De {sender_name} : ", item)]
    if sender == me:
        return [(f"Pour {receiver_name} : ", item)]
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


class Notifier:
    """Adresses des textes a modifier (cherchees une fois par processus)."""

    def __init__(self, mem):
        self.mem = mem
        key = CARRIER_KEY.encode("utf-16-le") + b"\0\0"
        tpl = TEMPLATE.encode("utf-16-le") + b"\0\0"
        found = _scan(mem, [key, tpl])
        self.carrier: Optional[int] = None
        for a in found[key]:
            length = struct.unpack("<I", mem.read(a + len(key), 4))[0]
            if 2 <= length <= 64:
                self.carrier = a + len(key) + 4
                self.carrier_orig = mem.read(self.carrier, (length - 1) * 2)
                break
        self.templates = found[tpl]

    @property
    def ok(self) -> bool:
        return self.carrier is not None and bool(self.templates)

    def show(self, prefix: str, item: str) -> bool:
        from .spawner import remote_call
        tpl = template_for(prefix).encode("utf-16-le").ljust(TEMPLATE_LEN * 2, b"\0")
        for a in self.templates:
            self.mem.write(a, tpl)
        self.mem.write(self.carrier, item[:MAX_LEN].encode("utf-16-le").ljust(MAX_LEN * 2, b"\0"))
        return remote_call(self.mem, self.mem.base + GIVE_ITEM_RVA, CARRIER_ITEM, 1, 1, 1, e=1) & 0xFF == 1

    def restore(self) -> None:
        orig = TEMPLATE.encode("utf-16-le")
        for a in self.templates:
            self.mem.write(a, orig)
        if self.carrier is not None:
            self.mem.write(self.carrier, self.carrier_orig)
