"""Charge une unite d'interieur (wd5) comme le font les ascenseurs / le voyage rapide (room_loading.md 4.A),
puis verifie les coffres de la salle.    python tools/rooms.py <unite hex> [region...]"""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phase_jump as pj  # noqa: E402

REQ = 0x11EABD0


def u32(m, r):
    return struct.unpack("<I", m.read(m.base + r, 4))[0]


def room_states(m):
    out = {}
    for i in range(16):
        room, st = struct.unpack("<II", m.read(m.base + 0x130C890 + 0x178 * i, 8))
        if st:
            out[hex(room)] = st
    return out


def load_unit(m, unit, wait=60.0):
    st = pj.state(m)
    if st["machine"] != 2 or st["scene"] != 1 or u32(m, REQ) not in (0, 5):
        raise RuntimeError(f"jeu pas pret : {st} demandeur {u32(m, REQ)}")
    m.write(m.base + 0x11EABF4, struct.pack("<8I", unit, *([0xFFFFFFFF] * 7)))
    m.write(m.base + 0x11EAC14, struct.pack("<I", 1))
    if u32(m, REQ) == 0:
        m.write(m.base + REQ, struct.pack("<I", 1))
    seen, t0 = [], time.time()
    while time.time() - t0 < wait:
        v = u32(m, REQ)
        if not seen or seen[-1] != v:
            seen.append(v)
        if v == 5 and room_states(m).get(hex(unit >> 8)) == 4:
            return True, seen
        time.sleep(0.2)
    return False, seen


def back_to_world(m, wait=60.0):
    if u32(m, REQ) == 5:
        m.write(m.base + REQ, struct.pack("<I", 6))
    t0 = time.time()
    while time.time() - t0 < wait:
        if u32(m, REQ) == 0:
            return True
        time.sleep(0.2)
    return False
