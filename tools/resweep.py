"""Deuxieme passe sur les coffres non retrouves : pour chacun, saut a la phase (de sa route, a partir de son
chapitre) dont le point de depart est le plus proche, teleportation AU NIVEAU du coffre, attente du chargement,
puis recherche de tout objet coffre (identifiant 0xF2014..0xF2016, quelle que soit sa classe).
    python tools/resweep.py [nombre max de phases]"""
import json
import math
import struct
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phase_jump as pj  # noqa: E402
import sweep  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "docs/research/ingame_verified.json"
LOG = Path(__file__).with_name("resweep_report.json")
routes = json.loads((ROOT / "docs/research/routes_full.json").read_text(encoding="utf-8"))["routes"]
SKIP = ("_STG", "Aerial", "Kaiju", "EndRoll", "Battle_Submerge", "_EV", "Boss", "Talk", "Unite", "Hack")


def starts(route):
    key = {"A": "A", "B": "B", "C": "C/D"}[route]
    steps = routes[key]["steps"] if isinstance(routes[key], dict) else routes[key]
    out = []
    for s in steps:
        if s["chapter"] and s.get("start_pos") and not any(x in s["subphase"] for x in SKIP):
            p = s["start_pos"]
            who = (s.get("character") or "2B").split()[0].split("+")[0]
            out.append((s["chapter"], int(s["phase"][1:], 16), s["subphase"], (p["x"], p["y"], p["z"]),
                        who if who in ("2B", "9S", "A2") else "2B"))
    return out


def chest_objects(g):
    base, size = sweep.entity_region(g.m)
    data = g.m.read(base, size)
    a = np.frombuffer(data[:len(data) // 4 * 4], dtype="<u4")
    out = []
    for i in np.where((a >= 0xF2014) & (a <= 0xF2016))[0]:
        off = int(i) * 4 - 0x5B8
        if off < 0 or off % 8:
            continue
        vt = struct.unpack_from("<Q", data, off)[0]
        if g.m.base < vt < g.m.base + 0x2000000:
            out.append((struct.unpack_from("<3f", data, off + 0x50), vt - g.m.base))
    return out


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 99
    ver = json.loads(VER.read_text(encoding="utf-8"))
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    todo = [c for c in db.CHESTS if not c["verified"] and log.get(c["name"], {}).get("result") != "present"
            and len(log.get(c["name"], {}).get("tried", [])) < 2]
    plan = defaultdict(list)
    for c in todo:
        route = c["region"][0]
        tried = set(log.get(c["name"], {}).get("tried", []))
        cands = [s for s in starts(route) if int(s[0][:2]) >= int(c["region"][1:]) and s[2] not in tried]
        if not cands:
            continue
        best = min(cands, key=lambda s: math.dist(s[3], c["pos"]))
        plan[(route, best[4] if route == "C" else {"A": "2B", "B": "9S"}[route], best[1], best[2])].append(c)
    g = sweep.Game()
    for n, ((route, who, phase, sub), chests) in enumerate(sorted(plan.items(), key=lambda kv: -len(kv[1]))):
        if n >= limit:
            break
        pj.set_route(g.m, route, who)
        ok = pj.jump(g.m, phase, sub)
        time.sleep(10)
        for c in chests:
            e = log.setdefault(c["name"], {"tried": []})
            e["tried"].append(sub)
            if ok:
                pos = c["pos"]
                g.goto((pos[0] + 1.0, pos[1] + 0.5, pos[2]), settle=3)
                found = None
                for _ in range(4):
                    g.tp(pos[0] + 1.0, pos[1] + 0.5, pos[2])
                    time.sleep(1.5)
                    near = [(math.dist(p, pos), vt) for p, vt in chest_objects(g) if math.dist(p, pos) < 4]
                    if near:
                        found = min(near)
                        break
                e["result"] = "present" if found else "absent"
                if found:
                    e["vtable"] = hex(found[1])
                    if c["pos"] not in ver["chests_present"]:
                        ver["chests_present"].append(c["pos"])
                    if c["pos"] in ver["chests_not_found"]:
                        ver["chests_not_found"].remove(c["pos"])
            else:
                e["result"] = "jump_failed"
            print(route, sub, c["name"], e["result"], e.get("vtable", ""), flush=True)
            LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
            VER.write_text(json.dumps(ver, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
