"""Parcours complet des routes A, B, C/D, E depuis les donnees du jeu (LECTURE SEULE, jeu non lance).

Usage :
    python tools/routes_full.py [routes|endings|enemies|md|all] [--out docs/research]

- routes  : docs/research/routes_full.json (etapes ordonnees par route, quetes disponibles, points de non-retour,
            objets cles, transitions de phase)
- endings : docs/research/endings_triggers.json (tools/rf_endings.py)
- enemies : docs/research/enemies_by_area.json (tools/rf_enemies.py)
- md      : docs/research/routes_full.md (resume lisible, a partir des 3 JSON)
Les fichiers sont extraits un par un via extract_research.game_file (cache disque), un fichier de phase a la fois.

Sources :
- core/coreph.dat:PhaseInfo.bxm (ordre des phases), phX/pXXX.dat:pXXX_sub.bxm (sous-phases : Name, Comment,
  RoomNo, PlayerPos), core/coregm.dat:ChapterData.cha (debuts de chapitre), QuestChapterData.qch (quetes par
  chapitre), pXXX_hap.z (sauts de phase ; jetons de groupe = crc32(nom de sous-phase)).
- docs/research/quest_rewards.json (genere par tools/resolve_quests.py) : remises / retraits d'objets cles.
- NieRAutomata.exe (tools/xref.py) : verification des references aux objets cles (cles d'acces, cle d'ascenseur).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bxm  # noqa: E402
import cpk  # noqa: E402
import extract_research as er  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "research"
PHASE_FILES = {"p100": "ph1/p100.dat", "p200": "ph2/p200.dat", "p300": "ph3/p300.dat", "p400": "ph4/p400.dat"}
TOKEN_SUBPHASE = 0xF3B97443  # code des jetons de groupe hap : id = crc32(nom de sous-phase)
CHAR_CODE = {1: "2B", 2: "9S", 3: "2B/9S", 4: "A2", 6: "9S+A2 (choice)", 0: None}
QCH_CHAR = {1: "2B", 2: "9S", 3: "A2", 4: "any"}
CHAR_TO_QCH = {"2B": 1, "9S": 2, "A2": 3}
ROUTE_GROUP = {0: "A", 1: "B", 2: "A+B", 3: "C/D"}

# --- zones : mots-cles japonais (commentaire) puis jetons anglais (nom de sous-phase) ----------------------
AREA_JA = [
    ("資源回収ユニット内部", None), ("コピー都市", "Copied City"), ("エイリアンシップ", "Alien Ship"),
    ("ショッピングモール", "Commercial Facility (Shopping Center)"), ("レジスタンスキャンプ", "Resistance Camp"),
    ("レジキャン", "Resistance Camp"), ("パスカルの村", "Pascal's Village"), ("パスカル村", "Pascal's Village"),
    ("ロボット山", "Abandoned Factory"), ("大廃墟都市", "City Ruins"), ("大虚構都市", "City Ruins"),
    ("ハイキョ都市", "City Ruins"), ("廃墟都市", "City Ruins"), ("水没都市", "Flooded City"),
    ("森の城", "Forest Castle / Forest Zone"), ("団地", "Desert Housing Complex"), ("砂漠", "Desert Zone"),
    ("遊園地", "Amusement Park"), ("バンカ", "Bunker"), ("塔", "Tower"), ("ポッド会話", "Pod conversation (no area)"),
    ("最終エンディング", "Credits (Ending E)"), ("ハッキングゲーム", "Hacking space"),
]
AREA_EN = [
    ("Copy_City", "Copied City"), ("Alien_Ship", "Alien Ship"), ("ShopM", "Commercial Facility (Shopping Center)"),
    ("Resistance_Camp", "Resistance Camp"), ("ResiCamp", "Resistance Camp"), ("GotoCamp", "City Ruins"),
    ("Pascal_Village", "Pascal's Village"), ("RobotM", "Abandoned Factory"), ("Robot_Mountain", "Abandoned Factory"),
    ("Ruined_City", "City Ruins"), ("Ruined_Front", "City Ruins"), ("Transfer_device", "City Ruins"),
    ("Submerge_City", "Flooded City"), ("Kaiju", "Flooded City (sea)"), ("Forest_Castle", "Forest Castle / Forest Zone"),
    ("King_of_the_forest", "Forest Castle"), ("Danchi", "Desert Housing Complex"), ("Desert", "Desert Zone"),
    ("Amusement_Park", "Amusement Park"), ("Park", "Amusement Park"), ("unker", "Bunker"), ("uker", "Bunker"),
    ("Banker", "Bunker"), ("Tower", "Tower"), ("Shooting", "Flight unit (shmup)"), ("Pod_Talk", "Pod conversation (no area)"),
    ("POD", "Pod conversation (no area)"), ("TrueEnd", "Credits (Ending E)"), ("Hack_Game", "Hacking space"),
]
SUBAREA_JA = [("資源回収ユニット", "Resource Recovery Unit"), ("地下工場", "underground factory"),
              ("教祖の部屋", "cult leader's room"), ("ボス", "boss area"), ("図書館", "library"),
              ("エレベーター", "elevator"), ("頂上", "summit"), ("格納庫", "hangar"), ("STG", "flight-unit section")]
UNUSED_JA = ("未使用", "削除予定", "※このフェーズから開始せず")


def area_of(name: str, comment: str | None):
    c = comment or ""
    area = src = None
    # mot-cle le plus tot dans le commentaire (format 'lieu_detail'), a egalite le plus long
    def first(t):
        h = sorted((t.find(k), -len(k), k, v) for k, v in AREA_JA if v and k in t)
        return (h[0][2], h[0][3]) if h else (None, None)

    k, area = first(c)
    if area:
        src = f"comment:{k}"
        if "から" in c:  # 'XからYへ' = trajet de X vers Y
            k2, a2 = first(c.split("から", 1)[1])
            if a2 and a2 != area:
                area, src = f"{area} -> {a2}", f"comment:{k}から{k2}"
    if area is None:
        for k, v in AREA_EN:
            if k in name:
                area, src = v, f"name:{k}"
                break
    sub = [v for k, v in SUBAREA_JA if k in c]
    return area, sub, src


SUB_RE = re.compile(r"^(?P<num>\d+(?:_\d+)*)_(?P<route>AB|CD|A|B|C|D)_(?P<rest>.+)$")


def parse_name(name: str):
    m = SUB_RE.match(name)
    if not m:
        return None, None
    return m.group("route"), m.group("rest")


def char_from_name(name: str, comment: str | None):
    c = comment or ""
    if "パスカル操作" in c:
        return "Pascal"
    for tok in ("2B", "9S", "A2"):  # suffixe d'abord (277_CD_Tower_2Bbtl_9S = 9S)
        if name.endswith(tok):
            return tok
    for tok in ("_2B", "_9S", "_A2"):
        if tok in name:
            return tok[1:]
    if c.startswith("A2-") or "（A2操作）" in c:
        return "A2"
    if c.startswith("9S-"):
        return "9S"
    return None


def pos_of(s):
    if not s:
        return None
    try:
        v = [float(x) for x in s.split()]
    except ValueError:
        return None
    if not v or all(abs(x) < 1e-6 for x in v[:3]):
        return None
    return {"x": v[0], "y": v[1], "z": v[2], "rot_y": v[3] if len(v) > 3 else None}


# --- hap : sauts de phase avec sous-phases sources (jetons de groupe) ------------------------------------

def hap_phase_jumps(z: bytes, crc_to_sub: dict[int, str]):
    root = er.hap_xml(z)
    groups = {}
    for g in root.iter("group"):
        gid = g.findtext("id")
        if gid is None:
            continue
        toks = []
        for v in g.findall("tokens/value"):
            try:
                if int(v.findtext("code"), 16) == TOKEN_SUBPHASE:
                    toks.append(int(v.findtext("id"), 16))
            except (TypeError, ValueError):
                pass
        groups[gid] = (g.findtext("name"), g.findtext("parent"), toks)

    def subs_of(gid):
        seen, out, chain = set(), [], []
        while gid in groups and gid not in seen:
            seen.add(gid)
            name, parent, toks = groups[gid]
            chain.append(name)
            if toks and not out:  # le groupe le plus proche portant des jetons decide
                out = [crc_to_sub.get(t, f"crc32:{t:08x}") for t in toks]
            gid = parent
        return out, chain

    jumps = []
    for hap in root.iter("hap"):
        hname, gid = hap.findtext("name"), hap.findtext("group")
        for act in hap.iter("action"):
            ph, sp = act.find("phase"), act.find("subPhase")
            if ph is None or sp is None:
                continue
            src, chain = subs_of(gid)
            jumps.append({"hap": hname, "action": act.findtext("name"), "to_phase": f"p{int(ph.text, 16):03x}"
                          if ph.text and ph.text.startswith("0x") else ph.text, "to_subphase": sp.text,
                          "from_subphases": src, "group_chain_ja": chain[:4]})
    return jumps


# --- construction ------------------------------------------------------------------------------------------

def load_base():
    ctx = er.Ctx()
    pi, _ = bxm.parse(cpk.dat_files(er.game_file("core/coreph.dat"))["PhaseInfo.bxm"])
    phase_order = [ph["attrs"].get("name") for ph in er.kids(er.kids(pi, "InfoList")[0], "Phase")]
    chapters = []
    for c in er.cha(ctx.gm["ChapterData.cha"]):
        key = f"CHAPTER_NAME_{c['chapter']:02d}_{c['sub']:02d}"
        c["english_name"] = ctx.t(key + (f"_{c['variant']}" if c["variant"] else "")) or ctx.t(key) \
            or ctx.t(key + "_0")
        c["english_chapter"] = ctx.t(f"CHAPTER_NAME_{c['chapter']:02d}_00")
        c["label"] = f"{c['chapter']:02d}-{c['sub']:02d}"
        chapters.append(c)
    qch = er.qch(ctx.gm["QuestChapterData.qch"])
    qnames = {}
    for q, _ in qch:
        qid = f"q{q:03d}"
        qnames[qid] = ctx.t(f"PAUSE_QUEST_NAME_{qid}_US") or ctx.t(f"PAUSE_QUEST_NAME_{qid}")
    return ctx, phase_order, chapters, qch, qnames


def read_phase(stem: str, crc_to_sub: dict):
    d = cpk.dat_files(er.game_file(PHASE_FILES[stem]))
    rows = []
    sub = d.get(f"{stem}_sub.bxm")
    if sub:
        tree, _ = bxm.parse(sub)
        for i, sp in enumerate(er.kids(tree, "SubPhase")):
            r = {"order": i}
            for c in sp["children"]:
                r[c["name"]] = c["value"]
            rows.append(r)
    for r in rows:
        crc_to_sub[zlib.crc32(r["Name"].encode())] = f"{stem}/{r['Name']}"
    z = d.get(f"{stem}_hap.z")
    jumps = hap_phase_jumps(z, crc_to_sub) if z and len(z) > 100 else []
    del d
    return rows, jumps


def build_routes(out_dir: Path):
    ctx, phase_order, chapters, qch, qnames = load_base()
    crc_to_sub: dict[int, str] = {}
    phases, jumps = {}, {}
    for stem in PHASE_FILES:  # sous-phases d'abord (jetons), puis sauts
        d = cpk.dat_files(er.game_file(PHASE_FILES[stem]))
        tree, _ = bxm.parse(d[f"{stem}_sub.bxm"])
        for sp in er.kids(tree, "SubPhase"):
            nm = next(c["value"] for c in sp["children"] if c["name"] == "Name")
            crc_to_sub[zlib.crc32(nm.encode())] = f"{stem}/{nm}"
        del d
    for stem in PHASE_FILES:
        phases[stem], jumps[stem] = read_phase(stem, crc_to_sub)
    for f in sorted(n for n in er.all_names() if n.startswith("phf/") and n.endswith(".dat")):
        stem = f.split("/")[1][:-4]
        z = er.dat_member(f, f"{stem}_hap.z")
        if z and len(z) > 100:
            PHASE_FILES.setdefault(stem, f)
            jumps[stem] = hap_phase_jumps(z, crc_to_sub)

    ch_by_sub = {}
    for c in chapters:
        ch_by_sub.setdefault((c["phase"], c["subphase"]), []).append(c)
    qavail = {}  # indice de chapitre -> {quete: valeur}
    for q, vals in qch:
        for i, v in enumerate(vals):
            if v:
                qavail.setdefault(i, {})[f"q{q:03d}"] = v

    # 1) etapes brutes
    raw = []
    excluded = []
    for stem in ("p100", "p200", "p300"):
        for r in phases[stem]:
            name, com = r["Name"], r.get("Comment")
            route, rest = parse_name(name)
            reason = None
            if route is None:
                reason = "name not in NN_route_* form (test/debug)"
            elif "TEST" in name or (com or "").startswith("e3_") or "PlayGo" in name:
                reason = "test / E3 demo / PlayGo"
            elif any(k in (com or "") for k in UNUSED_JA):
                reason = "comment says unused / to be deleted / do not start here"
            area, sub, asrc = area_of(name, com)
            st = {"phase": stem, "order": r["order"], "subphase": name, "comment_ja": com,
                  "route_token": route, "room": r.get("RoomNo"), "start_pos": pos_of(r.get("PlayerPos")),
                  "is_restart_point": r.get("isRestartPoint") == "YES", "area": area, "sub_area": sub,
                  "area_source": asrc, "character_from_name": char_from_name(name, com),
                  "chapter_starts": [dict(index=c["index"], label=c["label"], variant=c["variant"],
                                          route_group=ROUTE_GROUP.get(c["route_group"]),
                                          character=CHAR_CODE.get(c["character"]), english_name=c["english_name"],
                                          english_chapter=c["english_chapter"])
                                     for c in ch_by_sub.get((stem, name), [])]}
            if reason and not st["chapter_starts"]:
                st["excluded_reason"] = reason
                excluded.append(st)
            else:
                if reason:
                    st["note"] = f"flagged ({reason}) but is a Chapter Select entry"
                raw.append(st)

    # zones des salles g* : zone majoritaire des sous-phases de la salle
    room_area = {}
    for st in raw:
        if st["room"] and st["room"].startswith("g") and st["area"]:
            room_area.setdefault(st["room"], []).append(st["area"])
    room_area = {k: max(set(v), key=v.count) for k, v in room_area.items()}

    def route_steps(tokens, groups, phase_set, other_only):
        steps = [s for s in raw if s["route_token"] in tokens and s["phase"] in phase_set
                 and other_only not in (s["comment_ja"] or "")]  # 'Bルート専用' hors route A, etc.
        cur = None
        out = []
        for s in steps:
            starts = [c for c in s["chapter_starts"] if c["route_group"] in groups]
            s2 = {k: v for k, v in s.items() if k != "chapter_starts"}
            if starts:
                cur = starts[0]
                s2["chapter_start"] = True
                s2["chapter_assignment"] = "chapter-select entry (ChapterData.cha)"
            else:
                s2["chapter_start"] = False
                s2["chapter_assignment"] = "inferred: previous chapter-select entry in file order"
            s2["chapter"] = cur
            out.append(s2)
        return out

    def finish(steps, route):
        res = []
        for s in steps:
            c = s.get("chapter")
            who = s["character_from_name"]
            if route == "A":
                who = who if who in ("2B",) else "2B"
            elif route == "B":
                who = "9S" if who in (None, "2B/9S", "9S") else who
            else:
                if who is None and c:
                    who = c["character"]
            if s["area"] is None and s["room"] in room_area:
                s["area"], s["area_source"] = room_area[s["room"]], f"room {s['room']}"
            if (s["area"] or "").startswith("Pod conversation"):
                who = None  # conversation de Pods entre deux chapitres : pas de personnage jouable
            if (s["area"] or "").startswith("Credits"):
                who = "Pods 042/153 (web: credits shmup)"
            qs = []
            if c:
                code = CHAR_TO_QCH.get(who)
                for q, v in sorted(qavail.get(c["index"], {}).items()):
                    if v == 4 or (code and v == code) or (who == "Pascal" and v == 4):
                        qs.append({"quest": q, "name": qnames.get(q), "requires": QCH_CHAR.get(v)})
            res.append({
                "step": len(res) + 1, "phase": s["phase"], "subphase": s["subphase"], "comment_ja": s["comment_ja"],
                "chapter": c["label"] if c else None, "chapter_variant": c["variant"] if c else None,
                "chapter_index": c["index"] if c else None,
                "chapter_name": c["english_name"] if c else None,
                "chapter_title": c["english_chapter"] if c else None,
                "chapter_select_entry": s["chapter_start"], "chapter_assignment": s["chapter_assignment"],
                "character": who, "area": s["area"], "sub_area": s["sub_area"], "area_source": s["area_source"],
                "room": s["room"], "start_pos": s["start_pos"], "is_restart_point": s["is_restart_point"],
                "note": s.get("note"),
                "side_quests_available": qs})
        return res

    A = finish(route_steps({"A", "AB"}, {"A", "A+B"}, {"p100", "p200"}, "Bルート専用"), "A")
    B = finish(route_steps({"B", "AB"}, {"B", "A+B"}, {"p100", "p200"}, "Aルート専用"), "B")
    cd_all = route_steps({"CD", "C", "D"}, {"C/D"}, {"p300"}, "\0")
    true_end = [s for s in cd_all if "TrueEnd" in s["subphase"]]
    cd_all = [s for s in cd_all if "TrueEnd" not in s["subphase"]]
    # C/D : les chapitres A2 (12, 14) et 9S (13, 15-01/02) sont entrelaces dans le fichier : ordre de jeu = ordre
    # des chapitres (blocs en ordre de fichier), avec les deplacements prouves par les sauts de phase.
    by_name = {s["subphase"]: s for s in cd_all}
    for name, (before, chapter_label, why) in CD_MOVES.items():
        if name in by_name:
            s = by_name[name]
            s["sort_key"] = (before, -1)
            s["chapter_assignment"] = why
            s["chapter"] = next((dict(index=c["index"], label=c["label"], variant=c["variant"],
                                      route_group=ROUTE_GROUP.get(c["route_group"]),
                                      character=CHAR_CODE.get(c["character"]), english_name=c["english_name"],
                                      english_chapter=c["english_chapter"])
                                 for c in chapters if c["phase"] == "p300" and c["label"] == chapter_label), None)
    for s in cd_all:
        s.setdefault("sort_key", ((s["chapter"] or {}).get("label", "11-00"), s["order"]))
    cd_all.sort(key=lambda s: s["sort_key"])
    CD = finish(cd_all, "C/D")
    E = finish(true_end, "C/D")
    for s in E:
        s["chapter"] = "after 17-10 (credits)"
        s["chapter_assignment"] = "pf31 credits shmup; reached from 340_C/340_D (see route_boundaries.E)"
    for s in CD:
        nm = s["subphase"]
        s["branch"] = ("final choice: 9S selected -> 340_C_Tower_9Swin -> hap action 'フェーズジャンプ_CEnd' "
                       "(exe 0x863730: SceneState select/9S -> ending_C; web_reference says A2 -> C: disagreement, see endings_triggers.json)"
                       if nm.startswith(("335_CD_Tower_sele9S", "340_C_"))
                       else "final choice: A2 selected -> 340_D_Tower_A2win -> hap action 'フェーズジャンプ_DEnd' "
                            "(exe 0x863730: select/A2 -> ending_D; web says 9S -> D: disagreement)"
                       if nm.startswith(("335_CD_Tower_seleA2", "340_D_", "345_D_"))
                       else None)

    routes = {"A": A, "B": B, "C/D": CD, "E": E}

    # 2) points de non-retour (fenetres de quete) par route
    def pnr(route_steps_, route):
        order = []
        for s in route_steps_:
            if s["chapter_index"] is not None and (not order or order[-1][0] != s["chapter_index"]):
                lab = s["chapter"] + (f"v{s['chapter_variant']}" if s["chapter_variant"] else "")
                order.append((s["chapter_index"], lab, s["character"]))
        if not order:
            return []
        allowed = {"A": {1, 4}, "B": {2, 4}}.get(route, {1, 2, 3, 4})  # C/D : selon le personnage du chapitre
        seen = {}
        for pos, (ci, lab, who) in enumerate(order):
            for q, v in qavail.get(ci, {}).items():
                if v in allowed:
                    seen.setdefault(q, []).append((pos, lab, QCH_CHAR.get(v), who))
        # dernier chapitre ou au moins une quete existe : une quete qui dure jusque-la n'est pas 'perdue'
        last_any = max(p for lst in seen.values() for p, *_ in lst) if seen else -1
        out = []
        for q, lst in sorted(seen.items()):
            first, last = lst[0], lst[-1]
            gaps = [order[p][1] for p in range(first[0], last[0] + 1) if p not in {x[0] for x in lst}]
            ent = {"quest": q, "name": qnames.get(q), "first_chapter": first[1], "last_chapter": last[1],
                   "requires": sorted({x[2] for x in lst}),
                   "lost_after": last[1] if last[0] < last_any else None,
                   "available_until_end_of_route": last[0] >= last_any,
                   "next_chapter_without_it": order[last[0] + 1][1] if last[0] < len(order) - 1 else None,
                   "chapters_in_window_where_absent": sorted(set(gaps))}
            out.append(ent)
        return out

    points = {r: [p for p in pnr(st, r) if p["lost_after"]] for r, st in routes.items() if r != "E"}

    # 3) transitions de phase (hap) avec sous-phases sources
    trans = []
    for stem, js in jumps.items():
        for j in js:
            trans.append(dict(file=PHASE_FILES[stem], **j))
    boundaries = route_boundaries(trans)

    data = {
        "_source": "tools/routes_full.py (PhaseInfo.bxm, pXXX_sub.bxm, ChapterData.cha, QuestChapterData.qch, "
                   "pXXX_hap.z, quest_rewards.json, NieRAutomata.exe)",
        "_notes": [
            "Order of steps = order of SubPhase entries in pXXX_sub.bxm (A/B: p100 then p200; C/D: p300 sorted by "
            "chapter label then file order, since A2/9S chapters interleave in the file).",
            "Route membership = route token of the sub-phase name: A route = A+AB, B route = B+AB, C/D = CD/C/D.",
            "chapter = Chapter Select entry (ChapterData.cha) that starts at this sub-phase, else the previous "
            "entry (same character when the name ends in _2B/_9S/_A2) : 'chapter_assignment' says which.",
            "area: Japanese location keyword of the sub-phase comment, else the English token of the name, else the "
            "majority area of the room (g* rooms are sub-maps; r001 = open world). Unofficial translation.",
            "start_pos = PlayerPos of the sub-phase (x y z [rot_y]); null when 0 0 0 (cutscene / shmup / menu).",
            "side_quests_available = quests present in QuestChapterData.qch for the chapter entry and allowed for the "
            "playable character (1=2B, 2=9S, 3=A2, 4=any). These are Chapter Select windows, not prerequisites.",
            "Hap group tokens (code 0xF3B97443) are crc32(sub-phase name): used for 'from_subphases' of transitions.",
        ],
        "phase_order_PhaseInfo": phase_order,
        "routes": routes,
        "route_boundaries": boundaries,
        "points_of_no_return_quests": points,
        "points_of_no_return_web": WEB_PNR,
        "key_items": key_items(out_dir),
        "phase_transitions": trans,
        "excluded_subphases": [{k: s[k] for k in ("phase", "subphase", "comment_ja", "excluded_reason")}
                               for s in excluded],
        "other_phases": {"p400": [{"subphase": r["Name"], "comment_ja": r.get("Comment"), "room": r.get("RoomNo"),
                                   "start_pos": pos_of(r.get("PlayerPos"))} for r in phases["p400"]],
                         "p400_note": "p400 = DLC 3C3C1D119440927 (Plato / TV under the Amusement Park, room "
                                      "g5ac00) : not part of a route (comments: プラトン起動, テレビにアクセス)."},
    }
    (out_dir / "routes_full.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ecrit", out_dir / "routes_full.json", {k: len(v) for k, v in routes.items()})
    return data


def route_boundaries(trans):
    def find(pred):
        return [{k: t[k] for k in ("file", "hap", "action", "to_phase", "to_subphase", "from_subphases")}
                for t in trans if pred(t)]
    return {
        "A_end": {"desc": "Route A ends after Eve (10-04/10-05) : jump to pf10 EndRoll_A (credits A), then "
                          "SceneStateSystem ending_A",
                  "jumps": find(lambda t: t["to_subphase"] == "EndRoll_A")},
        "B_end_to_CD": {"desc": "Route B ends after Eve : hap ..M1090_S0320_GM_b jumps straight to p300 "
                                "00_CD_Bunker_2B (Route C/D start); ending_B is set in pf10",
                        "jumps": find(lambda t: t["to_phase"] == "p300" and t["file"].endswith("p200.dat"))},
        "CD_character_select": {"desc": "C/D: UI screen talk / phase jumps that pick the A2 or 9S chapter "
                                        "(_A2_1, _A2_2, _9S_1, _9S_2)",
                                "jumps": find(lambda t: re.search(r"_(A2|9S)_[12]$", t["action"] or "") is not None)},
        "CD_final_choice": {"desc": "17-09 final choice (335_CD_Tower_sele9S / seleA2) -> 340_C_Tower_9Swin / "
                                    "340_D_Tower_A2win -> pf10 EndRoll_CD, or pf31 (Ending E shmup)",
                            "jumps": find(lambda t: t["to_subphase"] and (t["to_subphase"].startswith(("335_", "340_"))
                                                                          or t["to_subphase"] == "EndRoll_CD"
                                                                          or t["to_phase"] == "pf31"))},
        "E": {"desc": "pf31 = Ending E credits shmup : clear -> p300 360_CD_TrueEnd_FIN, give up -> pf10 "
                      "BackTitle_CD",
              "jumps": find(lambda t: t["to_subphase"] in ("360_CD_TrueEnd_FIN", "BackTitle_CD"))},
    }


CD_MOVES = {
    # sous-phase : (trier juste avant ce chapitre, chapitre attribue, justification)
    "220_CD_Submerge_City_9S": ("15-03", "15-02", "moved: merge point of the A2 and 9S tracks (hap jumps "
                                "120_95_CD_2_Branch_A2_9S -> 220_CD_Submerge_City_9S -> 220_10 (15-03); "
                                "180_30_CD_2_Pod_Talk -> 220_10)"),
}

WEB_PNR = [
    {"when": "before 05-02", "what": "Improving Communications (q160) : qch window 02-02..05-02 only",
     "source": "web FX + qch"},
    {"when": "Missile Supply / Grun (07-02..07-03)", "what": "Emil's Memories (q330), The Wandering Couple (q500)"
     " progress erased if the mission starts first", "source": "web FX/FD (qch windows end 07-03 / continue)"},
    {"when": "after 11 (Bunker destroyed)", "what": "Bunker shops, quests (11B's Memento q410, Data Analysis Freak"
     " q180/q181) gone; no 'Bunker' sub-phase after 11-05 in p300", "source": "web FD + p300_sub.bxm"},
    {"when": "14-04 (Pascal's Village attacked)", "what": "Pascal's Village quests (q220-q222 windows end 14-03);"
     " Treasure Hunt at the Castle (q440 window ends 14-01)", "source": "qch + web FD"},
    {"when": "15 Soul Box", "what": "Faith weapon (one visit)", "source": "web GP"},
    {"when": "16 (9S fetches the Park Access Key)", "what": "Amusement Park Theater closed", "source": "web FD"},
    {"when": "Emil's Determination completed", "what": "Ending Y lost permanently", "source": "web FD/FX"},
]

KEY_ITEMS = {
    851: "item_uq_filter", 842: "item_uq_pascalReq_3", 820: "item_uq_accessKey_1", 821: "item_uq_accessKey_2",
    822: "item_uq_accessKey_3", 845: "item_uq_mallKey",
}
EXE_KEY_STRINGS = ["item_uq_accessKey_1", "item_uq_accessKey_2", "item_uq_accessKey_3", "item_uq_mallKey",
                   "item_uq_filter", "skill_act_sonar", "isActiveSkillSonar"]


def key_items(out_dir: Path):
    qr_path = out_dir / "quest_rewards.json"
    grants, takes = [], []
    if qr_path.exists():
        qr = json.loads(qr_path.read_text(encoding="utf-8"))
        names = set(KEY_ITEMS.values())
        for f, q in qr["quests"].items():
            for rw in q["rewards"]:
                for it in rw["items"]:
                    if it.get("internal_name") in names:
                        grants.append({"item": it["internal_name"], "name": it["name"], "file": f,
                                       "reward_id": rw["reward_id"], "script_method": rw["called_from"],
                                       "via": "getReWard (QuestRewordData.drp)"})
        for a in qr["add_item_calls"]:
            if a["args"] and a["args"][0] in names:
                cnt = a["args"][1] if len(a["args"]) > 1 else None
                (takes if isinstance(cnt, int) and cnt < 0 else grants).append(
                    {"item": a["args"][0], "count": a["args"][1] if len(a["args"]) > 1 else None, "file": a["file"],
                     "script": a["script"], "script_method": a["method"], "via": "addItem (mruby)"})
    exe = exe_refs()
    tower = tower_units()
    return {
        "grants": grants,
        "consumed_or_checked": takes,
        "checks": [
            {"item": "Fuel Filter (851, item_uq_filter)", "where": "Ch05 Resistance Camp",
             "evidence": "p100 p100_47a5d6eb_scp.bin : pascal_ON_TALK_ev1 -> getReWard 107 (Fuel Filter) ; "
                         "ane_ON_TALK_ev0 -> addItem('item_uq_filter', -1) = handed to Anemone (story step).",
             "confidence": "high (script)", "blocking": "story (main quest delivery; no explicit has-item test found)"},
            {"item": "Rigid Tree Bark (842, item_uq_pascalReq_3) -> Fuel Filter", "where": "Ch14 (A2) Pascal",
             "evidence": "p300 p300_e6cf440a_scp.bin : this_q300_91_itemCheck_a1 addItem(+1) (harvest), method "
                         "'item_uq_pascalReq_3?' tests possession, pascal_ON_TALK_ev2 addItem(-1) + getReWard 107 "
                         "(Fuel Filter). Sub-phase 91_00_CD_2_Pascal_Village_A2_SQ = 'filter material gathering'.",
             "confidence": "high (script)", "blocking": "story 14-01"},
            {"item": "Forest/Ocean/Park Access Keys (820-822)", "where": "Tower (Ch17) main/sub units",
             "evidence": "exe: Bg6001 vtable fn 0x5EA5B0 = has(accessKey_1) or has(_2) or has(_3) ; fn 0x574200 = "
                         "consume one key (0x7CA680) and set a per-key flag ; fn 0x31DCF0 refuses to re-add a key "
                         "whose flag is set. bg6001 is placed by quest/qb20 hap ('塔_メイン/サブユニット' = Tower main/"
                         "sub units) ; qb20 scripts have this_MainAccessKey_OFF / SubAccessKey_ON methods.",
             "tower_unit_placements": tower, "exe_refs": {k: exe.get(k) for k in EXE_KEY_STRINGS[:3]},
             "grants": "p300 getReWard 101 (area_keyget_HIT_a0, Meat Box 13-04), 102 (ev1010_DONE_a0, Soul Box 15), "
                       "103 (auto_5_talk1, God Box 16)",
             "confidence": "medium (vtable owner found by walking back to the RTTI locator)",
             "blocking": "Tower entry (Ch17)"},
            {"item": "Elevator Key (845, item_uq_mallKey)", "where": "City Ruins crater / Emil's hideout elevator",
             "evidence": "q330 (Emil's Memories) 'finish' -> getReWard 224 (Elevator Key). exe fn 0x8344B0 (called "
                         "from 0x8291C0) tests count(item_uq_mallKey) > 0 when [obj+4] in (0x14, 7) and [obj+8] == 0xC "
                         "(object type of the elevator not identified).",
             "exe_refs": exe.get("item_uq_mallKey"), "confidence": "medium (check site found, object not named)",
             "blocking": "optional (Emil's Residence, Emil Heads -> Ending Y chain)"},
            {"item": "A170 Scanner (skill_act_sonar, 2024)", "where": "Route A ~Ch08 (web: main quest Redheads)",
             "evidence": "No grant found in scripts/QuestRewordData. p200 hap '条件コマンド_ソナー会話判定' : condition "
                         "Pl0000.isActiveSkillSonar == 1 inside area 'エリア_ソナーチュートリアル' (198.9,-1.4,561.3) -> "
                         "signal p200_100_sonerTalk (tutorial talk only, not a gate).",
             "exe_refs": exe.get("isActiveSkillSonar"),
             "confidence": "low for the grant (unresolved)", "blocking": "optional (hidden items)"},
        ],
    }


def exe_refs():
    try:
        import xref
    except Exception as e:  # exe absent
        return {"error": str(e)}
    out = {}
    for s in EXE_KEY_STRINGS:
        i = xref.D.find(s.encode() + b"\0")
        if i < 0:
            out[s] = None
            continue
        rva = xref.off2rva(i)
        refs = xref.refs(rva)
        out[s] = {"string_rva": hex(rva),
                  "refs": [{"kind": k, "rva": hex(a), "function": [hex(x) for x in (xref.func_of(a) or ())]}
                           for k, a in refs]}
    return out


def tower_units():
    z = er.dat_member("quest/qb20.dat", "qb20_hap.z")
    if not z:
        return []
    return [{"objId": l["objId"], "position": l["position"], "hap": l["hap"], "action": l["action"]}
            for l in er.xml_layouts(er.hap_xml(z)) if l["objId"] == "bg6001"]


# --- resume lisible ------------------------------------------------------------------------------------

def build_md(out_dir: Path):
    R = json.loads((out_dir / "routes_full.json").read_text(encoding="utf-8"))
    E = _load(out_dir / "endings_triggers.json")
    M = _load(out_dir / "enemies_by_area.json")
    L = ["# NieR:Automata - routes, endings and enemies from game data", "",
         "Generated by `python tools/routes_full.py md` from routes_full.json, endings_triggers.json and "
         "enemies_by_area.json. Static data only (v1.04 Steam files); area names and Japanese translations are "
         "unofficial. See the JSON files for positions and evidence.", ""]
    L += ["## Route boundaries", ""]
    for k, v in R["route_boundaries"].items():
        L.append(f"- **{k}** : {v['desc']}")
        for j in v["jumps"][:6]:
            L.append(f"  - `{j['file']}` hap `{j['hap']}` / `{j['action']}` : from {', '.join(j['from_subphases']) or '?'}"
                     f" -> {j['to_phase']} `{j['to_subphase']}`")
    L.append("")
    for route, steps in R["routes"].items():
        L += [f"## Route {route}", "", "| # | chapter | chapter name | sub-phase | char | area | start pos | side quests |",
              "|---|---|---|---|---|---|---|---|"]
        prev_q = None
        for s in steps:
            p = s["start_pos"]
            ps = f"{p['x']:.0f}, {p['y']:.0f}, {p['z']:.0f}" if p else ""
            qs = [q["quest"] for q in s["side_quests_available"]]
            qtxt = "same" if qs == prev_q else (", ".join(qs) or "-")
            prev_q = qs
            br = f" ({s['branch']})" if s.get("branch") else ""
            L.append(f"| {s['step']} | {s['chapter'] or ''}{'*' if s['chapter_select_entry'] else ''} | "
                     f"{s['chapter_name'] or ''} | `{s['subphase']}`{br} | {s['character'] or ''} | "
                     f"{s['area'] or '?'}{(' / ' + ', '.join(s['sub_area'])) if s['sub_area'] else ''} | {ps} | {qtxt} |")
        L.append("")
        L.append("`*` = Chapter Select entry. 'same' = same quest list as the previous row.")
        L.append("")
    L += ["## Points of no return (quest windows, from QuestChapterData.qch)", ""]
    for route, lst in R["points_of_no_return_quests"].items():
        L.append(f"### Route {route}")
        for p in lst:
            L.append(f"- {p['quest']} {p['name']} ({'/'.join(p['requires'])}) : {p['first_chapter']}..{p['last_chapter']},"
                     f" gone from {p['next_chapter_without_it']}")
        L.append("")
    L += ["Web notes (not from data unless stated):", ""]
    for w in R["points_of_no_return_web"]:
        L.append(f"- {w['when']} : {w['what']} ({w['source']})")
    L += ["", "## Key items and where the game checks them", "", "| item | where | evidence | confidence |",
          "|---|---|---|---|"]
    for c in R["key_items"]["checks"]:
        L.append(f"| {c['item']} | {c['where']} | {c['evidence']} | {c['confidence']} |")
    L.append("")
    if E:
        L += ["## Endings (endings_triggers.json)", "", "| letter | title | trigger | where | joke | confidence |",
              "|---|---|---|---|---|---|"]
        def flat(v):
            if isinstance(v, dict):
                return "; ".join(f"{k}: {flat(x)}" for k, x in v.items() if x not in (None, [], ""))
            if isinstance(v, list):
                return ", ".join(flat(x) for x in v[:8]) + (" ..." if len(v) > 8 else "")
            return "" if v is None else str(v)

        for e in E.get("endings", []):
            trig = e.get("trigger_en_unofficial") or e.get("trigger_en") or ""
            L.append(f"| {e.get('letter')} | {e.get('title') or ''} | {flat(trig).replace('|', '/')} | "
                     f"{flat(e.get('where')).replace('|', '/')[:300]} | {e.get('is_joke')} | {e.get('confidence')} |")
        L.append("")
    if M:
        L += ["## Enemies and unit data (enemies_by_area.json)", "",
              f"Coverage: {json.dumps(M.get('coverage'), ensure_ascii=False)[:600]}", "",
              "| area | placements | unit data obtainable there (EmList SaveID -> Intel name) |", "|---|---|---|"]
        for area, v in M.get("by_area", {}).items():
            names = sorted({u["name"] for u in v.get("unit_data", []) if u.get("name")})
            L.append(f"| {area} | {v.get('placements')} | {len(names)}: {', '.join(names)} |")
        L += ["", "Unit data with no placement found in hap/grp data (script / hacking / STG / world spawns):", ""]
        L.append(", ".join(f"{r['SaveID']} {r['name']}" for r in M.get("records_without_placement", [])))
        L.append("")
    (out_dir / "routes_full.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("ecrit", out_dir / "routes_full.md")


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="all", choices=["routes", "endings", "enemies", "md", "all"])
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.what in ("routes", "all"):
        build_routes(out)
    if a.what in ("endings", "all"):
        import rf_endings
        rf_endings.build(out)
    if a.what in ("enemies", "all"):
        import rf_enemies
        rf_enemies.write(out)  # (build seul n'ecrivait pas enemies_by_area.json)
    if a.what in ("md", "all"):
        build_md(out)


if __name__ == "__main__":
    main()
