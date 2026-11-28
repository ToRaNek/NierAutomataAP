"""Tables de slots d'inventaire (objets et armes) en memoire.

Objet : 12 octets = id u32, statut u32, quantite u32.
Arme  : 20 octets = id u32, niveau u32, ... (format nierhook).
Slot vide : id = 0xFFFFFFFF.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from .memory import Memory

EMPTY = 0xFFFFFFFF
# Statut observe en memoire v1.04 sur les objets existants (0x00070000 = valeur dans le fichier de save).
ACTIVE_STATUS = 0xFFFFFFFF
ITEM_SLOT_SIZE = 12
WEAPON_SLOT_SIZE = 0x14
# Bornes nierhook v1.02 (meme taille en v1.04).
ITEM_SLOTS = (0x148CE18 - 0x148C4C4) // ITEM_SLOT_SIZE + 1
WEAPON_SLOTS = (0x148DFBC - 0x148DCC4) // WEAPON_SLOT_SIZE + 1
MAX_STACK = 99


@dataclass
class Slot:
    index: int
    item_id: int
    status: int
    quantity: int


class SlotTable:
    """status_off / qty_off : position des champs dans le slot (None = absent)."""

    def __init__(self, mem: Memory, start: int, count: int, slot_size: int,
                 status_off: Optional[int], qty_off: int, stackable: bool,
                 fixed_slots: Optional[dict[int, int]] = None):
        self.mem = mem
        self.start = start
        self.count = count
        self.slot_size = slot_size
        self.status_off = status_off
        self.qty_off = qty_off
        self.stackable = stackable
        self.fixed_slots = fixed_slots or {}

    def _addr(self, index: int) -> int:
        return self.mem.base + self.start + index * self.slot_size

    def _u32(self, raw: bytes, off: int) -> int:
        return struct.unpack_from("<I", raw, off)[0]

    def _all(self) -> list[Slot]:
        raw = self.mem.read(self._addr(0), self.count * self.slot_size)
        out = []
        for i in range(self.count):
            base = i * self.slot_size
            status = self._u32(raw, base + self.status_off) if self.status_off is not None else 0
            out.append(Slot(i, self._u32(raw, base), status, self._u32(raw, base + self.qty_off)))
        return out

    def read_all(self) -> list[Slot]:
        return [s for s in self._all() if s.item_id != EMPTY]

    def find(self, item_id: int) -> Optional[Slot]:
        return next((s for s in self.read_all() if s.item_id == item_id), None)

    def _put(self, index: int, offset: int, value: int) -> None:
        self.mem.write(self._addr(index) + offset, struct.pack("<I", value))

    def add(self, item_id: int, quantity: int, status: int = ACTIVE_STATUS) -> bool:
        slots = self._all()
        for s in slots:
            if s.item_id == item_id:
                if self.stackable:
                    self._put(s.index, self.qty_off, min(MAX_STACK, s.quantity + quantity))
                return True
        target = self.fixed_slots.get(item_id)
        if target is not None and target < self.count and slots[target].item_id == EMPTY:
            free = slots[target]
        else:
            free = next((s for s in slots if s.item_id == EMPTY), None)
        if free is None:
            return False
        if self.status_off is not None:
            self._put(free.index, self.status_off, status)
        self._put(free.index, self.qty_off, min(MAX_STACK, quantity) if self.stackable else quantity)
        self._put(free.index, 0, item_id)  # id en dernier : le slot n'existe qu'une fois complet
        return True

    def remove(self, item_id: int) -> bool:
        s = self.find(item_id)
        if s is None:
            return False
        self._put(s.index, 0, EMPTY)
        return True


def item_table(mem: Memory, start: int, count: int = ITEM_SLOTS) -> SlotTable:
    return SlotTable(mem, start, count, ITEM_SLOT_SIZE, status_off=4, qty_off=8, stackable=True)


def weapon_table(mem: Memory, start: int, count: int = WEAPON_SLOTS) -> SlotTable:
    # Chaque arme a sa case reservee (ordre du tableur nierhook = ordre de WEAPONS).
    from ..data.weapons import WEAPONS
    fixed = {wid: i for i, wid in enumerate(WEAPONS.values())}
    return SlotTable(mem, start, count, WEAPON_SLOT_SIZE, status_off=None, qty_off=4, stackable=False,
                     fixed_slots=fixed)


# Programmes de Pod possedes : 31 emplacements {i32 identifiant (-1 = vide), i32 1} (trouve par comparaison
# memoire avant/apres le don d'un programme, v1.04).
# Le jeu ne regarde que QUELLE CASE est remplie : la case k est le k-ieme programme de sa liste, quel que soit
# l'identifiant ecrit dedans (verifie en jeu : 2024 et 2006 ecrits dans les cases 1 et 2 s'affichaient "R020:
# Mirage" et "R030: Hammer" ; les cases 1 a 11 remplies d'un identifiant bidon donnaient Mirage ... Repair, et le
# compteur "Pod Programs" du menu suit le nombre de cases remplies parmi les 17 premieres).
POD_PROGRAMS_RVA = 0x148E680
POD_PROGRAM_SLOTS = 31
# identifiant du programme de chaque case (ordre de la table du jeu, docs/research/pod_programs.json)
POD_PROGRAM_ORDER = (2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2015, 2019, 2021, 2022,
                     2024)


def read_pod_programs(mem) -> set:
    """Programmes que le jeu affiche comme possedes : ceux dont la case est remplie."""
    import struct
    raw = mem.read(mem.base + POD_PROGRAMS_RVA, len(POD_PROGRAM_ORDER) * 8)
    ids = struct.unpack(f"<{len(POD_PROGRAM_ORDER) * 2}i", raw)[::2]
    return {POD_PROGRAM_ORDER[i] for i, cur in enumerate(ids) if cur != -1}


def add_pod_program(mem, program_id: int) -> bool:
    """Donne un programme en remplissant SA case, sans le message du jeu. False si le programme est inconnu."""
    import struct
    if program_id not in POD_PROGRAM_ORDER:
        return False
    addr = mem.base + POD_PROGRAMS_RVA + POD_PROGRAM_ORDER.index(program_id) * 8
    if struct.unpack("<i", mem.read(addr, 4))[0] == -1:
        mem.write(addr, struct.pack("<2i", program_id, 1))
    return True


def remove_pod_program(mem, program_id: int) -> bool:
    """Retire un programme en vidant sa case ; les autres ne bougent pas."""
    import struct
    if program_id in POD_PROGRAM_ORDER:
        mem.write(mem.base + POD_PROGRAMS_RVA + POD_PROGRAM_ORDER.index(program_id) * 8, struct.pack("<2i", -1, 1))
    return True
