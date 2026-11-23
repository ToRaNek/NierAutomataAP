"""Table des puces (plug-in chips). Format AutomataSpeedrunMod ChipManager : 300 slots de 48 octets.

Slot : unknown0, id, type_index, level, cost, setA, setB, setC, u1, u2, u3, u4 (u32).
id = 0xFFFFFFFF : slot vide. Puce OS : u1 = u2 = u3 = 0 (ne jamais la retirer).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .memory import Memory

CHIP_SLOT_SIZE = 48
CHIP_SLOTS = 300
EMPTY = 0xFFFFFFFF
# "Puce systeme" (verifiee en jeu v1.04 : id 3338, type 42, slot 0, cout 2).
SYSTEM_CHIP_TYPES = {42}


@dataclass
class Chip:
    index: int
    raw: bytes
    chip_id: int
    type_index: int
    level: int
    cost: int
    is_os: bool


def _parse(index: int, raw: bytes) -> Chip:
    f = struct.unpack("<12I", raw)
    is_os = (f[8] == 0 and f[9] == 0 and f[10] == 0) or (f[1] != EMPTY and f[2] in SYSTEM_CHIP_TYPES)
    return Chip(index, raw, f[1], f[2], f[3], f[4], is_os)


class ChipTable:
    def __init__(self, mem: Memory, start: int, count: int = CHIP_SLOTS):
        self.mem, self.start, self.count = mem, start, count

    def _addr(self, i: int) -> int:
        return self.mem.base + self.start + i * CHIP_SLOT_SIZE

    def _all(self) -> list[Chip]:
        raw = self.mem.read(self._addr(0), self.count * CHIP_SLOT_SIZE)
        return [_parse(i, raw[i * CHIP_SLOT_SIZE:(i + 1) * CHIP_SLOT_SIZE]) for i in range(self.count)]

    def read_all(self) -> list[Chip]:
        return [c for c in self._all() if c.chip_id != EMPTY]

    def add_raw(self, raw: bytes) -> bool:
        if len(raw) != CHIP_SLOT_SIZE:
            raise ValueError("une puce fait 48 octets")
        free = next((c for c in self._all() if c.chip_id == EMPTY), None)
        if free is None:
            return False
        addr = self._addr(free.index)
        self.mem.write(addr, raw[:4])
        self.mem.write(addr + 8, raw[8:])
        self.mem.write(addr + 4, raw[4:8])  # id en dernier
        return True

    def remove(self, slot_index: int) -> bool:
        c = self._all()[slot_index]
        if c.chip_id == EMPTY or c.is_os:
            return False
        self.mem.write(self._addr(slot_index) + 4, struct.pack("<I", EMPTY))
        return True
