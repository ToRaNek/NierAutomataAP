"""Pilote le jeu sans focus : detour de la lecture XInput + patchs anti-pause (docs/research/remote_control.md).

    python tools/remote_pad.py install | remove | press <masque hex> [duree s] | move <lx> <ly> <duree s> | status
Boutons : croix 1/2/4/8 (gauche, droite, bas, haut), A 0x10, B 0x20, X 0x40, Y 0x80, START 0x100, BACK 0x200.
"""
import ctypes
import struct
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.memory import ProcessMemory  # noqa: E402

SITE, READ_PAD = 0x277438, 0x278D10
SITE_ORIGINAL = bytes.fromhex("e8d3180000")
PATCHES = [(0x9C6280, b"\x02", b"\x00"), (0x86C5DC, b"\x05", b"\x03")]   # pause / effacement des pads sans focus
CTL = 0x100


def cave_code(cave: int, base: int) -> bytes:
    head = bytes.fromhex("4883EC28") + b"\x48\xB8" + struct.pack("<Q", base + READ_PAD) + b"\xFF\xD0"
    tail = bytes.fromhex("4883C428C3")
    c3 = bytes.fromhex("0F10400C" "0F114704" "488B481C" "48894F14")
    c2 = bytes.fromhex("C70701000000" "8B4804" "094F1C" "83780800") + b"\x74" + bytes([len(c3)]) + c3
    lea_end = len(head) + 5 + 7              # apres cmp/jne (5) et lea (7)
    c1 = b"\x48\x8D\x05" + struct.pack("<i", CTL - lea_end) + bytes.fromhex("833800") + b"\x74" + bytes([len(c2)])
    body = c1 + c2
    return head + bytes.fromhex("83FE04") + b"\x75" + bytes([len(body)]) + body + tail


def find_cave(m):
    cur = m.read(m.base + SITE, 5)
    if cur == SITE_ORIGINAL:
        return None
    return m.base + SITE + 5 + struct.unpack("<i", cur[1:])[0]


def install(m):
    cave = find_cave(m)
    if cave is None:
        k = m._k
        k.OpenProcess.restype = wintypes.HANDLE
        h = k.OpenProcess(0x1F0FFF, False, m.pid)
        k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        k.VirtualAllocEx.restype = ctypes.c_void_p
        for delta in range(0x18000000, 0x7F000000, 0x1000000):
            cave = k.VirtualAllocEx(h, ctypes.c_void_p((m.base - delta) & ~0xFFFF), 0x1000, 0x3000, 0x40)
            if cave:
                break
        k.CloseHandle(h)
        if not cave:
            raise SystemExit("pas de cave")
        m.write(cave + CTL, bytes(0x40))
        m.write(cave, cave_code(cave, m.base))
        m.write_code(m.base + SITE, b"\xE8" + struct.pack("<i", cave - (m.base + SITE + 5)))
    for rva, old, new in PATCHES:
        if m.read(m.base + rva, 1) == old:
            m.write_code(m.base + rva, new)
    return cave


def remove(m):
    cave = find_cave(m)
    if cave:
        m.write(cave + CTL, bytes(4))
        m.write_code(m.base + SITE, SITE_ORIGINAL)
    for rva, old, new in PATCHES:
        if m.read(m.base + rva, 1) == new:
            m.write_code(m.base + rva, old)


def set_state(m, cave, buttons=0, axes=None):
    lx, ly = axes or (0.0, 0.0)
    m.write(cave + CTL + 4, struct.pack("<II6f", buttons, 1 if axes else 0, lx, ly, 0, 0, 0, 0))
    m.write(cave + CTL, struct.pack("<I", 1))


def press(m, cave, mask, hold=0.15):
    set_state(m, cave, mask)
    time.sleep(hold)
    set_state(m, cave, 0)
    time.sleep(0.15)


def move(m, cave, lx, ly, dur):
    set_state(m, cave, 0, (lx, ly))
    time.sleep(dur)
    set_state(m, cave, 0)


def pos(m):
    pl = struct.unpack("<Q", m.read(m.base + 0x1020C88, 8))[0]
    return struct.unpack("<3f", m.read(pl + 0x50, 12)) if pl else None


if __name__ == "__main__":
    m = ProcessMemory.attach()
    cmd = sys.argv[1]
    if cmd == "remove":
        remove(m)
    elif cmd == "status":
        print("cave", hex(find_cave(m) or 0), "pos", pos(m), "pad0", m.read(m.base + 0x13FCF80, 0x38).hex())
    else:
        c = install(m)
        if cmd == "press":
            press(m, c, int(sys.argv[2], 16), float(sys.argv[3]) if len(sys.argv) > 3 else 0.15)
        elif cmd == "move":
            move(m, c, float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))
        print("cave", hex(c), "pos", [round(v, 2) for v in pos(m)])
