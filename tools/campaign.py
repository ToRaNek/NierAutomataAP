"""Campagne de test automatique : visite chaque chapitre d'une route par saut de phase, verifie que le client
valide le chapitre, puis verifie en jeu la presence des coffres et la pose des AP Items de chaque region.

    python tools/campaign.py A [chapitre de depart, ex. 03-02]
Resultats : tools/campaign_report.json (repris d'une execution a l'autre).
"""
import glob
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phase_jump as pj  # noqa: E402
import remote_pad as rp  # noqa: E402
import sweep  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402
from nier_automata.game import ap_items as apit  # noqa: E402

REPORT = Path(__file__).with_name("campaign_report.json")
PHASES = json.loads((Path(__file__).resolve().parent.parent / "docs/research/routes_full.json")
                    .read_text(encoding="utf-8"))["routes"]
SKIP = ("_STG", "Aerial", "Kaiju", "EndRoll", "Battle_Submerge")     # phases de vol / cinematiques longues


def client_chapters():
    files = sorted(glob.glob(os.path.join(os.environ["LOCALAPPDATA"], "NierAutomataAP", "*_1.json")),
                   key=os.path.getmtime)
    return set(json.load(open(files[-1]))["chapters"]) if files else set()


def save(rep):
    REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


def alive():
    try:
        rp.ProcessMemory.attach()
        return True
    except Exception:
        return False


def main():
    route = sys.argv[1]
    start = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else ""
    key = {"A": "A", "B": "B", "C": "C/D"}[route]
    steps = PHASES[key]["steps"] if isinstance(PHASES[key], dict) else PHASES[key]
    first = {}
    for s in steps:
        if s["chapter"] and not any(x in s["subphase"] for x in SKIP):
            first.setdefault(s["chapter"], s)
    rep = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    chapters = [c for c in db.CHAPTERS if c["route"] == route]
    if "--redo" in sys.argv:                       # refaire les sauts et les regions de cette route
        for k in [k for k in rep if k.startswith(route + " ")]:
            del rep[k]
        for d in ("regions", "regions_done"):
            for k in [k for k in rep.get(d, {}) if k.startswith(route)]:
                del rep[d][k]
    for n, ch in enumerate(chapters):
        cid = f"{route} {ch['chapter']}"
        last_of_region = n + 1 == len(chapters) or chapters[n + 1]["region"] != ch["region"]
        swept = rep.get("regions_done", {}).get(ch["region"])
        if ch["chapter"] < start or (rep.get(cid, {}).get("jump") == "ok" and (swept or not last_of_region)):
            continue
        s = first.get(ch["chapter"])
        r = rep.setdefault(cid, {})
        if s is None:
            r["jump"] = "skipped (flight/cutscene only)"
            save(rep)
            continue
        g = sweep.Game()
        try:
            who = (s.get("character") or "2B").split()[0].split("+")[0]
            who = who if who in ("2B", "9S", "A2") else {"A": "2B", "B": "9S", "C": "A2"}[route]
            pj.set_route(g.m, route, {"A": "2B", "B": "9S"}.get(route, who))
            ok = pj.jump(g.m, int(s["phase"][1:], 16), s["subphase"])
        except OSError as ex:
            ok = False
            r["error"] = str(ex)
        r["subphase"] = s["subphase"]
        r["jump"] = "ok" if ok else "failed"
        if not ok:
            save(rep)
            print(cid, "saut rate", pj.state(g.m) if alive() else "JEU FERME", flush=True)
            if not alive():
                return 2
            continue
        time.sleep(14)
        idx = db.CHAPTERS.index(ch)
        r["client_detected"] = idx in client_chapters()
        r["pos"] = [round(v, 1) for v in g.pos()]
        print(cid, s["subphase"], "client:", r["client_detected"], flush=True)
        save(rep)
        last_of_region = n + 1 == len(chapters) or chapters[n + 1]["region"] != ch["region"]
        if not last_of_region:
            continue
        region = ch["region"]
        res = rep.setdefault("regions", {}).setdefault(region, {})
        for c in db.CHESTS:
            if c["region"] != region or c["name"] in res:
                continue
            pos = c["pos"]
            try:
                g.goto((pos[0], pos[1] + 25, pos[2]), settle=0.5)
                obj = None
                for _ in range(4):
                    g.tp(pos[0], pos[1] + 25, pos[2])
                    time.sleep(1.2)
                    obj = g.chest_at(pos)
                    if obj:
                        break
                res[c["name"]] = "absent" if obj is None else ("already" if g.opened(obj) else "present")
            except OSError as ex:
                res[c["name"]] = f"error {ex}"
                if not alive():
                    save(rep)
                    return 2
            save(rep)
        for p in db.PICKUPS:
            if p["region"] != region or p["k"] > 3 or p["name"] in res:
                continue
            pos = p["pos"]
            try:
                g.goto((pos[0], pos[1] + 25, pos[2]), settle=0.5)
                found = False
                for _ in range(6):
                    g.tp(pos[0], pos[1] + 25, pos[2])
                    time.sleep(1.5)
                    if any(math.dist(q, pos) < 6 for q in apit.find_marked_objects(g.m).values()):
                        found = True
                        break
                res[p["name"]] = "spawned" if found else "not_spawned"
            except OSError as ex:
                res[p["name"]] = f"error {ex}"
            save(rep)
        rep.setdefault("regions_done", {})[region] = True
        save(rep)
        vals = list(res.values())
        print("  region", region, {v: vals.count(v) for v in sorted(set(vals))}, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
