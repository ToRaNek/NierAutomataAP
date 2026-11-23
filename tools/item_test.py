"""Fait apparaitre un it0000 a 1 m de 2B avec un champ de la fiche de placement force, puis
surveille l'inventaire 40 s pour voir ce qui est obtenu au ramassage.
    python tools/item_test.py <offset_hex> <valeur>"""
import struct, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.memory import ProcessMemory
from nier_automata.game.spawner import alloc, remote_call, set_info_bytes, REQUEST_CREATE_RVA, MANAGER_RVA
from nier_automata.game.inventory import item_table
off, val = int(sys.argv[1], 16), int(sys.argv[2])
m = ProcessMemory.attach()
p = struct.unpack("<Q", m.read(m.base + 0x1020C88, 8))[0]; ex, ey, ez = struct.unpack("<3f", m.read(p + 0x50, 12))
si = bytearray(set_info_bytes((ex + 1, ey, ez)))
if off: struct.pack_into("<I", si, off, val)
buf = alloc(m, bytes(si) + b"\0" * 0x70 + b"it0000\0")
inv = item_table(m, 0x148C834); before = {s.item_id: s.quantity for s in inv.read_all()}
remote_call(m, m.base + REQUEST_CREATE_RVA, m.base + MANAGER_RVA, buf + 0x100, 0x70000, buf)
print(f"objet a tes pieds (fiche {hex(off)}={val})", flush=True)
t0 = time.time()
while time.time() - t0 < 40:
    now = {s.item_id: s.quantity for s in inv.read_all()}
    d = {k: (before.get(k, 0), v) for k, v in now.items() if before.get(k, 0) != v}
    if d: print(f"obtenu apres {time.time()-t0:.1f}s :", d); break
    time.sleep(0.1)
else: print("rien ramasse")
