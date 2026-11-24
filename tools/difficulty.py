"""Donnees d'equilibrage de difficulte (NieR:Automata v1.04 Steam, LECTURE SEULE du jeu).

Usage :
    python tools/difficulty.py [--out docs/research] [--refresh]

Produit docs/research/difficulty.json + difficulty.md :
- niveau effectif de chaque placement d'ennemi (regle de l'exe, voir data_formats.md 'Difficulte'),
  statistiques par route / chapitre / etape / zone, niveaux des boss ;
- niveau 'Level' de la table StateBind (core_hap.pak) par sous-phase = niveau prevu par les concepteurs ;
- courbe de niveau recommandee ;
- armes (core/core.dat:WeaponParam.csv + WeaponInfoTable.bxm) et ou on les obtient ;
- table du joueur (pl0000ExpInfo.csv : EXP cumulee, PV...) et tables d'ennemis (emXXXXExpInfo.csv : PV, EXP...).

Memoire : un .dat a la fois (cache d'extract_research / world_positions) ; les emXXXX.dat sont extraits du CPK un
par un et seuls leurs *ExpInfo*.csv sont gardes (cache %TEMP%/nier_research_cache/difficulty_expinfo.json).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import world_positions as wp  # noqa: E402
import rf_enemies as rf  # noqa: E402
import logic_gaps_endings as le  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"
EXPINFO_CACHE = er.CACHE / "difficulty_expinfo.json"

TAGS = rf.TAGS | set("""levelRange relativeLevel items rate setRtn type2type type2 spawnInterval amountEachSpawn
cameraType createRange spawnRange respawnTime fitGround hard extream""".split())
ROUTE_TOK = {zlib.crc32(f"Route/{r}".encode()): r for r in "ABCD"}
VARIANTS = ("normal", "hard", "extream")
STEP_ROUTES = ("A", "B", "C/D")

# Boss : donnees d'unite de la categorie 'Special Unit Machines' + androides nommes + Emil (catalogue EmList)
BOSS_EXTRA = {("em1061", 0), ("em1061", 7), ("em1061", 8), ("em1074", 0), ("em1030", 1), ("em1030", 6),
              ("em1040", 6), ("em1020", 0), ("em1010", 0), ("em8800", 1), ("em8801", 0)}
BOSS_WORDS = re.compile(r"ボス|BOSS|Boss")


def _i(v):
    try:
        return int(str(v).strip(), 0)
    except (TypeError, ValueError):
        return None


def _rng(e):
    """Element levelRange -> [min, max] ou None."""
    if e is None:
        return None
    a, b = _i(rf._t(e, "min")), _i(rf._t(e, "max"))
    if a is None and b is None:
        return None
    return [a or 0, b or 0]


# ------------------------------------------------------------------------------------------- placements

def _groups_from_pak(v, H):
    raw = cpk.pak_group_block(v)
    out = {}
    if raw is None:
        return out
    for g in rf.yax_to_et(cpk.yax(raw), H).findall("group"):
        gid = rf._int(rf._t(g, "id"))
        if gid is None:
            continue
        toks = [(rf._int(rf._t(tv, "code")), rf._int(rf._t(tv, "id"))) for tv in g.findall("tokens/value")]
        out[gid] = {"name": rf._t(g, "name"), "parent": rf._int(rf._t(g, "parent")), "tokens": toks,
                    "attr": rf._int(rf._t(g, "attribute")) or 0}
    return out


def _walk_values(e, act, path, out):
    for c in e:
        if c.tag == "action":
            _walk_values(c, c, (), out)
            continue
        oid = c.find("objId")
        if oid is not None and (oid.text or "").startswith("em") and act is not None:
            out.append((act, c, next((p for p in path if p in VARIANTS), None)))
        _walk_values(c, act, path + (c.tag,), out)


def scan_placements(sp_hash):
    """Tous les placements em* des *_hap.pak / *_grp.pak (+ hap.z sans .pak) : champs de niveau bruts."""
    H = {zlib.crc32(t.encode()): t for t in TAGS}
    recs = []
    for n in rf.source_files():
        d = wp.members(n)
        groups, haps = {}, []
        stems = {k[:-len("_hap.pak")] for k in d if k.endswith("_hap.pak")}
        for k, v in d.items():
            if k.endswith("_hap.z") and len(v) > 100 and k[:-len("_hap.z")] not in stems:
                root = er.hap_xml(v)
                for g in root.iter("group"):
                    gid = rf._int(rf._t(g, "id"))
                    if gid is not None and g.find("name") is not None:
                        groups[gid] = {"name": rf._t(g, "name"), "parent": rf._int(rf._t(g, "parent")),
                                       "attr": rf._int(rf._t(g, "attribute")) or 0,
                                       "tokens": [(rf._int(rf._t(t, "code")), rf._int(rf._t(t, "id")))
                                                  for t in g.findall("tokens/value")]}
                haps += [(h, k) for h in root.iter("hap")]
        for k, v in d.items():
            if not k.endswith(".pak"):
                continue
            groups.update(_groups_from_pak(v, H))
            try:
                trees = cpk.pak_yax(v)
            except Exception:
                continue
            for t in trees:
                if t and any(tag == cpk.TAG_OBJ and val.startswith("em") for _, tag, val in t):
                    haps.append((rf.yax_to_et(t, H), k))
        for h, member in haps:
            vals = []
            _walk_values(h, None, (), vals)
            if not vals:
                continue
            chain, subs, routes, g, guard = [], set(), {}, groups.get(rf._int(rf._t(h, "group"))), 0
            while g and guard < 30:
                chain.append(g["name"])
                neg = bool(g["attr"] & 0x10)
                # sous-phases : groupe le plus proche portant des jetons de sous-phase (les ancetres en listent
                # davantage : intersection, pas union ; cf. routes_full 'Jetons de groupe hap')
                gsubs = {sp_hash[i] for c, i in g["tokens"] if c == rf.TOK_SUBPHASE and i in sp_hash}
                if gsubs and not subs:
                    subs = gsubs
                for c, i in g["tokens"]:
                    if c == rf.TOK_QUEST and i in ROUTE_TOK:
                        routes[ROUTE_TOK[i]] = not neg
                g = groups.get(g["parent"])
                guard += 1
            hname = rf._t(h, "name")
            for act, val, variant in vals:
                lv = {}
                for pv in val.findall("param/value"):
                    nm = rf._t(pv, "name")
                    if nm and re.match(r"(?i)lv(_[a-d])?$", nm):
                        lv[nm] = rf._t(pv, "body")
                is_gen = act.find("points") is not None and act.find("items") is not None
                if is_gen:
                    pts = [p for p in (rf._pos(rf._t(x, "point")) for x in act.findall("points/nodes/value")) if p]
                    pos = pts[0] if pts else None
                else:
                    pos = rf._pos(rf._t(val, "location/position"))
                rl = rf._t(act, "relativeLevel")
                recs.append({
                    "file": n, "member": member, "hap": hname, "action": rf._t(act, "name"),
                    "kind": "generator" if is_gen else "layout", "variant": variant,
                    "objId": rf._t(val, "objId"), "setType": rf._int(rf._t(val, "setType")),
                    "position": pos, "lv": lv,
                    "gen_range": _rng(act.find("levelRange")) if is_gen else None,
                    "item_range": _rng(val.find("levelRange")) if is_gen else None,
                    "relative": bool(_i(rl)) if is_gen else False,
                    "spawn_range": _rng(act.find("spawnRange")) if is_gen else None,
                    "subphases": sorted(f"{p}:{s}" for p, s in subs), "route_states": routes,
                    "group_chain": chain,
                    "route_hint": rf.route_hint(chain + [hname, rf._t(act, "name")]),
                })
        del d, haps, groups
    return recs


def level_for(r, route):
    """Niveau effectif (exe v1.04) d'un placement pour une route.
    Generateur 0x3504a0 : relativeLevel -> (plage de l'objet ou niveau du joueur) + plage du generateur ;
    sinon plage de l'objet si non nulle, sinon plage du generateur (tirage uniforme). Puis EmBase 0x65f730 :
    parametre Lv, remplace par Lv_B si Route/B, Lv_C si Route/C, Lv_D si Route/D (jamais mis). Route C/D : Route/B
    reste mise depuis la fin B (pas de StateOff) -> Lv_C, sinon Lv_B, sinon Lv."""
    lo = hi = 0
    mode = "fixed"
    if r["kind"] == "generator":
        ir = r["item_range"] if r["item_range"] and any(r["item_range"]) else None
        gr = r["gen_range"] or [0, 0]
        if r["relative"]:
            if ir:
                lo, hi = ir[0] + gr[0], ir[1] + gr[1]
            else:
                mode, lo, hi = "player_offset", gr[0], gr[1]
        else:
            lo, hi = (ir or gr)
    lv = {k.strip(): _i(v) for k, v in r["lv"].items()}
    pick, src = lv.get("Lv"), "Lv"
    # (noms de parametre sensibles a la casse : 'LV' / 'LV_B' de quelques placements ne sont pas lus)
    if route in ("B", "C/D") and lv.get("Lv_B") is not None:
        pick, src = lv["Lv_B"], "Lv_B"
    if route == "C/D" and lv.get("Lv_C") is not None:
        pick, src = lv["Lv_C"], "Lv_C"
    if pick is not None and pick < 1:
        return {"mode": "unset", "min": 1, "max": 1, "source": f"param {src}={pick} -> ligne 1 de ExpInfo"}
    if pick is not None:
        return {"mode": "fixed", "min": min(pick, 99), "max": min(pick, 99), "source": "param " + src}
    if mode == "player_offset":
        return {"mode": mode, "min": lo, "max": hi, "source": "generator relativeLevel"}
    if lo == 0 and hi == 0:
        return {"mode": "unset", "min": 1, "max": 1,
                "source": "aucun niveau (0) -> ligne 1 de ExpInfo (0x4034d0) ; em0030 en STG = niveau du joueur"}
    return {"mode": "fixed", "min": max(1, lo), "max": min(99, hi),
            "source": "generator item levelRange" if r["kind"] == "generator" and r["item_range"]
            and any(r["item_range"]) else ("generator levelRange" if r["kind"] == "generator" else "?")}


# ------------------------------------------------------------------------------------------- ExpInfo csv

def parse_csv_rows(b, ncols):
    """Lecture comme l'exe 0x40a6d0 : lignes separees par \\r, champs ',' ; champ vide = 0 ; 99 lignes max."""
    rows = []
    for line in b.decode("latin-1").replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        if not line.strip() or len(rows) >= 99:
            continue
        f = line.split(",")
        rows.append([_i(x) or 0 if x.strip() else 0 for x in f[:ncols]] + [0] * max(0, ncols - len(f)))
    return rows


def em_expinfo(refresh=False):
    if EXPINFO_CACHE.exists() and not refresh:
        return json.loads(EXPINFO_CACHE.read_text(encoding="utf8"))
    out = {}
    toc = er._toc_index()
    for n in sorted(x for x in toc if re.match(r"em/em[0-9a-f]{4}\.dat$", x)):
        p, row = toc[n]
        try:
            dat = cpk.dat_files(cpk.extract(p, row))
        except Exception:
            continue
        for k, v in dat.items():
            if re.search(r"(?i)expinfo\d*\.csv$", k):
                out[k] = v.decode("latin-1")
        del dat
    EXPINFO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    EXPINFO_CACHE.write_text(json.dumps(out), encoding="utf8")
    return out


# ------------------------------------------------------------------------------------------- utilitaires

def base_table(oid, em_tables):
    """Table ExpInfo d'un objId : la sienne, sinon celle du modele de base (emXXX0 : em0054 -> em0050, DEDUIT ;
    l'exe prend [em+0x2819c])."""
    for cand in (oid, (oid or "")[:5] + "0"):
        if f"{cand}ExpInfo.csv" in em_tables:
            return f"{cand}ExpInfo.csv"
    return None


def stats(vals):
    if not vals:
        return None
    return {"n": len(vals), "min": min(vals), "avg": round(sum(vals) / len(vals), 1),
            "median": statistics.median(vals), "max": max(vals)}


def designer_level(entry, route):
    """Liste 'Level' de StateBind -> niveau pour la route ('[Route/A] 7', '[Route/B] 33', '30')."""
    if not entry:
        return None
    plain, cond = None, {}
    for s in entry:
        m = re.match(r"\[Route/([A-D])\]\s*(\d+)", s.strip())
        if m:
            cond[m.group(1)] = int(m.group(2))
        elif s.strip().isdigit():
            plain = int(s.strip())
    key = {"A": "A", "B": "B", "C/D": "C"}[route]
    return cond.get(key, plain)


def boss_keys(catalogue):
    keys = {(c["EmID"], c["setType"]) for c in catalogue if c.get("category_name") == "Special Unit Machines"}
    names = {}
    for c in catalogue:
        names.setdefault((c["EmID"], c["setType"]), c.get("unit_data_name"))
    return keys | BOSS_EXTRA, names


# ------------------------------------------------------------------------------------------- construction

def build(out_dir: Path, refresh=False):
    phases = json.load(open(out_dir / "phases.json", encoding="utf8"))
    routes = json.load(open(out_dir / "routes_full.json", encoding="utf8"))
    ebya = json.load(open(out_dir / "enemies_by_area.json", encoding="utf8"))
    items = json.load(open(out_dir / "items.json", encoding="utf8"))
    qnames = {k: v.get("english_name") for k, v in
              json.load(open(out_dir / "quests.json", encoding="utf8"))["quests"].items()}
    sp_hash = {}
    for p in phases["phase_info"]:
        for s in p["subphases"]:
            sp_hash.setdefault(zlib.crc32(s.encode()), (p["phase"], s))

    # jointure vers enemies_by_area (zone, donnee d'unite)
    def pkey(file, member, hap, action, oid, pos):
        return (file, member, hap, action, oid, tuple(pos or ()))
    meta = {}
    for p in ebya["placements"]:
        meta.setdefault(pkey(p["file"], p["member"], p["hap"], p["action"], p["objId"], p["position"]), p)
    bkeys, bnames = boss_keys(ebya["catalogue"])
    cat_ids = {c["EmID"] for c in ebya["catalogue"]}

    recs = scan_placements(sp_hash)
    for r in recs:
        m = meta.get(pkey(r["file"], r["member"], r["hap"], r["action"], r["objId"], r["position"]))
        r["area"] = m["area"] if m else None
        r["unit_data_name"] = m["unit_data_name"] if m else None
        r["quest"] = (m["owner"] if m and m.get("owner_kind") == "quest" else None)
        r["quest_name"] = qnames.get(r["quest"]) if r["quest"] else None
        st = r["setType"] or 0
        # boss : donnee d'unite de boss (catalogue) ; mot 'ボス' seulement pour un objId absent d'EmList
        r["boss"] = (r["objId"], st) in bkeys or (r["objId"] not in cat_ids and bool(
            BOSS_WORDS.search(" ".join([r["hap"] or "", r["action"] or ""] + r["group_chain"]))))
        r["name"] = bnames.get((r["objId"], st)) or r["unit_data_name"] or r["objId"]
        r["levels"] = {rt: level_for(r, rt) for rt in STEP_ROUTES}
    counts = Counter((r["kind"], r["variant"]) for r in recs)

    # StateBind 'Level'
    sb = le.state_bind()
    sb_level = {(ph, sub): rec.get("Level") for ph, rows in sb.items() for sub, rec in rows}

    # placements par sous-phase (variante normale ou sans variante)
    by_sub = defaultdict(list)
    world = []
    quest_idx = defaultdict(list)
    for i, r in enumerate(recs):
        if r["variant"] in ("hard", "extream"):
            continue
        if r["subphases"]:
            for s in r["subphases"]:
                by_sub[s].append(i)
        elif r["quest"]:
            quest_idx[r["quest"]].append(i)
        else:
            world.append(i)

    def route_ok(r, route):
        rs = r["route_states"]
        letters = {"A": "A", "B": "B", "C/D": "C"}[route]
        hint = r.get("route_hint") or []
        if hint and not any(letters in h or (route == "C/D" and "D" in h) for h in hint):
            return False
        if not rs:
            return True
        pos = [k for k, v in rs.items() if v]
        neg = [k for k, v in rs.items() if not v]
        if pos and letters not in pos and not (route == "C/D" and "D" in pos):
            return False
        return letters not in neg

    def summarize(idx, route):
        fixed, unset, rel, bosses = [], 0, [], []
        for i in idx:
            r = recs[i]
            lv = r["levels"][route]
            if lv["mode"] == "unset":
                unset += 1
                if r["boss"]:
                    bosses.append({"name": r["name"], "objId": r["objId"], "setType": r["setType"],
                                   "level": "unset", "source": lv["source"]})
                continue
            if lv["mode"] == "player_offset":
                rel.append([lv["min"], lv["max"]])
                continue
            mid = (lv["min"] + lv["max"]) / 2
            fixed.append(mid)
            if r["boss"]:
                bosses.append({"name": r["name"], "objId": r["objId"], "setType": r["setType"],
                               "level": lv["min"] if lv["min"] == lv["max"] else [lv["min"], lv["max"]],
                               "source": lv["source"]})
        s = stats(fixed) or {}
        if fixed:
            mins = [recs[i]["levels"][route]["min"] for i in idx if recs[i]["levels"][route]["mode"] == "fixed"]
            maxs = [recs[i]["levels"][route]["max"] for i in idx if recs[i]["levels"][route]["mode"] == "fixed"]
            s["min"], s["max"] = min(mins), max(maxs)
        uniq = {}
        for b in bosses:
            uniq.setdefault((b["name"], str(b["level"])), b)
        return {"enemy_levels": s or None, "placements_level_unset": unset,
                "player_relative_offsets": sorted({tuple(x) for x in rel}) or None,
                "bosses": list(uniq.values())}

    route_out = {}
    for route in STEP_ROUTES:
        steps_out, chapters = [], defaultdict(lambda: {"steps": [], "idx": set(), "areas": set()})
        prev_designer = None
        for st in routes["routes"][route]:
            key = f"{st['phase']}:{st['subphase']}"
            idx = [i for i in by_sub.get(key, []) if route_ok(recs[i], route)]
            sm = summarize(idx, route)
            dl = designer_level(sb_level.get((st["phase"], st["subphase"])), route)
            carried = dl is None
            if dl is None:
                dl = prev_designer
            prev_designer = dl
            med = sm["enemy_levels"]["median"] if sm["enemy_levels"] else None
            rec_lv = dl if dl is not None else med
            steps_out.append({
                "step": st["step"], "subphase": key, "chapter": st["chapter"], "chapter_name": st["chapter_name"],
                "area": st["area"], "character": st["character"],
                "designer_level_statebind": dl, "designer_level_carried": carried and dl is not None,
                "enemy_median": med, "recommended_player_level": rec_lv, **sm})
            ch = chapters[st["chapter"] or "?"]
            ch["steps"].append(st["step"])
            ch["idx"].update(idx)
            ch["areas"].add(st["area"])
            ch.setdefault("designer", []).append(dl)
            ch.setdefault("name", st["chapter_name"])
        ch_out = []
        for c, v in chapters.items():
            sm = summarize(sorted(v["idx"]), route)
            ds = [x for x in v["designer"] if x is not None]
            med = sm["enemy_levels"]["median"] if sm["enemy_levels"] else None
            ch_out.append({"chapter": c, "chapter_name": v["name"], "steps": [min(v["steps"]), max(v["steps"])],
                           "areas": sorted(a for a in v["areas"] if a),
                           "designer_level_range": [min(ds), max(ds)] if ds else None,
                           "recommended_player_level": max(ds) if ds else med, **sm})
        # zones du monde (placements sans sous-phase : salles st*, cellules wd, core_hap, quetes)
        area_idx = defaultdict(list)
        for i in world:
            if route_ok(recs[i], route):
                area_idx[recs[i]["area"] or "?"].append(i)
        areas_out = {a: summarize(ix, route) for a, ix in sorted(area_idx.items())}
        q_out = {}
        for q, ix in sorted(quest_idx.items()):
            ix = [i for i in ix if route_ok(recs[i], route)]
            if ix:
                q_out[q] = {"quest_name": recs[ix[0]]["quest_name"], **summarize(ix, route)}
        route_out[route] = {"steps": steps_out, "chapters": ch_out, "world_areas": areas_out, "quests": q_out}

    # ---- tables joueur / ennemis
    pl = cpk.dat_files(er.game_file("pl/pl0000.dat"))
    prow = parse_csv_rows(pl["pl0000ExpInfo.csv"], 6)
    player = [{"level": i + 1, "exp_total": r[0], "hp": r[1], "col2": r[2], "col3": r[3], "col5_ignored": r[5]}
              for i, r in enumerate(prow)]
    del pl
    emx = em_expinfo(refresh)
    em_tables = {}
    for k, txt in sorted(emx.items()):
        rows = parse_csv_rows(txt.encode("latin-1"), 5)
        em_tables[k] = [{"level": i + 1, "hp": r[0], "col1": r[1], "col2": r[2], "exp": r[3], "col4": r[4]}
                        for i, r in enumerate(rows)]
    # EXP d'une 'mort typique' a chaque niveau : mediane des types places
    placed = {base_table(r["objId"], em_tables) for r in recs}
    exp_by_lv = defaultdict(list)
    for k, rows in em_tables.items():
        if k in placed and re.match(r"em[0-9a-f]{4}ExpInfo\.csv$", k):
            for row in rows:
                exp_by_lv[row["level"]].append(row["exp"])
    level_rate = []
    for p in player[:-1]:
        L = p["level"]
        need = player[L]["exp_total"] - p["exp_total"]
        e = statistics.median(exp_by_lv[L]) if exp_by_lv.get(L) else None
        level_rate.append({"level": L, "exp_to_next": need, "median_exp_per_kill_same_level": e,
                           "kills_to_next_level": round(need / e, 1) if e else None})

    # Simulation : EXP des ennemis scriptes (sous-phase, layout, niveau fixe) en suivant les etapes de la route
    def exp_of(oid, lv):
        rows = em_tables.get(base_table(oid, em_tables))
        if not rows:
            return None
        return rows[max(0, min(lv, len(rows)) - 1)]["exp"]

    def level_from_exp(x):
        lv = 1
        for p in player:
            if x >= p["exp_total"]:
                lv = p["level"]
        return lv
    sim = {}
    start_exp = 0
    for route in STEP_ROUTES:
        x = start_exp
        out, seen, miss = [], set(), 0
        for st in route_out[route]["steps"]:
            for i in by_sub.get(st["subphase"], []):
                r = recs[i]
                if i in seen or r["kind"] != "layout" or not route_ok(r, route):
                    continue
                seen.add(i)
                lv = r["levels"][route]
                if lv["mode"] != "fixed":
                    continue
                e = exp_of(r["objId"], lv["min"])
                if e is None:
                    miss += 1
                    continue
                x += e
            out.append({"step": st["step"], "chapter": st["chapter"], "cumulative_exp": x,
                        "player_level": level_from_exp(x)})
        chap_end = {}
        for o in out:
            chap_end[o["chapter"]] = o["player_level"]
        sim[route] = {"start_exp": start_exp, "end_exp": x, "end_level": level_from_exp(x),
                      "level_at_chapter_end": chap_end, "placements_without_expinfo": miss}
        start_exp = x  # A -> B -> C/D (le niveau est conserve ; web_reference.md sec. 2)

    weapons = build_weapons(items, out_dir, routes)

    data = {
        "_source": "tools/difficulty.py (lecture seule : *_hap.pak/*_grp.pak, core_hap.pak StateBind, "
                   "pl0000ExpInfo.csv, emXXXXExpInfo.csv, WeaponParam.csv, WeaponInfoTable.bxm ; exe v1.04)",
        "_notes": NOTES,
        "rules": RULES,
        "placement_counts": {f"{k[0]}/{k[1] or 'none'}": v for k, v in sorted(counts.items(), key=str)},
        "routes": route_out,
        "recommended_curve": {rt: [{"step": s["step"], "chapter": s["chapter"], "subphase": s["subphase"],
                                    "level": s["recommended_player_level"],
                                    "basis": "StateBind Level" if s["designer_level_statebind"] is not None
                                    else ("enemy median" if s["enemy_median"] is not None else None)}
                                   for s in route_out[rt]["steps"]] for rt in STEP_ROUTES},
        "exp_simulation_scripted_kills_only": sim,
        "player_table": player,
        "player_level_rate": level_rate,
        "enemy_tables": em_tables,
        "weapons": weapons,
        "placements": [{k: r[k] for k in ("file", "member", "hap", "action", "kind", "variant", "objId", "setType",
                                          "name", "boss", "position", "area", "quest", "subphases", "route_states", "route_hint", "lv",
                                          "gen_range", "item_range", "relative", "levels")} for r in recs],
    }
    (out_dir / "difficulty.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf8")
    (out_dir / "difficulty.md").write_text(render_md(data), encoding="utf8")
    return data


# ------------------------------------------------------------------------------------------- armes

WTYPE = {0: "small sword", 2: "large sword", 4: "spear", 6: "combat bracers"}
# Sources hors tables de placement (references : data_formats.md / web_reference.md)
WEAPON_EXTRA = {
    "wp0013": [{"kind": "fishing", "note": "etf042 -> arme 1013 (exe 0x629045), table de peche 6 (conduites d'eau), "
                                         "une seule fois (logic_gaps_fishing)", "confidence": "high"}],
    "wp0070": [{"kind": "initial_equipment", "note": "2B (web_reference.md)", "confidence": "web"}],
    "wp0071": [{"kind": "initial_equipment", "note": "9S (web_reference.md)", "confidence": "web"}],
}
# Pas de CORE_WP_NAME pour les armes de collaboration : nom web par coherence de source (DEDUIT)
WEAPON_NAME_GUESS = {"weapon_ff_sword": "Engine Blade", "weapon_dq_sword": "Cypress Stick"}


def web_weapon_sources(out_dir):
    out = {}
    try:
        t = (out_dir / "web_reference.md").read_text(encoding="utf8")
    except OSError:
        return out
    sec = t.split("### Weapon sources", 1)[-1].split("Sources:", 1)[0]
    for line in sec.splitlines():
        f = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(f) == 4 and f[0] not in ("Weapon", "---"):
            for nm in re.split(r",\s*|\s*/\s*", f[0]):
                out[nm] = {"source": f[2], "earliest": f[3]}
    return out


def build_weapons(items, out_dir, routes):
    core = cpk.dat_files(er.game_file("core/core.dat"))
    csv = core["WeaponParam.csv"].decode("latin-1")
    del core
    winfo = {w["ObjID"]: w for w in items["weapons"]}
    shops = json.load(open(out_dir / "shops.json", encoding="utf8"))["shops"]
    wpos = json.load(open(out_dir / "world_positions.json", encoding="utf8"))["unique_items"]
    qrw = json.load(open(out_dir / "quest_rewards.json", encoding="utf8"))["quests"]
    boxrec = json.load(open(out_dir / "chests.json", encoding="utf8"))["boxdata_records"]
    chap = {}
    for rt in STEP_ROUTES:
        for st in routes["routes"][rt]:
            chap.setdefault(f"{st['phase']}/{st['subphase']}", st["chapter"])
            chap.setdefault(f"{st['phase']}:{st['subphase']}", st["chapter"])
    web = web_weapon_sources(out_dir)
    rows = []
    for line in csv.replace("\r", "\n").split("\n"):
        f = line.split(",")
        if len(f) < 34 or not f[0].startswith("wp"):
            continue
        oid = f[0]
        w = winfo.get(oid, {})
        lv = []
        for k in range(4):
            g = [_i(x) or 0 for x in f[2 + 8 * k:10 + 8 * k]]
            lv.append({"level": k + 1, "attack_min": g[0], "attack_max": g[1], "attack_avg": (g[0] + g[1]) / 2,
                       "p2": g[2], "p3": g[3], "p4": g[4], "p5": g[5], "p6": g[6], "p7": g[7]})
        uid = w.get("UniqueID")
        src = []
        for s in shops:
            if s["internal_name"].startswith("shop_TEST"):
                continue
            for it in s["items"]:
                if it["unique_id"] == uid:
                    st = sorted(s["state_names"].get(k, k) for k, v in it["states"].items() if v)
                    src.append({"kind": "shop", "shop": s["internal_name"], "name": s["english_name"], "states": st})
        for b in wpos.get("in_boxes", []):
            if b["item_id"] == uid:
                c = b.get("conditions") or {}
                src.append({"kind": "box", "via": b["via"], "file": b["file"], "position": b["position"],
                            "routes": c.get("routes"), "subphases": c.get("subphases"),
                            "chapters": sorted({chap[s] for s in c.get("subphases") or [] if chap.get(s)}) or None})
        for b in wpos.get("from_scripts_addItem", []):
            if b["item_id"] == uid:
                src.append({"kind": "script_addItem", "file": b["file"], "hap": b.get("hap")})
        for q, qd in qrw.items():
            for rw in qd.get("rewards", []):
                if any(it["id"] == uid for it in rw.get("items", [])):
                    src.append({"kind": "quest_reward", "owner": q, "quest": qd.get("english_name"),
                                "reward_id": rw["reward_id"]})
        for b in boxrec:
            if any(e.get("id") == uid for e in b.get("entries", [])) and not any(
                    x["kind"] == "box" for x in src):
                src.append({"kind": "boxdata_record_only", "box_id": b["box_id"], "group": b["room_or_group"],
                            "note": "enregistrement BoxData sans entite placee trouvee"})
        src += WEAPON_EXTRA.get(oid, [])
        name = w.get("english_name")
        guess = None
        if not name and w.get("internal_name") in WEAPON_NAME_GUESS:
            name = guess = WEAPON_NAME_GUESS[w["internal_name"]]
        rows.append({"name_is_guess": bool(guess),"objId": oid, "unique_id": uid, "internal_name": w.get("internal_name"), "name": name,
                     "type": WTYPE.get(int(oid[2:4]) if oid[2:4].isdigit() else -1),
                     "category_WeaponInfoTable": w.get("Category"), "series_col1": _i(f[1]), "levels": lv,
                     "sources_data": src, "source_web": web.get(name or "")})
    # indice de puissance : attaque moyenne / mediane du type (Lv1 et Lv4)
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    for t, rs in by_type.items():
        m1 = statistics.median(r["levels"][0]["attack_avg"] for r in rs)
        m4 = statistics.median(r["levels"][3]["attack_avg"] for r in rs)
        for r in rs:
            r["power_index_lv1"] = round(r["levels"][0]["attack_avg"] / m1, 3)
            r["power_index_lv4"] = round(r["levels"][3]["attack_avg"] / m4, 3)
            pi = r["power_index_lv1"]
            r["tier"] = "high" if pi >= 1.05 else ("low" if pi <= 0.9 else "mid")
    return rows


# ------------------------------------------------------------------------------------------- textes

RULES = {
    "enemy_level_exe": [
        "EmBase init 0x65f730 : niveau = setInfo+0x74 (copie en [em+0x594] par 0x853b60) ; parametre de placement "
        "'Lv' le remplace ; puis 'Lv_B' si SceneState Route/B, 'Lv_C' si Route/C, 'Lv_D' si Route/D (0x65ff6c.."
        "0x660158) ; resultat [em+0x28030].",
        "Generateur 'EnemyGenerator' (0x346990 lit levelRange +0x9c, relativeLevel +0x3d0 ; objets 0x352b60 : "
        "levelRange par objet +0x24) ; niveau 0x3504a0 : relativeLevel -> (plage objet si non nulle, sinon niveau "
        "du joueur [Pl0000+0x14bc] via vfunc 0x2b0) + tirage plage generateur ; sinon plage objet si non nulle, "
        "sinon plage generateur. Tirage LCG uniforme min..max.",
        "Layouts hap (0x3e96c0) : pas de champ niveau ; setInfo+0x74 = 0 par defaut -> sans 'Lv' le niveau vaut 0 "
        "et la ligne de stats est celle du niveau 1 (0x4034d0 : indice = min(niv, nb)-1, borne a 0).",
        "Exception : bit 0x1000 de [0x1029b00] (pose par 0x515460 selon l'etat du joueur, probablement unite de vol) "
        "et objId em0030 : niveau = niveau du joueur, PV / 5 (0x661b2c, 0x661d03).",
        "Parametre 'MaxLv' (0x6619bd) : niveau tire d'une table d'execution (0x1495640) ; aucun placement ne l'utilise.",
        "SetLevel (vtable EmBase slot 104 = 0x631700) borne le niveau a 1..99.",
        "Aucune mise a l'echelle par difficulte trouvee dans ce chemin ; les layouts 'hard'/'extream' des haps "
        "sont separes (comptes dans placement_counts, exclus des statistiques).",
    ],
    "expinfo_csv": [
        "Chargeur 0x40fdc0 : '%sexpinfo%02d.csv' (indice 4 pour em1100 setType 4..6) sinon '%sexpinfo.csv' dans le "
        ".dat de l'objet ; analyseur 0x40a6d0 (99 lignes x 0x1c o, une ligne par niveau).",
        "Joueur (objId 0x1xxxx, mode 2) : col0 -> +0 = EXP cumulee du niveau, col1 -> +4 = PV max (0x436640 -> "
        "+0x85c), col2 -> +8 (utilise dans les calculs de degats : attaque, deduit), col3 -> +0xc ; col4+ ignorees.",
        "Ennemi (0x2xxxx, mode 1) : col0 -> +4 = PV (SetLevel), col1 -> +8, col2 -> +0xc, col3 -> +0x14 = EXP "
        "donnee a la mort (0x574140 : x (1 + bonus de puce 0x10), min 1, vers 0x7c9ef0), col4 -> +0x18 "
        "([em+0x27d54/58], sens non trace).",
        "Le fichier est celui de l'objId de base [em+0x2819c] (variantes sans .dat propre : table de la base).",
    ],
    "statebind_level": "core_hap.pak StateBind : champ 'Level' par sous-phase (ex. '[Route/A] 7', '[Route/B] 33'), "
                       "lu par 0x35b780 comme element de type 7 ; l'applicateur 0x31dcf0 ne traite que les types "
                       "0..6 : consommateur non trouve. Interprete comme niveau prevu du joueur (confiance moyenne).",
    "weapon_param_csv": "core/core.dat:WeaponParam.csv (charge par 0x821fd0) : objId, serie, puis 4 niveaux x 8 champs "
                        "(attaque min, attaque max, p2..p7). Attaque min/max : deduit (progression x1.8/x2.8/x3.8 "
                        "coherente) ; p2..p7 non traces (p2/p3 ressemblent a des longueurs de combo, p7 = valeur "
                        "d'aptitude). WeaponInfoTable.bxm 'Attack' 100..400 = valeurs factices identiques pour toutes.",
}

NOTES = [
    "Confiance : regle de niveau = haute (exe) ; persistance de Route/B en C/D = moyenne (StateOn sans StateOff) ; "
    "zone/route des placements du monde = moyenne ; 'Level' StateBind comme niveau joueur prevu = moyenne.",
    "Statistiques : placements de variante normale (ou sans variante) ; niveau 'unset' et 'player_offset' exclus des "
    "min/moy/max (comptes a part). Un generateur compte une fois (milieu de sa plage).",
    "Routes : A (p100+p200 A), B (p100+p200 B), C/D (p300). La simulation d'EXP enchaine A -> B -> C/D et ne compte que "
    "les ennemis poses (layout) des sous-phases : borne basse (sans generateurs, monde, quetes, puces).",
    "Non lus : ennemis apparus par scripts mruby, ennemis de piratage, STG (em0030 en vol = niveau du joueur).",
    "relativeLevel=1 : 34 objets de generateur. Animaux r100 (ema000/ema010) = joueur +3..5 ; r170 'ファストトラベル"
    "解除敵' = 1 + 1 (plage objet 1..1) ; p300 '敵発生機_汚染ヨルハ' (em1060, 11-xx C/D) = joueur +47..48 selon la "
    "regle lue (donc ~99 apres borne) : a verifier en jeu (confiance faible sur ce cas).",
    "Zones du monde : tous les placements sans sous-phase d'une zone, quels que soient les etats de scene qui les "
    "activent (arenes, apres la Tour...) : enveloppe large ; la mediane est plus representative que le max.",
]


def render_md(d):
    L = ["# Difficulte : niveaux d'ennemis, courbe recommandee, armes, EXP (v1.04)", "",
         "Genere par `python tools/difficulty.py` -> `difficulty.json`. Lecture seule du jeu. Traduction non officielle.",
         "", "## Regles (exe)", ""]
    for x in d["rules"]["enemy_level_exe"]:
        L.append(f"- {x}")
    L += ["", "### Tables ExpInfo", ""] + [f"- {x}" for x in d["rules"]["expinfo_csv"]]
    L += ["", f"- StateBind : {d['rules']['statebind_level']}", f"- Armes : {d['rules']['weapon_param_csv']}", "",
          "## Notes", ""] + [f"- {x}" for x in d["_notes"]]
    L += ["", "Placements lus : " + ", ".join(f"{k} {v}" for k, v in d["placement_counts"].items()), ""]
    for rt in STEP_ROUTES:
        R = d["routes"][rt]
        L += [f"## Route {rt} : par chapitre", "",
              "| Chapitre | Nom | Zones | Niv. prevu (StateBind) | Ennemis min/moy/med/max (n) | Sans niv. | Boss |",
              "|---|---|---|---|---|---|---|"]
        for c in R["chapters"]:
            e = c["enemy_levels"]
            es = f"{e['min']}/{e['avg']}/{e['median']}/{e['max']} ({e['n']})" if e else "-"
            dr = c["designer_level_range"]
            ds = "-" if not dr else (str(dr[0]) if dr[0] == dr[1] else f"{dr[0]}-{dr[1]}")
            bs = ", ".join(f"{b['name']} {b['level']}" for b in c["bosses"][:6]) or "-"
            L.append(f"| {c['chapter']} | {c['chapter_name'] or ''} | {', '.join(c['areas'])} | {ds} | {es} | "
                     f"{c['placements_level_unset']} | {bs} |")
        L += ["", f"### Route {rt} : zones du monde (placements sans sous-phase)", "",
              "| Zone | min/moy/med/max (n) | Relatif au joueur | Sans niv. |", "|---|---|---|---|"]
        for a, s in R["world_areas"].items():
            e = s["enemy_levels"]
            es = f"{e['min']}/{e['avg']}/{e['median']}/{e['max']} ({e['n']})" if e else "-"
            rel = ", ".join(f"+{x[0]}..{x[1]}" for x in (s["player_relative_offsets"] or [])) or "-"
            L.append(f"| {a} | {es} | {rel} | {s['placements_level_unset']} |")
        L += ["", f"### Route {rt} : quetes (placements des fichiers de quete sans sous-phase)", "",
              "| Quete | Nom | min/moy/med/max (n) | Boss |", "|---|---|---|---|"]
        for q, s in R["quests"].items():
            e = s["enemy_levels"]
            es = f"{e['min']}/{e['avg']}/{e['median']}/{e['max']} ({e['n']})" if e else "-"
            bs = ", ".join(f"{b['name']} {b['level']}" for b in s["bosses"][:4]) or "-"
            L.append(f"| {q} | {s['quest_name'] or ''} | {es} | {bs} |")
        L.append("")
    L += ["## Courbe recommandee (niveau du joueur par etape)", "",
          "Niveau = 'Level' de StateBind (prevu par les concepteurs) ; a defaut mediane des ennemis de l'etape.", ""]
    for rt in STEP_ROUTES:
        seq, last = [], None
        for s in d["recommended_curve"][rt]:
            if s["level"] != last:
                seq.append(f"{s['chapter'] or '?'}:{s['level']}")
                last = s["level"]
        L.append(f"- **{rt}** : " + " -> ".join(seq))
    sim = d["exp_simulation_scripted_kills_only"]
    L += ["", "## Simulation d'EXP (ennemis poses des sous-phases seulement, borne basse)", "",
          "| Route | EXP debut -> fin | Niveau fin | Niveau en fin de chapitre |", "|---|---|---|---|"]
    for rt in STEP_ROUTES:
        s = sim[rt]
        ce = ", ".join(f"{k}:{v}" for k, v in s["level_at_chapter_end"].items())
        L.append(f"| {rt} | {s['start_exp']} -> {s['end_exp']} | {s['end_level']} | {ce} |")
    L += ["", "## Joueur (pl0000ExpInfo.csv)", "", "| Niv. | EXP cumulee | PV | col2 | col3 | EXP vers suivant | "
          "EXP/kill med. (meme niv.) | kills |", "|---|---|---|---|---|---|---|---|"]
    rate = {r["level"]: r for r in d["player_level_rate"]}
    for p in d["player_table"]:
        if p["level"] in (1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 99):
            r = rate.get(p["level"], {})
            L.append(f"| {p['level']} | {p['exp_total']} | {p['hp']} | {p['col2']} | {p['col3']} | "
                     f"{r.get('exp_to_next', '-')} | {r.get('median_exp_per_kill_same_level', '-')} | "
                     f"{r.get('kills_to_next_level', '-')} |")
    L += ["", "## Armes (WeaponParam.csv)", "",
          "| Arme | Type | Lv1 atk | Lv4 atk | Indice Lv1 | Tier | Sources (donnees) | Web (plus tot) |",
          "|---|---|---|---|---|---|---|---|"]
    for w in sorted(d["weapons"], key=lambda x: (x["type"] or "", -x["levels"][0]["attack_avg"])):
        a1, a4 = w["levels"][0], w["levels"][3]
        srcs = []
        for s in w["sources_data"]:
            if s["kind"] == "shop":
                srcs.append(f"shop {s['name'] or s['shop']}")
            elif s["kind"] == "box":
                srcs.append(f"box {s['file']}" + (f" ({','.join(s['chapters'])})" if s.get("chapters") else ""))
            elif s["kind"] == "quest_reward":
                srcs.append(f"quest {s['owner']} {s['quest'] or ''}".strip())
            elif s["kind"] == "boxdata_record_only":
                srcs.append(f"BoxData {s['box_id']} (non place)")
            else:
                srcs.append(s["kind"])
        web = w["source_web"]
        L.append(f"| {w['name'] or w['internal_name']} | {w['type']} | {a1['attack_min']}-{a1['attack_max']} | "
                 f"{a4['attack_min']}-{a4['attack_max']} | {w['power_index_lv1']} | {w['tier']} | "
                 f"{'; '.join(sorted(set(srcs))) or '-'} | {(web or {}).get('earliest', '-')} |")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESEARCH))
    ap.add_argument("--refresh", action="store_true", help="re-extraire les ExpInfo des emXXXX.dat")
    a = ap.parse_args()
    d = build(Path(a.out), a.refresh)
    print("placements", len(d["placements"]), "weapons", len(d["weapons"]), "enemy tables", len(d["enemy_tables"]))


if __name__ == "__main__":
    main()
