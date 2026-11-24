"""Lacune 5 : donnees d'unite (Intel > Unit Data, EmList.bxm) sans placement d'ennemi -> ou / comment elles
se debloquent. LECTURE SEULE (CPK + exe), petite RAM (un .dat a la fois, caches extract_research / world_positions).

Usage :
    python tools/logic_gaps_enemies.py [--out FICHIER.json] [--update-enemies]
    (module : run() -> dict ; utilise par tools/logic_gaps.py)

Regles de l'exe v1.04 (RVA, base 0x140000000) - voir docs/research/data_formats.md :
- 0x7F9640 lit une ligne d'EmList (enregistrement 0x34 o, tableau [0xF59238], nombre [0xF59240]) :
  +0x0c SaveID, +0x10 EmID (objId numerique), +0x18 setType, +0x1c masque setFlag (EmList setFlag 0 -> 0x10,
  1 -> 0x10000010, sinon 0), +0x20 QueID (hexa), +0x24 mode (bDie=1,bTalk=0 -> 0 'mort' ; bDie=0,bTalk=1 -> 1
  'dialogue' ; sinon -1 'evenement seulement').
- 0x8257C0(mgr, objId, objId2, setType, setFlag, arg6, evenement) = enregistrement ; PAS d'arret au premier
  enregistrement : toutes les lignes qui correspondent sont debloquees (EmID egal, setType egal, (setFlag & masque)
  == masque ; em0000 setType 2 recoit toujours le bit 0x10 ; em0060/61/90 et em0040 (hors setType 10) ignorent
  setType). Mort (evenement 0) : seulement les lignes de mode 0 ; sont exclus em1030 st6, em5000 st1/st5,
  em6000 st1/st2, emb010, emb041/051/061.
- 0x825780 (appele a la mort par 6 classes d'ennemis, ex. 0x5F2E02) : setType force a 10 si [ennemi+0x2C32C] != 0
  (ecrit a 1 par 0x53FCCD / 0x69646F = etats d'attaque) -> lignes 'EMP Attack Machines'.
- hap::EmListUnlockAction (vtable 0xC445C0, fonction 0x3A04C0, code d'action hap 0xC168700D = crc32 du nom) :
  ObjId / setType / setFlag -> 0x8257C0 en mode evenement (pl1000 : rien si l'etat 'pascal/memorylost').
- 0x8259D0(mgr, numero de quete) appele en fin de quete (0x3F8671) : sprintf('0x%03d') -> lignes QueID egales.
- 0x825AE0 (appele par 0x3F1CA7, changement d'etat de quete) : q400/RUN_1 -> 150 ; RUN_2 -> 150,151 ;
  DONE -> 150,151,152 ; q070/DONE -> QueID 0x070.
- 0x85C160 (saut de phase vers pf10) : EndRoll_A / BackTitle_A -> em5000 setType 5 et 6 ; EndRoll_CD/BackTitle_*
  (codes 2..4) -> em1030 st6 (select/9S) ou em1040 st6 (select/A2), em8002 st0, em8020 st2, em8010 st6.
- 0x825CB0 (dialogue, appele par 0x35776F) : lignes de mode 1.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import rf_endings as rfe  # noqa: E402
import rf_enemies as rfm  # noqa: E402
import world_positions as wp  # noqa: E402
import xref  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"

UNLOCK_CODE = "0xc168700d"
# donnees sans placement dans enemies_by_area.json avant la correction hap.pak de rf_enemies (passe 1)
ORIGINAL_UNPLACED = (3, 9, 10, 35, 36, 46, 47, 48, 52, 53, 72, 73, 77, 81, 107, 108, 109, 110, 114, 117, 118, 124,
                     129, 145, 151, 152, 156, 157, 158, 161)
OBJ_PREFIX = {"pl": 0x1, "em": 0x2, "bg": 0xC}
TOK_SUBPHASE, TOK_STATE = 0xF3B97443, 0x35C92545
EXTRA_TAGS = ("ObjId objId setType setFlag setRtn items points nodes point rate levelRange spawnRange location "
              "position rotation layouts normal hard extream value group name id code param body comment").split()

# preuves dans l'exe : (rva, octets attendus) verifies a chaque execution
EXE_CHECKS = {
    "setFlag_mask_0x10000010": (0x7F9879, bytes.fromhex("c745 9b 10000010".replace(" ", ""))),
    "setFlag_mask_0x10": (0x7F9882, bytes.fromhex("c7459b10000000")),
    "emp_setType_10": (0x825789, bytes.fromhex("41ba0a000000")),
    "endroll_eve_st5": (0x85C8B2, bytes.fromhex("ba00500200")),
    "unlock_q400_150": (0x825B25, bytes.fromhex("ba96000000")),
    "quest_queid_fmt": (0xCE65B4, b"0x%03d\0"),
}


# regle de mort de l'exe : definie dans rf_enemies.py (partagee avec l'extraction des placements)
objid_num, mask_of, mode_of, death_match = rfm.objid_num, rfm.mask_of, rfm.mode_of, rfm.death_match


def _i(v):
    try:
        return int(v, 0)
    except (TypeError, ValueError):
        return None


def event_match(rec, objId, setType, setFlag):
    """Regle de 0x8257C0 en mode evenement (EmListUnlockAction, fin) : pas de filtre de mode ni d'exclusion."""
    if rec["EmID"] != objId:
        return False
    num = objid_num(objId)
    ignore_st = num in (0x20060, 0x20061, 0x20090) or (num == 0x20040 and (setType or 0) != 10)
    if not ignore_st and rec["setType"] != (setType or 0):
        return False
    m = mask_of(rec["setFlag"])
    return not m or ((setFlag or 0) & m) == m


# --------------------------------------------------------------------------------------------- donnees

def logic_files():
    names = er.all_names()
    return sorted(n for n in names if re.match(r"(ph\w|phf|quest|st\d)/[^/]+\.dat$", n) or n == "core/corehap.dat") + \
        sorted(n for n in names if wp.WD_RE.match(n))


def q_state_hashes():
    out = {}
    states = ["RUN_%d" % i for i in range(20)] + ["DONE", "CLR", "FIN", "FAIL", "NONE", "START", "RUN"]
    for q in [f"q{i:03d}" for i in range(1000)] + [f"q{x}{i:02x}" for x in "abcef" for i in range(256)]:
        for st in states:
            out[zlib.crc32(f"{q}/{st}".encode())] = f"{q}/{st}"
    for s in ("Route/A", "Route/B", "Route/C", "Route/D", "PL/2B", "PL/9S", "PL/A2", "select/9S", "select/A2",
              "pascal/memorylost", "Tower_Appear", "Serious_RC"):
        out[zlib.crc32(s.encode())] = s
    return out


def scan(target_ems: set[str], T, SP, QS):
    """Parcourt les .pak (hap.pak = source de verite, grp.pak) de tous les fichiers logiques + cellules wd."""
    unlocks, places, diag = [], [], Counter()
    for n in logic_files():
        try:
            mem = wp.members(n)
        except Exception:
            continue
        groups = {}
        trees = []
        for m, b in mem.items():
            if not m.endswith(".pak"):
                continue
            for g in rfe.group_table(b, T):
                gid = _i(rfe.kv(g, "id"))
                if gid is not None:
                    toks = []
                    tk = rfe.kid(g, "tokens")
                    for v in (tk["k"] if tk else []):
                        if v["t"] == "value":
                            toks.append((_i(rfe.kv(v, "code")), _i(rfe.kv(v, "id"))))
                    groups[gid] = (rfe.kv(g, "name"), _i(rfe.kv(g, "parent")), toks, _i(rfe.kv(g, "attribute")))
            try:
                for t in cpk.pak_yax(b):
                    trees.append((m, t))
            except Exception:
                continue
            if m.endswith("_hap.pak") and (m[:-4] + ".z") in mem:
                diag["files_with_hap_pak_and_hap_z"] += 1
        del mem
        for m, flat in trees:
            if not any(tag == cpk.TAG_OBJ or v == UNLOCK_CODE for _, tag, v in flat):
                continue
            root = rfe.tree(flat, T)  # racine = le hap (name, id, group, action*)
            _scan_hap(n, m, root, groups, target_ems, unlocks, places, SP, QS)
        del trees
    return unlocks, places, diag


def _context(hap, groups, SP, QS):
    gid = _i(rfe.kv(hap, "group"))
    chain, subs, states, neg = [], set(), set(), False
    g, guard = groups.get(gid), 0
    while g and guard < 40:
        name, parent, toks, attr = g
        chain.append(name)
        for c, i in toks:
            if c == TOK_SUBPHASE and i in SP:
                subs.add("%s:%s" % SP[i])
            elif c == TOK_STATE:
                states.add(("NOT " if attr and attr & 0x10 else "") + QS.get(i, "0x%08x" % (i or 0)))
        g = groups.get(parent)
        guard += 1
    return {"group_chain": chain, "subphases": sorted(subs), "scene_states": sorted(states)}


AREA_CODE = "0x8cf2e32"  # action hap 'エリア' (zone : area/value/position)


def _hap_areas(hap):
    """Positions des zones (actions 0x8cf2e32) du meme hap : indice de lieu pour une action sans position."""
    out = []
    for a in hap["k"]:
        if a["t"] == "action" and rfe.kv(a, "code") == AREA_CODE:
            for nd in rfe.walk(a):
                if nd["t"] == "position":
                    p = rfm._pos(nd["v"])
                    if p:
                        out.append({"area_action": rfe.kv(a, "name"), "position": p})
                    break
    return out[:12]


def _subphase_starts(subphases, sub_pos):
    out = []
    for s in subphases:
        ph, name = s.split(":", 1)
        r = sub_pos.get((ph, name))
        if r and r.get("PlayerPos"):
            v = [float(x) for x in r["PlayerPos"].split()[:3]]
            if any(v):
                out.append({"subphase": s, "player_start": [round(x, 2) for x in v], "room": r.get("RoomNo"),
                            "comment_ja": r.get("Comment")})
    return out


def _scan_hap(n, m, hap, groups, target_ems, unlocks, places, SP, QS):
    hname = rfe.kv(hap, "name")
    ctx = None
    stack = [(hap, None)]
    while stack:
        node, act = stack.pop()
        for c in node["k"]:
            a = c if c["t"] == "action" else act
            if c["t"] == "action" and rfe.kv(c, "code") == UNLOCK_CODE:
                ctx = ctx or _context(hap, groups, SP, QS)
                params = {k["t"]: k["v"] for k in c["k"] if k["t"] not in ("code", "name", "id", "attribute")}
                unlocks.append({"file": n, "member": m, "hap": hname, "hap_area_positions": _hap_areas(hap),
                                "action": rfe.kv(c, "name"),
                                "action_id": rfe.kv(c, "id"), "objId": rfe.kv(c, "ObjId"),
                                "setType": _i(rfe.kv(c, "setType")), "setFlag": _i(rfe.kv(c, "setFlag")),
                                "other_fields": {k: v for k, v in params.items()
                                                 if k not in ("ObjId", "setType", "setFlag")}, **ctx})
            oid = rfe.kv(c, "objId")
            if oid in target_ems and c["t"] == "value":
                ctx = ctx or _context(hap, groups, SP, QS)
                loc = rfe.kid(c, "location")
                pos = rfm._pos(rfe.kv(loc, "position")) if loc else None
                gen = act is not None and rfe.kid(act, "items") is not None and rfe.kid(act, "points") is not None
                d = {"objId": oid, "setType": _i(rfe.kv(c, "setType")), "setFlag": _i(rfe.kv(c, "setFlag")),
                     "kind": "generator" if gen else "layout", "file": n, "member": m, "hap": hname,
                     "action": rfe.kv(act, "name") if act else None, "action_code": rfe.kv(act, "code") if act else None,
                     "position": pos, **ctx}
                if gen:
                    pts = rfe.kid(act, "points")
                    pl = []
                    for nd in rfe.walk(pts):
                        if nd["t"] == "point":
                            p = rfm._pos(nd["v"])
                            if p:
                                pl.append(p)
                    d["points"] = pl[:8]
                    d["position"] = pl[0] if pl else None
                    d["rate"] = _i(rfe.kv(c, "rate"))
                prm = rfe.kid(c, "param")
                if prm:
                    pv = {}
                    for v in prm["k"]:
                        if v["t"] == "value" and rfe.kv(v, "name") not in (None, "puid"):
                            pv[rfe.kv(v, "name")] = rfe.kv(v, "body")
                    if pv:
                        d["params"] = pv
                places.append(d)
            stack.append((c, a))


# --------------------------------------------------------------------------------------------- analyse

def exe_evidence():
    out = {}
    for k, (rva, want) in EXE_CHECKS.items():
        o = xref.rva2off(rva)
        got = xref.D[o:o + len(want)] if o is not None else b""
        out[k] = {"rva": hex(rva), "ok": got == want}
    return out


def area_for(p):
    a = None
    for nm in [p.get("action"), p.get("hap")] + p.get("group_chain", []):
        a = rfm.area_of(nm)
        if a:
            return a, "name_keyword"
    room = re.match(r"st\d/(r\w+)\.dat", p["file"])
    if room and room.group(1) in rfm.ROOMS:
        return rfm.ROOMS[room.group(1)], "room_file"
    for s in p.get("subphases", []):
        a = rfm.area_of(s.split(":", 1)[1])
        if a:
            return a, "owner_subphase"
    return None, None


def slim(p):
    keys = ("objId", "setType", "setFlag", "kind", "position", "file", "member", "hap", "action", "group_chain",
            "subphases", "scene_states", "params", "rate")
    d = {k: p[k] for k in keys if p.get(k) not in (None, [], {})}
    a, src = area_for(p)
    if a:
        d["area"], d["area_source"] = a, src
    return d


def run(update_enemies: bool = False) -> dict:
    eba_path = RESEARCH / "enemies_by_area.json"
    eba = json.load(open(eba_path, encoding="utf8"))
    cat = eba["catalogue"]
    # re-executable : les entrees deja resolues par une passe precedente sont reprises
    # + les 30 donnees sans placement de la premiere passe (ORIGINAL_UNPLACED) pour garder la meme couverture
    # apres une regeneration de enemies_by_area.json
    missing = sorted({r["SaveID"] for r in eba["records_without_placement"]}
                     | {r["SaveID"] for r in eba.get("records_resolved_logic_gaps", [])} | set(ORIGINAL_UNPLACED))
    fresh_unplaced = {r["SaveID"] for r in eba["records_without_placement"]} |         {r["SaveID"] for r in eba.get("records_resolved_logic_gaps", [])}
    recs = {sid: [c for c in cat if c["SaveID"] == sid] for sid in missing}
    target_ems = {c["EmID"] for rows in recs.values() for c in rows}
    qnpc = json.load(open(RESEARCH / "world_positions.json", encoding="utf8"))["quest_npcs"]
    phases = json.load(open(RESEARCH / "phases.json", encoding="utf8"))
    sub_pos = {(ph, r["Name"]): r for ph, rows in phases["sub_phase_files"].items() for r in rows}

    T = rfe.tag_names()
    for t in EXTRA_TAGS:
        T.setdefault(zlib.crc32(t.encode()), t)
    SP = rfe.subphase_hashes()
    QS = q_state_hashes()
    unlocks, places, diag = scan(target_ems, T, SP, QS)

    results = []
    for sid in missing:
        rows = recs[sid]
        r0 = rows[0]
        entry = {"SaveID": sid, "name": r0["unit_data_name"],
                 "emlist": [{"EmID": c["EmID"], "setType": c["setType"], "setFlag": c["setFlag"],
                             "setFlag_mask": hex(mask_of(c["setFlag"])), "mode": mode_of(c), "QueID": c["QueID"]}
                            for c in rows],
                 "unlock": [], "positions": []}
        # 1) mort d'un ennemi place
        for c in rows:
            hits = [p for p in places if death_match(c, p["objId"], p["setType"], p["setFlag"])]
            if hits:
                entry["unlock"].append({"how": "kill", "rule": "exe 0x8257C0 (mort, masque setFlag %s)"
                                        % hex(mask_of(c["setFlag"])), "placements": len(hits),
                                        "confidence": "high"})
                entry["positions"] += [slim(p) for p in hits]
        # 2) EmListUnlockAction (hap)
        for c in rows:
            for u in unlocks:
                if event_match(c, u["objId"], u["setType"], u["setFlag"]):
                    a, _src = area_for(u)
                    # position indicative : meme objId pose dans le meme fichier, sous-phases communes si possible
                    same = [p for p in places if p["objId"] == c["EmID"] and p["file"] == u["file"]]
                    inter = [p for p in same if set(p.get("subphases", [])) & set(u["subphases"])]
                    for p in inter:
                        sp = slim(p)
                        sp["note"] = "entite %s posee dans le meme fichier et les memes sous-phases" % c["EmID"]
                        entry["positions"].append(sp)
                    starts = _subphase_starts(u["subphases"], sub_pos)
                    entry["unlock"].append({"area": a,"how": "hap EmListUnlockAction (敵図鑑解放)", "rule": "exe 0x3A04C0 -> 0x8257C0",
                                            "file": u["file"], "member": u["member"], "hap": u["hap"],
                                            "action": u["action"], "group_chain": u["group_chain"],
                                            "subphases": u["subphases"], "scene_states": u["scene_states"],
                                            "position_estimate": {
                                                "note": "l'action n'a pas de position : elle s'execute dans le flux "
                                                        "du hap (apres les evenements qui la precedent) pendant la "
                                                        "sous-phase ; position = depart joueur de la sous-phase "
                                                        "(PlayerPos de pXXX_sub.bxm) + zones du meme hap",
                                                "subphase_start": starts,
                                                "hap_areas": u.get("hap_area_positions", []),
                                                "confidence": "medium" if starts else "low"},
                                            "confidence": "high"})
        # 3) QueID : fin de la quete (numero decimal = chiffres hexa de QueID)
        for c in rows:
            if c["QueID"] not in (None, "", "-1"):
                # QueID = '0x%03d' % numero DECIMAL de la quete (0x590 -> q590)
                q = "q" + c["QueID"][2:] if re.fullmatch(r"0x[0-9]{3}", c["QueID"]) else None
                if q:
                    info = qnpc.get(q, {})
                    entry["unlock"].append({"how": "quest completion", "quest": q,
                                            "quest_name": info.get("english_name"),
                                            "rule": "exe 0x3F8671 -> 0x8259D0 (QueID == '0x%03d' % quete)",
                                            "quest_giver_positions": [g.get("position") for g in info.get("givers", [])][:3],
                                            "confidence": "high"})
                    # ennemis du meme EmID poses dans les fichiers de cette quete / salles (pour la position)
                    near = [p for p in places if p["objId"] == c["EmID"]
                            and (q in p["file"] or any(q in s for s in p.get("scene_states", []))
                                 or any(q in g for g in p.get("group_chain", [])))]
                    if not near:
                        near = [p for p in places if p["objId"] == c["EmID"] and (p["setType"] or 0) == c["setType"]]
                    for p in near:
                        sp = slim(p)
                        sp["note"] = "ennemi du meme EmID/setType (combat de la quete ; la donnee vient a la fin de la quete)"
                        entry["positions"].append(sp)
        # 4) cas codes en dur dans l'exe
        if r0["EmID"] == "emb000" and sid in (150, 151, 152):
            st = {150: "q400/RUN_1", 151: "q400/RUN_2", 152: "q400/DONE"}[sid]
            entry["unlock"].append({"how": "quest state", "state": st, "quest": "q400",
                                    "rule": "exe 0x825AE0 (appele par 0x3F1CA7) : RUN_1 -> 150, RUN_2 -> +151, DONE -> +152",
                                    "confidence": "high"})
            entry["positions"] += [dict(slim(p), note="emb000 du script/hap de q400")
                                   for p in places if p["objId"] == "emb000"]
        if r0["EmID"] == "em5000" and r0["setType"] in (5, 6):
            entry["unlock"].append({"how": "ending", "trigger": "saut de phase vers pf10 EndRoll_A ou BackTitle_A",
                                    "rule": "exe 0x85C160 : code -1 -> 0x85C89D enregistre em5000 setType 5 puis 6",
                                    "confidence": "high"})
            entry["positions"] += [dict(slim(p), note="combat final d'Eve (setType du placement != 5/6)")
                                   for p in places if p["objId"] == "em5000"]
        if r0["setType"] == 10:
            emp = [p for p in places if p["objId"] == r0["EmID"] and "EMP" in (p.get("params") or {})]
            entry["unlock"].append({"how": "kill after EMP attack",
                                    "rule": "exe 0x825780 : setType remplace par 10 si [ennemi+0x2C32C] != 0. Le "
                                            "drapeau est pose par l'attaque EMP = actions EmBase 0x84 (132, "
                                            "0x696337 -> 0x53F860, 0x53FCCD) et 0x85 (133, 0x69646F) de la table "
                                            "de sauts 0x6979e4 (EmBase vtable slot 174 = 0x692760), motions "
                                            "05a0/05a1/05a2 (sons em_common_EMP_open/Buzzer/atk_loop/end dans "
                                            "em000f/em001f/em004f/em005f = em0000, em0010, em0040, em0050 "
                                            "seulement). Capacite activee par le parametre de placement 'EMP' "
                                            "(probabilite 1 / 0.5 / 0.3 ; chaine 'EMP' lue par EmBase 0x65f730 "
                                            "(0x66016c) et Em0040 0x5a73ca).",
                                    "emp_placements": len(emp),
                                    "data_source": "placements %s avec param EMP (routes C/D : p300 25/26/27_CD "
                                                   "City Ruins, r200 groupe '塔出現後' C)" % r0["EmID"],
                                    "confidence": "high" if emp else "medium"})
            entry["positions"] += [dict(slim(p), note="placement avec param EMP=%s" % p["params"]["EMP"])
                                   for p in emp]
        if r0["EmID"] in ("em1030", "em1040") and r0["setType"] == 6:
            sel = ("select/9S (le joueur est 9S, A2 vaincue)" if r0["EmID"] == "em1030"
                   else "select/A2 (le joueur est A2, 9S vaincu)")
            entry["unlock"].append({"how": "ending", "trigger": "saut de phase vers pf10 (EndRoll_CD / BackTitle) "
                                    "apres le choix final, " + sel,
                                    "rule": "exe 0x85C160 (codes 2..4) : em1030 st6 si select/9S, em1040 st6 si "
                                            "select/A2 (puis em8002, em8020 st2, em8010 st6)",
                                    "subphases": ["p300:340_C_Tower_9Swin" if r0["EmID"] == "em1030"
                                                  else "p300:340_D_Tower_A2win"],
                                    "confidence": "high"})
        if r0["EmID"] == "emb054":
            entry["unlock"].append({"how": "quest reward", "reward_id": 123,
                                    "trigger": "getReWard('123') = Cruel Lament, st1/r160 densetu_ON_TALK_ev4 "
                                               "(forgeron legendaire Masamune, Chateau de la Foret)",
                                    "rule": "exe 0x7ca970 (attribution getReWard) : id 0x7b (0x7caa7f) -> "
                                            "0x825e20(emb054) x2 puis lignes EmList emb054 -> 0x817980 (SaveID)",
                                    "position": [998.5, 3.62, -377.06], "confidence": "high"})
        if r0["EmID"] == "em0096" and r0["setType"] == 2:
            entry["unlock"].append({"how": "kill (setType 2 non trouve dans les donnees)",
                                    "rule": "mort, regle 0x8257C0 : il faut un em0096 de setType 2 ; les em0096 "
                                            "places (arenes DLC q090/q091/q092, r520) sont setType 0 -> ligne 190 "
                                            "non atteinte par ces placements. em0096 est aussi cree a l'execution "
                                            "par em0046 (0x64da0b : em0042 -> em0090, em0044 -> em0094, em0046 -> "
                                            "em0096) : setType de l'enfant non lu.",
                                    "candidates": "em0046 places (q091/q092/q102 setType 1, p300, r150, r501, r502)",
                                    "confidence": "low"})
        hegel_dup = r0["EmID"] == "em8800" and sid == 129
        if hegel_dup:
            entry["unlock"].append({"how": "same as 128", "rule": "2 lignes identiques (em8800 st0, mode 0) : "
                                    "0x8257C0 ne s'arrete pas a la 1re ligne -> 128 et 129 debloquees ensemble",
                                    "confidence": "high"})
        if not entry["unlock"]:
            entry["unlock"].append({"how": "unresolved", "confidence": "none"})
        best = max(entry["unlock"], key=lambda u: {"high": 3, "medium": 2, "low": 1}.get(u["confidence"], 0))
        entry["status"] = "resolved" if best["confidence"] in ("high", "medium") else "open"
        entry["confidence"] = best["confidence"]
        # dedoublonnage des positions
        seen, pos = set(), []
        for p in entry["positions"]:
            k = (p.get("file"), p.get("hap"), tuple(p.get("position") or ()), p.get("setType"), p.get("setFlag"))
            if k not in seen:
                seen.add(k)
                pos.append(p)
        entry["positions"] = pos[:40]
        entry["positions_total"] = len(pos)
        results.append(entry)

    out = {
        "_source": "tools/logic_gaps_enemies.py (lecture seule CPK + exe v1.04)",
        "exe_evidence": exe_evidence(),
        "rules": __doc__.split("Regles de l'exe v1.04", 1)[1].strip(),
        "summary": {"records": len(results), "resolved": sum(r["status"] == "resolved" for r in results),
                    "open": [r["SaveID"] for r in results if r["status"] != "resolved"],
                    "unlock_actions_found": len(unlocks), "target_placements_found_in_pak": len(places),
                    "diag": dict(diag)},
        "records": results,
        "emlist_unlock_actions": unlocks,
        "rf_enemies_note": "CORRIGE : rf_enemies.py lit maintenant les *_hap.pak (le .z seulement sans .pak), les "
                           "blocs de groupes v1 (YAX brut) et applique la regle de mort de l'exe (death_match, "
                           "partagee) et la regle de dialogue 0x825CB0.",
    }
    if update_enemies:
        _update_eba(eba_path, eba, [r for r in results if r["SaveID"] in fresh_unplaced])
    return out


def _update_eba(path, eba, results):
    done = {r["SaveID"]: r for r in results if r["status"] == "resolved"}
    eba["records_without_placement"] = [{"SaveID": r["SaveID"], "name": r["name"], "EmID": r["emlist"][0]["EmID"]}
                                         for r in results if r["SaveID"] not in done]
    eba["records_resolved_logic_gaps"] = [
        {"SaveID": r["SaveID"], "name": r["name"], "source": "logic_gaps", "confidence": r["confidence"],
         "unlock": r["unlock"], "positions": r["positions"][:12], "positions_total": r["positions_total"]}
        for r in done.values()]
    eba["changes_logic_gaps"] = (
        "tools/logic_gaps_enemies.py : %d/%d donnees sans placement resolues (deblocage par mort selon la regle de "
        "l'exe 0x8257C0 avec masque setFlag, action hap EmListUnlockAction 0xC168700D, fin de quete QueID, etats "
        "q400, fin A, attaque EMP). Les entrees resolues sont dans records_resolved_logic_gaps (source "
        "'logic_gaps') ; records_without_placement ne garde que les non resolues. A relancer apres chaque "
        "regeneration de enemies_by_area.json (tools/rf_enemies.py ou routes_full.py enemies), qui lit deja les "
        "*_hap.pak (source de verite) et applique les regles de mort / dialogue de l'exe."
        % (len(done), len(results)))
    json.dump(eba, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--update-enemies", action="store_true")
    a = ap.parse_args()
    res = run(a.update_enemies)
    p = Path(a.out) if a.out else er.CACHE / "lg_enemies.json"
    json.dump(res, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    s = res["summary"]
    print("records", s["records"], "resolved", s["resolved"], "open", s["open"], "unlock actions",
          s["unlock_actions_found"], "placements", s["target_placements_found_in_pak"], "exe", res["exe_evidence"])


if __name__ == "__main__":
    main()
