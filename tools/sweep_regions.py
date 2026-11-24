"""Balayage de presence des coffres de regions donnees depuis une phase precise.
    python tools/sweep_regions.py <route> <perso> <phase hex> <sous-phase> <region> [region...]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phase_jump as pj  # noqa: E402
import sweep  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402

REPORT = Path(__file__).with_name("campaign_report.json")
route, who, phase, sub, *regions = sys.argv[1:]
rep = json.loads(REPORT.read_text(encoding="utf-8"))
g = sweep.Game()
pj.set_route(g.m, route, who)
print("saut", pj.jump(g.m, int(phase, 16), sub), flush=True)
time.sleep(8)
for c in db.CHESTS:
    if c["region"] not in regions:
        continue
    res = rep.setdefault("regions", {}).setdefault(c["region"], {})
    if res.get(c["name"]) in ("present", "already"):
        continue
    pos = c["pos"]
    g.goto((pos[0], pos[1] + 25, pos[2]), settle=0.5)
    obj = None
    for _ in range(4):
        g.tp(pos[0], pos[1] + 25, pos[2])
        time.sleep(1.2)
        obj = g.chest_at(pos)
        if obj:
            break
    res[c["name"]] = "absent" if obj is None else "present"
    print(c["name"], res[c["name"]], flush=True)
    REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
