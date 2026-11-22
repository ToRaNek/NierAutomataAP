"""Sonde NieR:Automata : verifie la version, affiche la phase et l'inventaire en direct.

Usage :
    python tools/probe.py                     # affichage continu
    python tools/probe.py --once              # une seule lecture
    python tools/probe.py --dump-weapons-around
Les changements de phase sont logges dans tools/phases_seen.log.
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nier_automata.data.offsets import OFFSETS, detect_version  # noqa: E402
from nier_automata.game.memory import ProcessMemory, read_cstr, read_u32  # noqa: E402

EMPTY = 0xFFFFFFFF
ITEM_SLOT, ITEM_COUNT = 12, 200
WEAPON_SLOT, WEAPON_COUNT = 0x14, 39
LOG = Path(__file__).with_name("phases_seen.log")


def slots(mem, start, size, count):
    out = []
    raw = mem.read(mem.base + start, size * count)
    for i in range(count):
        a, b, c = struct.unpack_from("<III", raw, i * size)
        if a != EMPTY:
            out.append((i, a, b, c))
    return out


def snapshot(mem, off):
    return {
        "phase": read_cstr(mem, off["currentPhase"]),
        "loading": read_u32(mem, off["isLoading"]),
        "world": read_u32(mem, off["isWorldLoaded"]),
        "items": slots(mem, off["itemTableStart"], ITEM_SLOT, ITEM_COUNT),
        "weapons": slots(mem, off["weaponTableStart"], WEAPON_SLOT, WEAPON_COUNT),
    }


def show(s):
    print(f"Phase : {s['phase']!r}   isLoading={s['loading']}  isWorldLoaded={s['world']}")
    print(f"Objets ({len(s['items'])}) : " + ", ".join(f"id={i[1]} x{i[3]}" for i in s["items"][:20]))
    print(f"Armes ({len(s['weapons'])}) : " + ", ".join(f"id=0x{w[1]:X} niv={w[2]}" for w in s["weapons"][:20]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dump-weapons-around", action="store_true")
    args = ap.parse_args()

    mem = ProcessMemory.attach()
    if mem is None:
        print("NieRAutomata.exe introuvable : lance le jeu.")
        return 1
    version = detect_version(mem.exe_path)
    print(f"Process {mem.pid}, base 0x{mem.base:X}, exe {mem.exe_path}")
    print(f"Version : {version or 'INCONNUE'}")
    if version is None:
        return 1
    off = OFFSETS[version]

    if args.dump_weapons_around:
        start = 0x148DC00
        raw = mem.read(mem.base + start, 0x800)
        for i in range(0, len(raw), 16):
            print(f"{start + i:08X}: " + raw[i:i + 16].hex(" "))
        return 0

    last_phase = None
    while True:
        s = snapshot(mem, off)
        if s["phase"] != last_phase:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{s['phase']}\n")
            last_phase = s["phase"]
        if args.once:
            show(s)
            return 0
        print("\x1b[2J\x1b[H", end="")
        show(s)
        if not mem.is_alive():
            print("Jeu ferme.")
            return 0
        time.sleep(0.5)


if __name__ == "__main__":
    sys.exit(main())
