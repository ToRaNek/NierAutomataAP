"""Ouvre un magasin par son nom et achete son premier objet (docs/research/shop_control.md).
    python tools/shop_buy.py PV|FC|RC"""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import remote_pad as rp  # noqa: E402
from nier_automata.game.spawner import remote_call  # noqa: E402

NAMES = {"PV": 0xCFC0E8, "FC": 0xCFBFE0}
UI = 0x1410E00
m = rp.ProcessMemory.attach()
cave = rp.install(m)
b = m.base
u32 = lambda r: struct.unpack("<I", m.read(b + r, 4))[0]
i32 = lambda r: struct.unpack("<i", m.read(b + r, 4))[0]
u8 = lambda r: m.read(b + r, 1)[0]


def snap():
    return {"mode": hex(u32(0x13FD7B8)), "etat": u32(UI + 0x12FC), "racine": u32(UI + 0x1308), "curseur": u32(UI + 0x1304),
            "n": u32(UI + 0x12F8), "confirm": u8(UI + 0x1319), "dlg": u32(0xF04038), "dlg_cur": u32(0xF04068),
            "G": i32(0x148C830),
            "liste728": [x for x in struct.unpack("<12i", m.read(b + UI + 0x728, 48))],
            "liste748": [x for x in struct.unpack("<6i", m.read(b + UI + 0x748, 24))]}


def wait(cond, t=6.0):
    end = time.time() + t
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


which = sys.argv[1]
name = m.read(b + NAMES[which], 0x20).split(bytes(1))[0]
print("magasin", name, "| avant", snap())
m.write(b + 0x148C830, struct.pack("<i", 9000))
for _ in range(3):
    remote_call(m, b + 0x81C870, b + NAMES[which])
    if wait(lambda: u32(UI + 0x12FC) == 1, 5):
        break
print("ouvert", snap())
rp.press(m, cave, 0x10)                                   # Acheter
print("liste ?", wait(lambda: u32(UI + 0x12FC) == 2), snap())
rp.press(m, cave, 0x10)                                   # premier objet
print("confirmation ?", wait(lambda: u32(0xF04038) == 2), snap())
rp.press(m, cave, 0x1)                                    # gauche : Oui
wait(lambda: u32(0xF04068) == 1, 2)
print("curseur", snap()["dlg_cur"])
rp.press(m, cave, 0x10)
time.sleep(2)
print("apres achat", snap())
for _ in range(3):
    rp.press(m, cave, 0x20)
    time.sleep(0.8)
print("ferme", {k: snap()[k] for k in ("mode", "etat", "G")})
