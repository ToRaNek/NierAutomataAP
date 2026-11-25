"""Construit nier_automata/data/world_data.json a partir de docs/research (voir data_formats.md).

Contenu : chapitres de toutes les routes (story checks), coffres nommes par lieu, points de collecte retenus
pour les AP Items, points d'acces, quetes annexes - chacun avec sa region logique ("A02", "B05", "C13"...),
les capacites requises et un drapeau "excluded" (ratable / incertain : jamais d'objet important).

Les identifiants sont stables tant que la recherche ne change pas (tri deterministe).
"""
from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "docs" / "research"
OUT = ROOT / "nier_automata" / "data" / "world_data.json"

# zone officielle -> (route minimale, chapitre majeur, ratable)
AREAS = {
    "The Bunker": ("A", 1, True),            # detruit a partir du chapitre 12
    "City Ruins": ("A", 2, False), "Resistance Camp": ("A", 2, False),
    "Desert Zone": ("A", 3, False), "Desert Zone: Border Area": ("A", 3, False),
    "Desert Zone: Sand Cave": ("A", 3, False), "Desert Zone: Housing Complex": ("A", 3, False),
    "Desert Zone: Pit Hollow": ("A", 3, False),
    "Amusement Park: Attraction Square": ("A", 4, False), "Amusement Park: Main Square": ("A", 4, False),
    "Amusement Park: Theater": ("A", 4, False), "Amusement Park: Under the Theater": ("A", 4, False),
    "Pascal's Village": ("A", 5, True),       # detruit au chapitre 14
    "City Ruins: Deep Cave": ("A", 5, False),
    "City Ruins: Shopping Center": ("A", 6, False),
    "City Ruins: Emil's Residence": ("A", 7, True),   # demande la quete Emil's Memories
    "Forest Zone": ("A", 6, False), "Forest Castle: Lower Castle": ("A", 6, False),
    "Forest Castle: Upper Castle": ("A", 6, False),
    "Flooded City": ("A", 7, False), "Copied City": ("A", 8, False),
    "Abandoned Factory": ("A", 9, False),
    # sous-sol de l'usine : fenetre d'acces libre tres courte dans l'histoire (avis d'un joueur experimente)
    "Abandoned Factory: His Grace's Room": ("A", 9, True),
    "Abandoned Factory: Underground Area": ("A", 9, True),
    "Forest Zone: Meat Box": ("C", 13, True), "Flooded City: Soul Box": ("C", 15, True),
    "Amusement Park: God Box": ("C", 16, True),
    "The Tower: Lower Section": ("C", 17, True), "The Tower: Upper Section": ("C", 17, True),
}
# premier chapitre C/D ou une zone de la route A redevient accessible
AREA_C_MAJOR = {1: 11, 2: 11, 3: 12, 4: 16, 5: 14, 6: 13, 7: 15, 8: 15, 9: 14}
REGIONS = [f"A{n:02d}" for n in range(1, 11)] + [f"B{n:02d}" for n in range(1, 11)] + [f"C{n:02d}" for n in range(11, 18)]
# niveau conseille par region (courbe des concepteurs, difficulty.md)
REGION_LEVEL = dict(zip(REGIONS, [1, 3, 7, 10, 15, 19, 22, 24, 26, 28,
                                  30, 30, 33, 33, 37, 37, 40, 40, 45, 45,
                                  47, 47, 48, 48, 49, 50, 50]))
AP_NAMES_REGION = {  # points d'acces : code -> region
    "ft_RC": "A02", "ft_CC": "A02", "ft_CRb": "A02", "ft_CS": "A02",
    "ft_DC": "A03", "ft_DI": "A03", "ft_DO": "A03", "ft_DD": "A03",
    "ft_AP": "A04", "ft_PV": "A05", "ft_AS": "A05",
    "ft_FC": "A06", "ft_FC2": "A06", "ft_FC3": "A06", "ft_SC": "A07",
    "ft_RME": "A09", "ft_RMI2": "A09", "ft_RMI": "A09",
}
HARD_QUESTS = {"q900", "q103", "q104"}   # tres longues : jamais d'objet important
# ratables d'apres un joueur experimente (document du 2026-11-24) : jamais d'objet important
MISSABLE_QUESTS = {"q500", "q720", "q240"}
PICKUPS_PER_AREA = 8
PICKUP_MIN_DIST = 30.0


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def region_of(area_label, locked=False, routes=()):
    route, major, missable = AREAS[area_label]
    if routes and "A" not in routes:
        if "B" in routes:
            route = max(route, "B")
        else:
            route, major = "C", (major if route == "C" else AREA_C_MAJOR[major])
    if locked and route == "A":
        route = "B"                           # coffres verrouilles : piratage par 9S
    return f"{route}{major:02d}", missable


# zones du desert que beaucoup de joueurs ne trouvent jamais (avis d'un joueur experimente) : (x, z, rayon).
# Le champ petrolifere est repere par son point d'acces ; l'oasis (un trou dans la tempete de sable, un seul
# coffre) n'a pas de nom dans les fichiers : les deux groupes isoles au bord du desert sont traites pareil.
HIDDEN_SPOTS = [(-892.0, -74.0, 150.0), (-1540.0, -600.0, 90.0), (-720.0, -1110.0, 60.0)]


def hidden_spot(pos) -> bool:
    return any(math.hypot(pos[0] - x, pos[2] - z) < r for x, z, r in HIDDEN_SPOTS)


def refine(region, label, c):
    """Corrections verifiees en jeu (tools/sweep.py) : la zone "City Ruins" couvre aussi la ville d'apres
    l'effondrement (st2/r200, chapitre 05), les egouts et les grottes, pas accessibles au chapitre 02."""
    if label != "City Ruins" or region[0] == "C":
        return region
    hap, major = c.get("hap", ""), int(region[1:])
    if "下水道_水没都市" in hap:              # egouts vers la cite engloutie
        major = max(major, 7)
    elif "下水道_遊園地" in hap:              # egouts vers le parc d'attractions
        major = max(major, 4)
    elif c["file"].startswith("st2/r200") or c["position"][1] < -20:
        major = max(major, 5)
    return f"{region[0]}{major:02d}"


def reach_index():
    out = {}
    for key, v in load("reachability.json")["locations"].items():
        _, file, member, eid = key.split(":")
        out[(file, eid)] = v
    return out


def build_chapters(routes):
    chapters = []
    for route, key in (("A", "A"), ("B", "B"), ("C", "C/D")):
        by = OrderedDict()
        last = None
        steps = routes[key]["steps"] if isinstance(routes[key], dict) else routes[key]
        for s in steps:
            ch = s["chapter"] or last
            if ch is None:
                ch = "11-01"
            last = ch
            e = by.setdefault(ch, {"route": route, "chapter": ch, "title": s.get("chapter_name") or "",
                                   "subphases": [], "character": s.get("character") or ""})
            if not e["title"] and s.get("chapter_name"):
                e["title"] = s["chapter_name"]
            if s["subphase"] not in e["subphases"]:
                e["subphases"].append(s["subphase"])
                e.setdefault("phase_ids", []).append(int(s["phase"][1:], 16))
        for ch, e in by.items():
            e["region"] = f"{route}{int(ch[:2]):02d}"
            e["name"] = f"Story {route if route != 'C' else 'C/D'} {ch}: {e['title']}"
            chapters.append(e)
    return chapters


def spread(points, k, min_dist, anchor):
    """Echantillonnage du plus eloigne : le 1er est le plus proche de l'ancre, puis on maximise l'ecart."""
    if not points:
        return []
    rest = sorted(points, key=lambda p: (math.dist(p["pos"], anchor), p["pos"]))
    chosen = [rest.pop(0)]
    while rest and len(chosen) < k:
        best = max(rest, key=lambda p: (min(math.dist(p["pos"], c["pos"]) for c in chosen), p["pos"]))
        if min(math.dist(best["pos"], c["pos"]) for c in chosen) < min_dist:
            break
        chosen.append(best)
        rest.remove(best)
    return chosen


def main():
    world = load("world_positions.json")
    reach = reach_index()
    routes = load("routes_full.json")["routes"]
    data = {"version": 1, "regions": REGIONS, "region_level": REGION_LEVEL}
    data["chapters"] = build_chapters(routes)

    # --- coffres
    chests = []
    skipped = defaultdict(int)
    for c in world["chests"]:
        label = c["area"].get("label")
        if label not in AREAS:
            skipped["zone hors liste (DLC...)"] += 1
            continue
        if c["context"].get("kind") in ("quest", "phase"):
            skipped["coffre de quete/phase"] += 1
            continue
        if c["objId"].startswith("bg08"):
            # socle d'arme (pas un coffre) : l'arme ramassee passe par les checks "Weapon Found" (vu en jeu)
            skipped["socle d'arme"] += 1
            continue
        if not c["box"].get("contents"):
            # sans contenu : doublon d'un coffre voisin ou caisse de quete (verifie en jeu : absents)
            skipped["sans contenu (doublon / caisse de quete)"] += 1
            continue
        if any(st.startswith(("q65", "NOT q65")) and "NOT" not in st for st in c["conditions"].get("scene_states", [])):
            skipped["caisse de la quete Sorting Trouble"] += 1
            continue
        if any(math.dist(c["position"], o["pos"]) < 1.5 for o in chests):
            skipped["doublon au meme endroit"] += 1
            continue
        locked = c["objId"] == "ba2016"
        region, missable = region_of(label, locked, c["conditions"].get("routes") or ())
        region = refine(region, label, c)
        groups = " ".join(c["conditions"].get("group_chain") or [])
        states = [x for x in c["conditions"].get("scene_states", []) if not x.startswith("NOT")]
        # coffre qui n'existe qu'apres / pendant une quete annexe (verifie en jeu : absent sinon)
        quest_gated = ("クリア後" in groups or "で有効" in groups or any(x[:1] == "q" and x[1:4].isdigit() for x in states))
        # ville d'avant le cratere (st1/r100, phase p100) : le sol disparait au chapitre 5
        pre_crater = c["file"] == "st1/r100.dat"
        # les 2 coffres cote a cote juste avant le pont de l'usine : faciles a rater (avis d'un joueur experimente ;
        # identification par leur position, a confirmer)
        before_bridge = label == "Abandoned Factory" and abs(c["position"][0] + 490) < 2 and abs(c["position"][2] - 317) < 2
        if "sub221" in groups:                     # quete d'A2 au Village de Pascal (route C/D)
            region = "C14"
        rc = reach.get((c["file"], c["entity_id"]), {})
        needs = rc.get("needs")
        unknown = not isinstance(needs, list)
        chests.append({
            "area": label, "pos": [round(v, 2) for v in c["position"]], "region": region,
            "needs": [] if unknown else needs, "locked": locked,
            "excluded": bool(missable or unknown or quest_gated or pre_crater or before_bridge or hidden_spot(c["position"])
                             or c["area"].get("confidence") == "low"),
            "pre_crater": pre_crater,
            "quest_gated": bool(quest_gated),
            "contents": [it["id"] for it in c["box"].get("contents", [])][:4],
        })
    # presence constatee en jeu : un coffre non retrouve ne recoit jamais d'objet important
    seen = {tuple(p) for p in load("ingame_verified.json")["chests_present"]}
    for c in chests:
        c["verified"] = tuple(c["pos"]) in seen
        c["excluded"] = bool(c["excluded"] or not c["verified"])
    chests.sort(key=lambda c: (c["area"], c["pos"][0], c["pos"][2], c["pos"][1]))
    n = defaultdict(int)
    for c in chests:
        n[c["area"]] += 1
        c["name"] = f"Chest: {c['area']} #{n[c['area']]}"
    data["chests"] = chests

    # --- points d'acces
    aps = []
    anchors = {}
    for a in load("access_points_resolved.json")["access_points"]:
        code = a["code"]
        if not a.get("is_access_point") or a.get("always_active") or code not in AP_NAMES_REGION:
            continue
        ents = a.get("placed_entities") or []
        if not ents:
            continue
        pos = [round(v, 2) for v in ents[0]["position"]]
        aps.append({"code": code, "name": f"Access Point: {a['english_name']}", "region": AP_NAMES_REGION[code],
                    "bit": a["activation_bit"], "pos": pos,
                    # sous-sol de l'usine : fenetre d'acces courte (avis d'un joueur experimente)
                    "excluded": a["english_name"] in ("Factory: Hangar", "Factory: Furnace")})
        anchors[code] = pos
    data["access_points"] = aps

    # --- points de collecte retenus pour les AP Items
    per_area = defaultdict(list)
    for p in world["item_pickups"]:
        label = p["area"].get("label")
        if label not in AREAS or p["context"].get("kind") in ("quest", "phase"):
            continue
        if p["conditions"].get("routes") or p["area"].get("confidence") == "low":
            continue
        rc = reach.get((p["file"], p["entity_id"]), {})
        if rc.get("needs") != [] or rc.get("confidence") == "low":
            continue
        if refine(region_of(label)[0], label, p) != region_of(label)[0]:
            continue                               # sous-zone tardive (egouts, grottes) : pas d'AP Item
        per_area[label].append({"pos": [round(v, 2) for v in p["position"]]})
    pickups = []
    not_spawned = {tuple(p) for p in load("ingame_verified.json")["pickups_not_spawned"]}
    for label in sorted(per_area):
        pts = per_area[label]
        near = [a["pos"] for a in aps if AP_NAMES_REGION[a["code"]] == region_of(label)[0]]
        cx = sum(p["pos"][0] for p in pts) / len(pts)
        cy = sum(p["pos"][1] for p in pts) / len(pts)
        cz = sum(p["pos"][2] for p in pts) / len(pts)
        anchor = min(near, key=lambda a: math.dist(a, (cx, cy, cz))) if near else (cx, cy, cz)
        region, missable = region_of(label)
        for k, p in enumerate(spread(pts, PICKUPS_PER_AREA, PICKUP_MIN_DIST, anchor), 1):
            pickups.append({"area": label, "k": k, "name": f"AP Item: {label} #{k}", "pos": p["pos"],
                            "region": region,
                            "excluded": bool(missable or tuple(p["pos"]) in not_spawned or hidden_spot(p["pos"]))})
    data["pickups"] = pickups

    # --- quetes
    quests = []
    avail = load("quest_availability.json")["quests"]
    runtime = load("runtime_state.json")["quests"]
    # etat de chaque quete releve EN JEU a chaque chapitre de la route A (sans l'accepter) :
    # BREAK = le jeu ne la propose plus -> ratable
    seen = load("quest_states_by_chapter.json")
    closed = {q for ch in seen.values() for q, st in ch.items() if st == "BREAK"}
    for qid in sorted(avail):
        q = avail[qid]
        status_index = (runtime.get(qid) or {}).get("status_index")
        if status_index is None:
            continue                              # pas de statut lisible en memoire
        values = set(q.get("values") or [])
        win = {k: v for k, v in (q.get("windows") or {}).items() if k in ("A", "B", "A+B", "C/D")}
        ab = [c[:5] for k in ("A+B", "A", "B") for c in win.get(k, [])]
        cd = [c[:5] for c in win.get("C/D", [])]
        if ab and (values & {1, 4}):
            region = f"A{int(min(ab)[:2]):02d}"
        elif ab and 2 in values:
            region = f"B{int(min(ab)[:2]):02d}"
        elif cd:
            region = f"C{int(min(cd)[:2]):02d}"
        else:
            continue
        last = max(ab) if ab else ""
        missable = (region[0] != "C" and not cd and last < "10-01") or (region[0] == "C" and max(cd) < "17-01")
        quests.append({"id": qid, "name": f"Quest: {q['english_name']}", "region": region,
                       "status_index": status_index,
                       "excluded": bool(missable or qid in HARD_QUESTS or qid in MISSABLE_QUESTS or qid in closed)})
    data["quests"] = quests

    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("ecrit", OUT, f"{OUT.stat().st_size // 1024} Ko")
    print("chapitres", len(data["chapters"]), "| coffres", len(chests), f"(exclus {sum(c['excluded'] for c in chests)},",
          f"verrouilles {sum(c['locked'] for c in chests)}) | AP Items", len(pickups),
          "| points d'acces", len(aps), "| quetes", len(quests), f"(exclues {sum(q['excluded'] for q in quests)})")
    print("coffres ignores :", dict(skipped))


if __name__ == "__main__":
    sys.exit(main())
