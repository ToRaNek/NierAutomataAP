"""Facade haut niveau sur le processus NieRAutomata.exe."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..data.items_data import FILLER_ITEMS, FILLER_QUANTITY, FUNDS_ITEMS, TRAP_ITEMS
from ..data.offsets import OFFSETS, detect_version
from ..data.phases import MENU_PHASES
from ..data.weapons import WEAPONS
import struct

from .deathlink import HP_OFFSET, MAX_HP_COPY_OFFSET, add_funds
from .traps import damage_after_trap, funds_after_trap
from .inventory import item_table, weapon_table
from .memory import ProcessMemory, read_cstr, read_u32


def save_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents" / "My Games" / "NieR_Automata"


def backup_saves(src: Optional[Path] = None, dst_root: Optional[Path] = None) -> Optional[Path]:
    src = src or save_dir()
    files = list(src.glob("SlotData_*.dat")) + list(src.glob("GameData.dat"))
    if not files:
        return None
    root = dst_root or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NierAutomataAP" / "backups"
    dst = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dst / f.name)
    return dst


class NierGame:
    def __init__(self):
        self.mem: Optional[ProcessMemory] = None
        self.version: Optional[str] = None
        self.error: Optional[str] = None

    def attach(self) -> bool:
        if self.mem is not None and self.mem.is_alive():
            return True
        if self.mem is not None:
            self.mem.close()
        self.mem, self.version = ProcessMemory.attach(), None
        if self.mem is None:
            self.error = "Jeu non lance"
            return False
        self.version = detect_version(self.mem.exe_path)
        if self.version is None:
            self.error = "Version de NieRAutomata.exe inconnue : seule la v1.04 Steam est supportee"
            self.mem.close()
            self.mem = None
            return False
        self.error = None
        o = OFFSETS[self.version]
        self._off = o
        self._items = item_table(self.mem, o["itemTableStart"])
        self._weapons = weapon_table(self.mem, o["weaponTableStart"])
        return True

    def in_game(self) -> bool:
        try:
            if not self.attach():
                return False
            phase = self.phase()
            return (phase not in MENU_PHASES and bool(phase)
                    and read_u32(self.mem, self._off["isLoading"]) == 0
                    and read_u32(self.mem, self._off["isWorldLoaded"]) != 0)
        except OSError:
            self.mem = None
            return False

    def phase(self) -> str:
        return read_cstr(self.mem, self._off["currentPhase"])

    def chest_counter(self) -> int:
        return read_u32(self.mem, self._off["chestCounter"])

    def position(self) -> tuple[float, float, float]:
        return struct.unpack("<3f", self.mem.read(self.mem.base + self._off["playerLocation"], 12))

    def owned_items(self) -> set[int]:
        return {s.item_id for s in self._items.read_all()}

    def owned_weapons(self) -> set[int]:
        return {s.item_id for s in self._weapons.read_all()}

    def give(self, name: str) -> bool:
        if name in WEAPONS:
            return self._weapons.add(WEAPONS[name], 1)
        if name in TRAP_ITEMS:
            return self.apply_trap(*TRAP_ITEMS[name])
        if name in FUNDS_ITEMS:
            add_funds(self.mem, self._off["funds"], FUNDS_ITEMS[name])
            return True
        if name in FILLER_ITEMS:
            return self._items.add(FILLER_ITEMS[name], FILLER_QUANTITY.get(name, 1))
        return True  # objet inconnu : ignore plutot que bloquer la file

    def remove_weapon(self, weapon_id: int) -> bool:
        return self._weapons.remove(weapon_id)

    def entity(self) -> Optional[int]:
        try:
            p = struct.unpack("<Q", self.mem.read(self.mem.base + self._off["playerEntity"], 8))[0]
        except (OSError, AttributeError):
            return None
        return p if 0x10000 < p < 0x7FFFFFFFFFFF else None

    def hp(self) -> Optional[int]:
        p = self.entity()
        if p is None:
            return None
        try:
            return struct.unpack("<I", self.mem.read(p + HP_OFFSET, 4))[0]
        except OSError:
            return None

    def kill(self) -> bool:
        p = self.entity()
        if p is None:
            return False
        try:
            self.mem.write(p + HP_OFFSET, struct.pack("<I", 0))
        except OSError:
            return False
        return True

    def apply_trap(self, kind: str, percent: int) -> bool:
        """False = pas applicable maintenant (pas d'entite) : le client reessaie au tour suivant."""
        if kind == "money":
            funds = read_u32(self.mem, self._off["funds"])
            self.mem.write(self.mem.base + self._off["funds"], struct.pack("<I", funds_after_trap(funds, percent)))
            return True
        p = self.entity()
        if p is None:
            return False
        try:
            hp, = struct.unpack("<I", self.mem.read(p + HP_OFFSET, 4))
            max_hp, = struct.unpack("<I", self.mem.read(p + MAX_HP_COPY_OFFSET, 4))
            if hp == 0 or max_hp == 0:
                return False
            self.mem.write(p + HP_OFFSET, struct.pack("<I", damage_after_trap(hp, max_hp, percent)))
        except OSError:
            return False
        return True

    def grounded(self) -> Optional[bool]:
        """2B au sol = compteur de sauts (+0x14A8) a 0. None si illisible."""
        p = self.entity()
        if p is None:
            return None
        try:
            return struct.unpack("<I", self.mem.read(p + 0x14A8, 4))[0] == 0
        except OSError:
            return None
