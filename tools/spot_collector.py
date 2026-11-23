"""Collecte automatique d'emplacements pendant une partie normale.

- coffre ouvert (compteur 0xF50F60 qui augmente) : position de 2B -> tools/spots_chests.tsv
- changement de zone : positions des objets poses au sol (BehaviorSetItem) -> tools/spots_items.tsv
Leger : lecture toutes les 0,5 s ; le scan memoire n'a lieu qu'au changement de zone.
"""
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.memory import ProcessMemory, read_cstr, read_u32  # noqa: E402
from nier_automata.game.ap_items import SET_ITEM_VTABLE_RVA  # noqa: E402
from nier_automata.game.spawner import _MBI  # noqa: E402

HERE = Path(__file__).parent
CHESTS, ITEMS = HERE / "spots_chests.tsv", HERE / "spots_items.tsv"


def player_pos(m):
    p = struct.unpack("<Q", m.read(m.base + 0x1020C88, 8))[0]
    return struct.unpack("<3f", m.read(p + 0x50, 12)) if p else None


def scan_items(m):
    import ctypes
    from ctypes import wintypes
    k = m._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    vt = m.base + SET_ITEM_VTABLE_RVA
    out, addr = [], 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(m.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000 and size % 8 == 0:
            try:
                arr = memoryview(m.read(base, size)).cast("Q")
                for i, v in enumerate(arr):
                    if v == vt:
                        o = base + i * 8
                        if struct.unpack("<I", m.read(o + 0x838, 4))[0] < 0x10000:  # pas nos AP Items
                            out.append(struct.unpack("<3f", m.read(o + 0x50, 12)))
            except OSError:
                pass
        addr = base + size
    return out


def log(path, phase, pos, extra=""):
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{phase}\t{pos[0]:.1f}\t{pos[1]:.1f}\t{pos[2]:.1f}\t{extra}\n")


def main():
    while True:
        m = ProcessMemory.attach()
        if m is None:
            time.sleep(10); continue
        last_chest, last_phase = None, None
        try:
            while m.is_alive():
                phase = read_cstr(m, 0xF64B20)
                chest = read_u32(m, 0xF50F60)
                pos = player_pos(m)
                if pos and last_chest is not None and chest == last_chest + 1:
                    log(CHESTS, phase, pos, "coffre")
                    print("coffre", phase, [round(v, 1) for v in pos], flush=True)
                last_chest = chest
                if phase != last_phase and phase not in ("", "SIGNIN", "START"):
                    time.sleep(5)  # laisser la zone se charger
                    for p in scan_items(m):
                        log(ITEMS, phase, p, "objet")
                    last_phase = phase
                time.sleep(0.5)
        except OSError:
            time.sleep(5)


if __name__ == "__main__":
    main()
