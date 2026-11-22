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
ACTIVE_STATUS = 0x00070000
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
                 status_off: Optional[int], qty_off: int, stackable: bool):
        self.mem = mem
        self.start = start
        self.count = count
        self.slot_size = slot_size
        self.status_off = status_off
        self.qty_off = qty_off
        self.stackable = stackable

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
    return SlotTable(mem, start, count, WEAPON_SLOT_SIZE, status_off=None, qty_off=4, stackable=False)
