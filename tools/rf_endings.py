"""Declencheurs des fins A..Z (LECTURE SEULE des CPK, aucun lancement du jeu).

Usage :
    python tools/rf_endings.py [--out docs/research] [--raw]

Sources :
- hap en arbres YAX (`*_hap.pak` + `*_grp.pak` ; les `*_hap.z` XML sont INCOMPLETS : p300_hap.z n'a pas
  Ending_M/R/V, q900 n'a Ending_Y que dans q900_9e77724b_grp.pak). Balises YAX = crc32 zlib du nom de balise
  (verifie : subPhase 0xacf1615, name 0x5e237e06, position 0x462ce4f5) ; noms tires des hap.z.
- Table des groupes : `*_hap.pak` version 4, en-tete `<III>` (4, ?, taille de la table d'entrees h) puis
  a h+4... : u32 taille decompressee + zlib d'un YAX `count/group(id,name,parent,tokens,...)`.
- Jetons de groupe : code 0xf3b97443 = sous-phase (id = crc32 du nom), 0x35c92545 = etat SceneState
  (id = crc32, ex. 'Route/A' 0x583082bb), 0x5cda8ece = salle (id 0x502 -> r502).
- puid code 0xa6aaf7a4 = reference a une action/hap du meme fichier (id) ; 0xcecad9ce = objet systeme
  (id = crc32 du nom, ex. SceneStateSystem 0x35c92545... voir OBJ_NAMES).
- exe : 0x7614a0 = saut de phase (edx = phase, r8 = nom de sous-phase). Sites : voir EXE_TRIGGERS.
Resultat : docs/research/endings_triggers.json (+ `--raw` : endings_triggers_raw.json, contexte complet).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIRS = ("ph1", "ph2", "ph3", "ph4", "phf", "st1", "st2", "st5", "quest", "core")
JUMP_RE = re.compile(r"^(Ending_|EndRoll_|BackTitle_)")
TOK_SUBPHASE, TOK_SCENE, TOK_ROOM = 0xF3B97443, 0x35C92545, 0x5CDA8ECE
PUID_LOCAL, PUID_OBJ = 0xA6AAF7A4, 0xCECAD9CE
EXTRA_TAGS = ("subPhase", "phase", "name", "position", "objId", "body", "label", "args", "hap", "group", "action",
              "code", "id", "area", "condition", "conditions", "state", "value", "tokens", "command", "commands",
              "size", "comment", "parent", "puid", "pred", "items", "attribute", "priority", "delay", "count",
              "type", "param", "rotation", "scale", "radius", "height", "points", "location")
OBJ_NAMES = ("SceneStateSystem", "MiscState", "QuestState", "ContinueState", "FastTravel", "EnemyGenerator",
             "Action", "PhaseEventAction", "UITimerAction", "ScrollMap", "HackingEnemy", "EmBase", "NPC", "Pl0000",
             "BehaviorAppBase", "GroupImpl", "EntityLayoutAction", "Behavior")


# --- YAX -----------------------------------------------------------------------------------------

def tag_names() -> dict[int, str]:
    names = set(EXTRA_TAGS)
    for f in ("ph1/p100.dat", "ph2/p200.dat", "ph3/p300.dat"):
        stem = f.split("/")[1][:-4]
        z = er.dat_member(f, f"{stem}_hap.z")
        if z:
            names |= set(re.findall(r"<([A-Za-z_][A-Za-z0-9_]*)>", zlib.decompress(z).decode("shift_jis", "replace")))
    return {zlib.crc32(n.encode()): n for n in names}


def tree(flat, T):
    """[(profondeur, hachage, valeur)] -> noeud racine {t, v, k}."""
    root = {"t": "#root", "v": "", "k": []}
    stack = [(-1, root)]
    for ind, tag, val in flat:
        n = {"t": T.get(tag, f"0x{tag:08x}"), "v": val, "k": []}
        while stack[-1][0] >= ind:
            stack.pop()
        stack[-1][1]["k"].append(n)
        stack.append((ind, n))
    return root


def kid(n, t):
    for c in n["k"]:
        if c["t"] == t:
            return c
    return None


def kv(n, t):
    c = kid(n, t)
    return c["v"] if c else None


def walk(n):
    yield n
    for c in n["k"]:
        yield from walk(c)


def group_table(pak: bytes, T):
    try:
        # version 4 = zlib, version 1 = YAX brut (avant : seuls les version 4 etaient lus)
        raw = cpk.pak_group_block(pak)
        if raw is None:
            return []
        root = tree(cpk.yax(raw), T)
    except Exception:
        return []
    return [g for g in root["k"] if g["t"] == "group"]


# --- dictionnaires de hachages -----------------------------------------------------------------

def subphase_hashes():
    pi = er.bxm.parse(cpk.dat_files(er.game_file("core/coreph.dat"))["PhaseInfo.bxm"])[0]
    out = {}
    for ph in er.kids(er.kids(pi, "InfoList")[0], "Phase"):
        for s in er.kids(ph, "SubPhase"):
            for c in s["children"]:
                out[zlib.crc32(c["value"].encode())] = (ph["attrs"].get("name"), c["value"])
    return out


def ihex(s):
    try:
        return int(s, 16)
    except (TypeError, ValueError):
        return None


# --- extraction --------------------------------------------------------------------------------

def action_summary(a, ids):
    """Resume lisible d'une action : nom, code, conditions (cible, etat), commandes (cible, label, args), zone."""
    s = {"name": kv(a, "name"), "code": kv(a, "code"), "id": kv(a, "id")}
    conds, cmds, refs = [], [], []
    for n in walk(a):
        if n["t"] == "puid":
            code, pid = ihex(kv(n, "code")), ihex(kv(n, "id"))
            refs.append(ids.get(pid, f"0x{pid or 0:08x}") if code == PUID_LOCAL else ids.get(("obj", pid), f"obj:0x{pid or 0:08x}"))
    for v in walk(a):
        if v["t"] == "value" and kid(v, "puid") is not None and kid(v, "condition") is not None:
            p = kid(v, "puid")
            pid = ihex(kv(p, "id"))
            st = kid(kid(v, "condition"), "state")
            conds.append({"target": ids.get(pid, f"0x{pid or 0:08x}"),
                          "state": kv(st, "label") if st else None, "pred": kv(kid(v, "condition"), "pred")})
        if v["t"] == "command" and kid(v, "label") is not None:
            pass
    for n in walk(a):
        k = n["k"]
        for i, c in enumerate(k):
            if c["t"] == "command" and kid(c, "label") is not None:
                args = k[i + 1]["v"] if i + 1 < len(k) and k[i + 1]["t"] == "args" else None
                cmds.append({"label": kv(c, "label"), "args": args})
            if c["t"] == "command" and kid(c, "command") is not None:
                inner = kid(c, "command")
                cmds.append({"label": kv(inner, "label"), "args": kv(c, "args")})
    area = kid(a, "area")
    if area is not None:
        pos = [kv(v, "position") for v in area["k"] if v["t"] == "value"]
        if pos:
            s["area_positions"] = pos
    for t in ("phase", "subPhase", "questId"):
        if kv(a, t):
            s[t] = kv(a, t)
    if conds:
        s["conditions"] = conds
    if cmds:
        s["commands"] = cmds
    if refs:
        s["refs"] = sorted(set(map(str, refs)))
    return s


def scan_file(name, T, SP, SCENE):
    d = cpk.dat_files(er.game_file(name))
    haps, groups = [], []
    for k, v in d.items():
        if not k.endswith(".pak"):
            continue
        if k.endswith("_hap.pak"):
            groups += group_table(v, T)
        try:
            for t in cpk.pak_yax(v):
                h = tree(t, T)
                h["member"] = k
                haps.append(h)
        except Exception:
            continue
    gidx = {ihex(kv(g, "id")): g for g in groups}
    ids = {}
    for o in OBJ_NAMES:
        ids[("obj", zlib.crc32(o.encode()))] = o
    for h in haps:
        hn = kv(h, "name")
        ids[ihex(kv(h, "id"))] = f"hap:{hn}"
        for a in h["k"]:
            if a["t"] == "action":
                ids[ihex(kv(a, "id"))] = f"{hn}/{kv(a, 'name')}"
    for g in groups:
        ids.setdefault(ihex(kv(g, "id")), f"group:{kv(g, 'name')}")

    def group_chain(gid):
        out, seen = [], set()
        while gid in gidx and gid not in seen:
            seen.add(gid)
            g = gidx[gid]
            toks = []
            tk = kid(g, "tokens")
            for v in (tk["k"] if tk else []):
                if v["t"] != "value":
                    continue
                c, i = ihex(kv(v, "code")), ihex(kv(v, "id"))
                if c == TOK_SUBPHASE:
                    toks.append({"subphase": SP.get(i, (None, f"0x{i:08x}"))[1], "phase": SP.get(i, (None,))[0]})
                elif c == TOK_SCENE:
                    toks.append({"scene_state": SCENE.get(i, f"0x{i:08x}")})
                elif c == TOK_ROOM:
                    toks.append({"room": f"r{i:03x}"})
                else:
                    toks.append({"code": kv(v, "code"), "id": kv(v, "id")})
            out.append({"group": kv(g, "name"), "id": kv(g, "id"), "comment": kv(g, "comment"), "tokens": toks})
            gid = ihex(kv(g, "parent"))
        return out

    found = []
    for h in haps:
        acts = [a for a in h["k"] if a["t"] == "action"]
        hits = []
        for a in acts:
            sp = kv(a, "subPhase")
            if sp and JUMP_RE.match(sp):
                hits.append(("phase_jump", sp, a))
            for c in action_summary(a, {}).get("commands", []):
                if c["label"] == "ContinueState.setBadEnd":
                    hits.append(("setBadEnd", None, a))
                if c["label"] == "SceneStateSystem.set" and c["args"] and re.fullmatch(r"ending_[A-Z]+", c["args"]):
                    hits.append(("scene_state", c["args"], a))
                    break
        hits = list({(k, t, id(a)): (k, t, a) for k, t, a in hits}.values())
        if not hits:
            continue
        my_ids = {ihex(kv(h, "id"))} | {ihex(kv(a, "id")) for a in acts}
        referrers = []
        for h2 in haps:
            if h2 is h:
                continue
            for a2 in h2["k"]:
                if a2["t"] != "action":
                    continue
                if any(n["t"] == "puid" and ihex(kv(n, "id")) in my_ids
                       for n in walk(a2)):
                    r = action_summary(a2, ids)
                    r["hap"] = kv(h2, "name")
                    r["groups"] = [g["group"] for g in group_chain(ihex(kv(h2, "group")))]
                    referrers.append(r)
        for kind, target, a in hits:
            setbad = None
            if kind == "setBadEnd":
                summ = action_summary(a, ids)
                for c in summ.get("commands", []):
                    if c["label"] == "ContinueState.setBadEnd":
                        setbad = c["args"]
                target = {"0": "Ending_W", "1": "Ending_U"}.get(str(setbad), f"setBadEnd({setbad})")
            found.append({
                "file": name, "member": h["member"], "kind": kind, "target": target,
                "hap": kv(h, "name"), "hap_id": kv(h, "id"), "action": kv(a, "name"),
                "groups": group_chain(ihex(kv(h, "group"))),
                "hap_actions": [action_summary(x, ids) for x in acts],
                "referrers": referrers,
            })
    return found


def scene_dict(names):
    """crc32 -> nom d'etat SceneState : args des commandes SceneStateSystem.* + Route/X."""
    out = {zlib.crc32(f"Route/{r}".encode()): f"Route/{r}" for r in "ABCDE"}
    for s in ("ending_A", "ending_B", "ending_C", "ending_D", "ending_CD", "ending_E"):
        out[zlib.crc32(s.encode())] = s
    for f in names:
        stem = f.split("/")[1][:-4]
        z = er.dat_member(f, f"{stem}_hap.z")
        if not z or len(z) < 100:
            continue
        for a in re.findall(r"<args>([^<]{1,80})</args>", zlib.decompress(z).decode("shift_jis", "replace")):
            for w in a.split():
                w = w.strip('"*!')
                out[zlib.crc32(w.encode())] = w
    return out


# --- exe ---------------------------------------------------------------------------------------

def exe_triggers():
    """Sites de l'exe qui sautent vers pf30 (0x7614a0, edx=0xf30) : verifies par desassemblage (capstone)."""
    try:
        import xref
    except Exception as e:  # exe absent
        return [{"error": str(e)}]
    D = xref.D

    def s_at(rva):
        o = xref.rva2off(rva)
        return D[o:o + 32].split(b"\0")[0].decode("latin-1") if o else None

    def lea_target(site):
        o = xref.rva2off(site)
        if D[o:o + 3] not in (b"\x4c\x8d\x05",):
            return None
        return site + 7 + struct.unpack_from("<i", D, o + 3)[0]

    out = []
    for site, letter, note in EXE_TRIGGERS:
        t = lea_target(site)
        out.append({"rva": f"0x{site:x}", "function": [f"0x{x:x}" for x in (xref.func_of(site) or ())],
                    "string": s_at(t) if t else None, "letter": letter, "evidence": note,
                    "verified": (s_at(t) == f"Ending_{letter}") if t else False})
    return out


EXE_TRIGGERS = [
    (0x991B77, "K", "menu objets (fn 0x991958, son 'core_main_disicion') : nom interne de l'objet utilise compare a "
                    "'fish_16' (Mackerel) -> saut 0xf30 Ending_K + BGM_Player_Die"),
    (0x899125, "T", "fn 0x898ee0 : objet 3000..3999 (puce) ; 0x7f54c0 teste emplacement == 0xd0a (3338 OS Chip) et "
                    "equipe -> Ending_T"),
    (0x9893E8, "T", "menu puces (fn 0x9892df : core_pluginchip_remove / _dump / _settype_equip) -> Ending_T"),
    (0x98BA08, "T", "menu puces, 2e chemin (fn 0x98b83f, meme schema START/Ending_T)"),
    (0x83DC66, "U", "ecran game over (fn 0x83dc4b) : si [0x11eac20]==1 -> Ending_U ; [0x11eac20] ecrit par "
                    "ContinueState.setBadEnd(x) (natif 0x80e200 : etat 6, valeur x)"),
    (0x83DCB8, "W", "meme fonction : [0x11eac20]==0 (setBadEnd 0) -> Ending_W"),
]


# --- interpretation (manuelle, traduction NON OFFICIELLE) --------------------------------------
# Rempli a partir de la sortie brute (--raw). Chaque entree reprend les noms japonais trouves.

INTERP: dict[str, dict] = {}  # rempli plus bas (voir _interp())


def chapters_for(subphases, phases):
    """Sous-phases -> chapitres (point de selection de chapitre le plus proche avant, meme fichier, route
    compatible). DEDUIT."""
    files = phases["sub_phase_files"]
    order = {(ph, r["Name"]): r["order"] for ph, rows in files.items() for r in rows}
    chs = phases["chapters"]
    out = []
    for ph, sp in subphases:
        if (ph, sp) not in order:
            continue
        o = order[(ph, sp)]
        tok = sp.split("_")
        route = next((t for t in tok if t in ("A", "B", "AB", "CD", "C", "D")), None)
        ok_groups = {"A": {0, 2}, "B": {1, 2}, "AB": {0, 1, 2}, "CD": {3}, "C": {3}, "D": {3}}.get(route, {0, 1, 2, 3})
        best = None
        for c in chs:
            if c["phase"] != ph or c["route_group"] not in ok_groups or (ph, c["subphase"]) not in order:
                continue
            co = order[(ph, c["subphase"])]
            if co <= o and (best is None or co > order[(ph, best["subphase"])]):
                best = c
        if best:
            out.append({"subphase": sp, "chapter": f"{best['chapter']:02d}-{best['sub']:02d}",
                        "route_group": {0: "A", 1: "B", 2: "A+B", 3: "C/D"}[best["route_group"]],
                        "chapter_name": best.get("english_name")})
    return out


def build(out_dir: Path, raw: bool = False) -> dict:
    T = tag_names()
    SP = subphase_hashes()
    names = [n for n in er.all_names() if n.endswith(".dat") and n.split("/")[0] in DIRS]
    SCENE = scene_dict([n for n in names if n.split("/")[0] in ("ph1", "ph2", "ph3", "phf", "quest", "st1", "st2")])
    phases = json.loads((out_dir / "phases.json").read_text(encoding="utf-8"))
    endings = json.loads((out_dir / "endings.json").read_text(encoding="utf-8"))
    found = []
    for n in names:
        try:
            found += scan_file(n, T, SP, SCENE)
        except Exception as e:
            print("skip", n, e, file=sys.stderr)
    for f in found:
        sps = [(t["phase"], t["subphase"]) for g in f["groups"] for t in g["tokens"] if "subphase" in t]
        f["active_subphases"] = [s for _, s in sps]
        f["chapters"] = chapters_for(sps, phases)
        f["route_states"] = sorted({t["scene_state"] for g in f["groups"] for t in g["tokens"] if "scene_state" in t})
    exe = exe_triggers()
    if raw:
        (out_dir / "endings_triggers_raw.json").write_text(json.dumps(found, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
    titles = {e["letter"]: e for e in endings["endings"]}
    res = {"_source": "tools/rf_endings.py ; hap YAX (*_hap.pak, *_grp.pak), NieRAutomata.exe (capstone), "
                      "phf/pf30_sub.bxm. Traductions des noms japonais = NON OFFICIELLES.",
           "endings": []}
    for L in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        e = titles.get(L, {})
        def is_hit(f):
            if f["target"] in (f"Ending_{L}", f"ending_{L}") or (L == "A" and f["target"] == "EndRoll_A"):
                return True
            if L in "CD" and f["target"] == "EndRoll_CD":
                return f"{L}End" in (f["action"] or "")
            if L == "E":
                return any(a["name"] == "フェーズジャンプ_TrueEnd" or a.get("subPhase") == "360_CD_TrueEnd_FIN"
                           for a in f["hap_actions"]) and f["kind"] == "phase_jump"
            return False
        hits = [f for f in found if is_hit(f)]
        srcs = []
        for f in hits:
            srcs.append({"file": f["file"], "member": f["member"], "kind": f["kind"], "target": f["target"],
                         "hap": f["hap"], "action": f["action"],
                         "hap_actions": [a["name"] for a in f["hap_actions"]],
                         "conditions": [c for a in f["hap_actions"] for c in a.get("conditions", [])][:12],
                         "commands": [c for a in f["hap_actions"] for c in a.get("commands", [])][:12],
                         "referrers": [{"hap": r["hap"], "action": r["name"],
                                        "conditions": r.get("conditions", [])[:6],
                                        "commands": r.get("commands", [])[:6]} for r in f["referrers"]][:8],
                         "groups": [g["group"] for g in f["groups"]],
                         "active_subphases": sorted(set(f["active_subphases"])),
                         "chapters": list({c["chapter"] + c["route_group"]: c for c in f["chapters"]}.values()),
                         "route_states": f["route_states"]})
        for x in exe:
            if x.get("letter") == L:
                srcs.append({"kind": "exe", **x})
        item = {"letter": L, "title": e.get("title"), "pf30_subphase": e.get("pf30_subphase"),
                "pf30_comment_ja": e.get("pf30_comment_ja"),
                "pf30_comment_en_unofficial": e.get("pf30_comment_en_unofficial"),
                "trigger_sources": srcs}
        item.update(INTERP.get(L, {}))
        res["endings"].append(item)
    res["dlc"] = {"note": "Ending DLC (3C3C1D119440927): ph4/p400 hap '小型ゼンマイ操作' (small wind-up machine "
                          "control), subphase 60_00_OrganizePapers -> phase jump EndRoll_DLC (p400 = Plato/DLC "
                          "phase, entered from the Amusement Park TV, 10_00_firstChoice). Not a letter ending.",
                  "confidence": "medium"}
    res["other_jumps"] = [{"file": f["file"], "hap": f["hap"], "action": f["action"], "target": f["target"],
                           "active_subphases": f["active_subphases"]} for f in found
                          if not re.match(r"^(Ending_[A-Z]|ending_[A-Z])$", str(f["target"]))
                          and f["target"] not in ("EndRoll_A", "EndRoll_CD")]
    return res


def _interp():
    def E(joke, conf, trig, where, web, unresolved=None, kind="joke"):
        d = dict(is_joke=joke, kind=kind, confidence=conf, trigger_en_unofficial=trig, where=where, web_check=web)
        if unresolved:
            d["unresolved"] = unresolved
        return d
    INTERP.update({
        "A": E(False, "high", "End of Route A: after the Eve fight, hap 'イベント再生' (event playback, played by "
               "'..M1090_S0320_GM_a') sets SceneState ending_A, clears GAME flags 8/9 and jumps to pf10 EndRoll_A. "
               "Group tokens: Route/A + subphases 200_xx (Eve fight).",
               "ph2/p200 10-04..10-05 (200_80_AB_Ruined_City_end), Route A", "agree (beat Route A, 10-05)",
               kind="main"),
        "B": E(False, "medium", "phf/pf10 hap '流れ(3)' (flow 3) 'コマンド送信_クリアB' (send command: clear B) sets "
               "SceneState ending_B and unlocks achievement 0x11 (inside the credits phase pf10).",
               "pf10 credits, reached from p200 end of Route B (10-05 v2 'The Beginning of Battle')",
               "agree (beat Route B)", "the p200 Route/B jump into pf10 was not isolated (no EndRoll_B subphase; "
               "the B credits flow is pf10)", kind="main"),
        "C": E(False, "medium", "p300 hap '流れ(26)' (group 340_9S勝利 = 9S wins) action 'フェーズジャンプ_CEnd' -> pf10 "
               "EndRoll_CD. Path: 332_CD_Tower_Talk '流れ' 'フェーズジャンプ_9Ssele' -> 335_CD_Tower_sele9S -> "
               "'フェーズジャンプ_9Swin' -> 340_C_Tower_9Swin. exe fn 0x863730: SceneState 'select/9S' set -> "
               "sets 'ending_C' (select/A2 -> ending_D). Script p300_987be645 (in 流れ(26)) tests 'ending_D on?' "
               "(other ending already seen -> 'フェーズジャンプ_TrueEnd' to pf31).",
               "ph3/p300 17-09 -> 17-10 v1 (9S's Final Moments)",
               "DISAGREE: web says choosing A2 gives C and 9S gives D; internal data names the 9S-select/9S-win "
               "branch 'C' (subphase 340_C_, CEnd, select/9S -> ending_C)",
               "which CREDIT_END_TITLE is displayed for each branch was not traced; release behaviour may follow "
               "the web (A2 -> C)", kind="main"),
        "D": E(False, "medium", "p300 hap '流れ(14)' (group 340_A2勝利 = A2 wins) 'フェーズジャンプ_DEnd' -> pf10 "
               "EndRoll_CD (copy in quest/qaef '流れ(27)'). Path: 'フェーズジャンプ_A2sele' -> 335_CD_Tower_seleA2 -> "
               "'フェーズジャンプ_A2win' -> 340_D_Tower_A2win (-> 345_D_Tower_A2win_9Shack). exe: select/A2 -> "
               "ending_D. Script p300_10112854 (in 流れ(14)) tests 'ending_C on?' before 'フェーズジャンプ_TrueEnd'.",
               "ph3/p300 17-09 -> 17-10 v2 (A2's Final Moments)", "DISAGREE (see C): web says 9S -> D",
               "see C", kind="main"),
        "E": E(False, "medium", "No Ending_E jump (pf30 Ending_E is commented '未使用' = unused). True ending: at the "
               "end of the C or D branch, 'フェーズジャンプ_TrueEnd' -> pf31 'start' (credits shoot-'em-up), the "
               "scripts testing the other ending (ending_C / ending_D 'on?'); pf31/p300 '流れ(27)' "
               "'フェーズジャンプ_STGクリア' (STG cleared) -> p300 360_CD_TrueEnd_FIN, 'フェーズジャンプ_諦め' (give up) "
               "-> pf10 BackTitle_CD.", "ph3/p300 340_x -> phf/pf31 -> 350/360_CD_TrueEnd",
               "agree (after C and D, credits shmup)", "the Pod 153 'Yes/No' prompt itself was not located; the "
               "'other ending seen' reading of the 'on?' tests is inferred", kind="main"),
        "F": E(True, "high", "quest/qac8 hap 'バッドエンド' (bad end): 'タイマー' (timer) + '条件ブロック' on the timer, "
               "'行動制限' (restrict actions), noise filter (Pl0000.setUINoiseFilterMax), then "
               "'フェーズジャンプ_バッドエンド' -> Ending_F. pf30 comment: route B prologue, leave the rebuild game "
               "idle too long.", "quest/qac8 (internal quest; prologue Route B per pf30 comment)",
               "agree (let the 9S restore timer run out, 01-03 B)", "qac8 activation subphase not resolved"),
        "G": E(True, "high", "p100 hap 'バットエンド処理' (bad-end handling) in group '飛行ユニット搭乗' (boarding "
               "the flight unit) under '00_02_B_ロボット山＿9S操作開始': a single phase jump with an area at "
               "(-643.7, -10.6, 372.9). pf30: route B prologue, run away without boarding the flight unit.",
               "ph1/p100 prologue Route B (00_02/00_05_B_RobotM...), 01-01 v2",
               "partial: web says 'walk along a crane' at 01-01 B; data = leaving instead of boarding the flight unit"),
        "H": E(True, "high", "p100 hap 'バッドエンド' in group '90_大ハイキョ都市_巨大ロボ襲来' (Goliath attack): areas "
               "'エリア_バッドエンド警告'/'警告2' (warning) and 'エリア_バッドエンド実行' (execute) at (439.5, 10.9, 37.8), "
               "(-146.6, 11.3, 61.8), (-188.8, 21.7, 508.8) -> 'フェーズジャンプ_バッドエンド' Ending_H.",
               "ph1/p100 90_00_AB_Ruined_City / 90_10_AB_Ruined_City_AerialBTL, 05-02 Route A or B",
               "agree (ignore the Goliath intercept order, 05-02)"),
        "I": E(True, "high", "p200 hap 'バッドエンド対応' (bad-end response), group 'A' + '115_９S救出' (9S rescue): "
               "'条件ブロック' (DONE) + area at (258.9, -114.5, 568.6) -> Ending_I.",
               "ph2/p200 110_00_A_Copy_City / 115_AB_Copy_City_AdamDie, Route A 08-01",
               "agree (abandon 9S after Adam, Copied City)"),
        "J": E(True, "high", "p200 haps '司祭達を攻撃した際の対処' / '..対処2' (response when attacking the priests): "
               "'条件コマンド' on ON_SCARE_TALK of 5 priest NPCs + '条件ブロックリスト' on "
               "BehaviorAppBase.getHpRate100 of the same 5 -> Ending_J.",
               "ph2/p200 140_00_A_RobotM_CrazyReligion and 140_20_A_RobotM_CR_GuruRoom, Route A 09-01",
               "agree (kill the peaceful priests while escorting Pascal)"),
        "K": E(True, "high", "exe fn 0x991958 (item-use menu, sound 'core_main_disicion'): if the used item's "
               "internal name == 'fish_16' (Mackerel, UniqueID 8016) -> phase jump 0xf30 Ending_K + BGM_Player_Die.",
               "anywhere (item menu)", "agree (eat the Mackerel)"),
        "L": E(True, "high", "p200 hap 'エリア外警告' (out-of-area warning), group '160~200_ステージ固有行動制御': 5 areas "
               "+ 'エリア_badEnd' (-451.0, 12.8, 461.7) -> Ending_L; enabled by 'エリア外通知(1..4)' (out-of-area "
               "notice) 条件コマンド on HITOUT/INSIDE.",
               "ph2/p200 160_A..200_70 (camp attack -> Eve fight), 10-01..10-04 A/B",
               "agree (flee during the camp attack / Eve section)"),
        "M": E(True, "high", "p300 haps 'バッドエンド' (group '100_砂漠エリア_パスカルのムラへ' = desert, to Pascal's "
               "village; 2 'エリアコマンド' areas) and 'バッドエンド(2)' (group '110_パスカルの村_パスカル護衛' = escort "
               "Pascal) -> Ending_M.", "ph3/p300 100_CD_2_Desert_A2 (14-03) and 110_CD_2_Pascal_Village_A2 (14-04)",
               "agree (A2 doesn't go to help the village, 14-03)"),
        "N": E(True, "high", "st1/r140 (Pascal's Village room) hap '初回訪問時/バッドエンド' (first visit / bad end), "
               "group 'パスカル村＿バッドエンド': 条件コマンド requiring DONE on every villager layout area "
               "('オブジェ配置エリア_パスカル', '鍛冶屋/道具屋', '遊び場', '2F', '1F'...) -> Ending_N; same check "
               "in '陥没前', '陥没後', 'バンカー破壊後', '通常訪問時_パスカル不在中のバッドエンド' (before/after the "
               "collapse, after Bunker destruction, Pascal absent).", "st1/r140 Pascal's Village (any route, "
               "several village states)", "partial: web says routes C/D or 05-01/07-01; data: several village "
               "states incl. first visit", "exact meaning of 'DONE' on a layout area (all residents dead) inferred"),
        "O": E(True, "high", "p300 haps 'バッドエンド処理' / '(2)' / '(5)' / '_9S防衛前まで': 'エリア_予兆' (warning "
               "area) -> signal p300_xx_caution, 'エリア_進行禁止/不可' (no-go area) -> Ending_O; also enabled by "
               "'流れ(9)/条件コマンド_9Sが死んだら' (if 9S dies) and '流れ(汚染解除前)/条件コマンド_2Bが死んだら'.",
               "ph3/p300 10..27_CD (11-02..11-04: 9S hack, big melee, YoRHa contamination, jamming)",
               "agree (leave the City Ruins fight / abandon 2B after the EMP)"),
        "P": E(True, "high", "p300 hap '時間制限' (time limit): infection timeline (Pl0000.setUIPollutionGaugeLv1..7, "
               "set2BDieFilterLv0..3, signals p300_50_virus0..6), each level started when 2B enters "
               "'流れ/エリア_N_汚染LvN' areas, then 'フェーズジャンプ' Ending_P.",
               "ph3/p300 50_CD_Submerge_City_2B (11-06)", "agree (infection reaches 100%)"),
        "Q": E(True, "high", "p300 hap 'バッドエンド処理(4)', groups '50_20_ハイキョ都市_2B死亡目撃' + PL/9S: warning "
               "area (-33.3, -5.7, 239.5), no-go area (-76.3, -25.1, 243.0) -> Ending_Q.",
               "ph3/p300 50_20_CD_Ruined_City_2BDead_9S (11-07)", "agree (9S doesn't go to the Commercial Facility)"),
        "R": E(True, "high", "p300 hap '攻撃した際の処理' (handling when attacked), group '避難するパスカル村の住人' "
               "(evacuating villagers): ON_SCARE_TALK + getHpRate100 on 5 villagers -> Ending_R; Route/C, Route/D.",
               "ph3/p300 120_xx_CD_2_RobotM (14-05, Abandoned Factory shelter)",
               "agree (attack sheltering machines, 14-05)"),
        "S": E(True, "high", "p300 hap 'バッドエンド_塔からの離脱' (leaving the tower): 3 nested areas (HITOUT -> signals "
               "escape_fast/second/third), last area 'エリア_3_2' (261.2, -10.2, 362.9) -> Ending_S; script group "
               "'スクリプト(28)' param 'ending_S'.", "ph3/p300 250_CD_Unknown_9S / 260_00_CD_Ruined_City_9S (17-01)",
               "agree (abandon Devola & Popola)"),
        "T": E(True, "high", "exe: chip menu (fn 0x9892df, sounds core_pluginchip_remove/_dump) and fn 0x898ee0 "
               "(items 3000..3999): 0x7f54c0 tests chip id == 0xd0a (3338 OS Chip) -> Ending_T (0xf30).",
               "anywhere (plug-in chip menu)", "agree (remove the OS chip)"),
        "U": E(True, "high", "quest/qb40 (Bunker base quest) hap '自爆バッドエンド' (self-destruct bad end): "
               "ContinueState.setBadEnd 1 -> native 0x80e200 (game-over state 6, value 1) -> game-over handler "
               "0x83dc4b: value 1 -> Ending_U.", "Bunker (qb40), while the Bunker exists (until Ch11)",
               "agree (self-destruct in the Bunker)"),
        "V": E(True, "high", "p300 hap 'バッドエンド_ハッキングを行わない' (not hacking): Bg6001.startCountDown, "
               "conditions TOWER_NOTHACKING_30/60/120/180 (seconds) -> Ending_V.",
               "ph3/p300 250/260_CD (17-01, tower hack with Devola & Popola)", "agree (don't hack the tower)"),
        "W": E(True, "medium", "exe game-over handler 0x83dc4b: if [0x11eac20] == 0 -> Ending_W. pf30 comment: AB "
               "prologue, die at the Abandoned Factory.", "prologue p100 (per pf30 comment)",
               "agree (die in the prologue)", "no ContinueState.setBadEnd 0 found in hap/scripts of ph*/phf/st*/"
               "quest/core: how state 6/value 0 is reached in the prologue was not traced"),
        "X": E(True, "high", "p300 hap 'バッドエンド', group '50_10_ハイキョ都市_A2バトル': waits for event ev0841, "
               "area (142.9, -20.8, -117.8) -> Ending_X.", "ph3/p300 50_10_CD_Ruined_City_A2Come_2B (11-06)",
               "agree (A2 runs away from infected 2B)"),
        "Y": E(True, "high", "quest/q900 (Emil's Determination) hap '進行制御(11)': Emil Em8800 forms 2/3 then "
               "'条件コマンド_自爆モードへ' (to self-destruct mode); '条件コマンド_失敗' (fail) on Em8800 state "
               "FINAL_BOMB enables hap 'ゲームオーバー' (q900/RUN_2, BGM_Player_Die) -> Ending_Y; STOP_BOMB -> "
               "'_成功' -> q900/CLR.", "quest/q900, Desert boss area (~-792, -21, -1058)",
               "agree with web (let Emil self-destruct); pf30 comment says 'flee during the last Emil fight'",
               kind="hidden"),
        "Z": E(True, "high", "quest/q910 hap 'バッドエンド判定' (bad-end check): '条件ブロック_パスカル死んだ？' (is "
               "Pascal dead?), area (224.9, -2.4, 592.5) OUTSIDE -> 'フェーズジャンプ_パスカル殺害後のバッドエンド' "
               "(bad end after killing Pascal) -> Ending_Z.", "quest/q910, outside the Resistance Camp (14-01 A2)",
               "agree (kill Pascal outside the camp)"),
    })


_interp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "research"))
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    res = build(out, a.raw)
    (out / "endings_triggers.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", sum(1 for e in res["endings"] if e["trigger_sources"]), "/ 26 lettres avec source")


if __name__ == "__main__":
    main()
