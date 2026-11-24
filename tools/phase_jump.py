"""Saut de phase brut (docs/research/phase_jump.md, option B) : python tools/phase_jump.py <phase hex> <sous-phase>"""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import remote_pad as rp  # noqa: E402
from nier_automata.game.spawner import remote_call  # noqa: E402


def state(m):
    b = m.base
    u = lambda r: struct.unpack("<I", m.read(b + r, 4))[0]
    return {"phase": hex(u(0xF64AA0)), "sub": m.read(b + 0xF64AA8, 0x20).split(b"\0")[0].decode(),
            "machine": u(0xF64A9C), "scene": u(0x102A368)}


def jump(m, phase: int, sub: str, wait: float = 90.0) -> bool:
    cave = rp.install(m)
    name = cave + 0x200
    m.write(name, sub.encode() + bytes(0x21 - len(sub)))
    m.write(m.base + 0x14958B0, struct.pack("<I", 0x40000000))
    remote_call(m, m.base + 0x761460, m.base + 0x102A360, phase, name, 1, e=0)
    end = time.time() + wait
    time.sleep(3)
    while time.time() < end:
        s = state(m)
        if s["sub"] == sub and s["machine"] == 2 and s["scene"] == 1:
            return True
        time.sleep(1)
    return False


if __name__ == "__main__":
    m = rp.ProcessMemory.attach()
    print("avant", state(m))
    ok = jump(m, int(sys.argv[1], 16), sys.argv[2])
    print("saut", ok, state(m), "pos", [round(v, 1) for v in rp.pos(m)] if ok else None)
