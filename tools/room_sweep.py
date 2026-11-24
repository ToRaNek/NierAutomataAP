"""Verifie les coffres des interieurs : charge chaque unite wd5 par le demandeur du jeu, se place a cote de chaque
coffre non confirme et cherche l'objet coffre. Met a jour docs/research/ingame_verified.json.
    python tools/room_sweep.py [unite hex ...]"""
import json
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import resweep  # noqa: E402
import rooms  # noqa: E402
import sweep  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "docs/research/ingame_verified.json"
UNITS = {"st5/r502.dat": 0x50200, "st5/r503.dat": 0x50300, "st5/r530.dat": 0x53001, "st5/r500.dat": 0x50001,
         "st5/r501.dat": 0x50100, "st5/r520.dat": 0x52001}


def main():
    world = json.loads((ROOT / "docs/research/world_positions.json").read_text(encoding="utf-8"))
    real = [x for x in world["chests"] if x["box"].get("contents")]
    src = lambda c: min(real, key=lambda x: math.dist(x["position"], c["pos"]))["file"]
    ver = json.loads(VER.read_text(encoding="utf-8"))
    only = {int(a, 16) for a in sys.argv[1:]}
    g = sweep.Game()
    m = g.m
    for file, unit in UNITS.items():
        if only and unit not in only:
            continue
        cs = [c for c in db.CHESTS if c["pos"] not in ver["chests_present"] and src(c) == file]
        if not cs:
            continue
        first = cs[0]["pos"]
        tgt = (first[0] + 1.0, first[1] + 1.0, first[2])
        m.write(m.base + 0x11EABF4, struct.pack("<8I", unit, *([0xFFFFFFFF] * 7)))
        m.write(m.base + 0x11EAC14, struct.pack("<I", 1))
        if rooms.u32(m, rooms.REQ) == 0:
            m.write(m.base + rooms.REQ, struct.pack("<I", 1))
        t0, ok = time.time(), False
        while time.time() - t0 < 70:
            g.tp(*tgt)
            if rooms.u32(m, rooms.REQ) == 5 and rooms.room_states(m).get(hex(unit >> 8)) == 4:
                ok = True
                break
            time.sleep(0.15)
        print(file, hex(unit), "charge" if ok else "ECHEC", rooms.room_states(m), flush=True)
        if not ok:
            continue
        for c in cs:
            p = c["pos"]
            g.hold((p[0] + 1.0, p[1] + 1.0, p[2]), 3.5)
            d = min((math.dist(q, p) for q, _ in resweep.chest_objects(g)), default=999)
            res = "present" if d < 4 else "absent"
            if res == "present":
                ver["chests_present"].append(p)
                if p in ver["chests_not_found"]:
                    ver["chests_not_found"].remove(p)
                VER.write_text(json.dumps(ver, indent=1), encoding="utf-8")
            print("  ", c["name"], res, flush=True)
    # retour au monde ouvert, a un endroit sur
    safe = (-70.0, 1.0, 593.0)
    if rooms.u32(m, rooms.REQ) == 5:
        m.write(m.base + rooms.REQ, struct.pack("<I", 6))
        t0 = time.time()
        while time.time() - t0 < 60 and rooms.u32(m, rooms.REQ) != 0:
            g.tp(*safe)
            time.sleep(0.15)
        g.hold(safe, 6)
    print("retour au monde:", rooms.u32(m, rooms.REQ) == 0, [round(v, 1) for v in g.pos()], rooms.room_states(m))


if __name__ == "__main__":
    main()
