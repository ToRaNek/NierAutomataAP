"""Gap 4 : objets cles (A170 Scanner, Elevator Key / ascenseurs). Lecture seule (exe + CPK via le cache).

    python tools/logic_gaps_keyitems.py [--out FICHIER.json] [--no-wd]

run() -> dict. Un .dat a la fois (world_positions.members), un Collector par fichier (pas d'index global).
Partie exe : faits verifies par lecture des octets (tables de sauts, chaines, RTTI) ; partie donnees : scripts
mruby et placements hap.pak/grp.pak qui citent le Scanner, la cle d'ascenseur, la boutique shop_Upgrade ou
l'entite ascenseur ba0200.
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
import extract_research as er  # noqa: E402
import mruby  # noqa: E402
import resolve_quests  # noqa: E402
import world_positions as wp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"
IMG = 0x140000000

NEEDLES = ("sonar", "Sonar", "soner", "sccaner", "mallKey", "ElevatorUnlock", "Shop_upgrade", "Elevator",
           "elevator", "Wev_lock", "CC_Opening")
FILE_RE = re.compile(r"((ph\w|quest|st\d|core|novel)/[^/]+\.dat|wd[1-5a]/g[0-9a-f]+\.dat)$")


# ============================================================================ exe
def _exe():
    import xref
    return xref


def _cstr(x, rva, n=64):
    o = x.rva2off(rva)
    if o is None:
        return None
    s = x.D[o:o + n].split(b"\0")[0]
    return s.decode("latin1") if len(s) >= 3 and all(32 <= c < 127 for c in s) else None


def _lea_target(x, rva):
    """lea r64, [rip+disp32] (48/4C 8D xx) a l'adresse rva -> cible."""
    o = x.rva2off(rva)
    b = x.D[o:o + 7]
    if b[0] in (0x48, 0x4C) and b[1] == 0x8D:
        return rva + 7 + struct.unpack_from("<i", b, 3)[0]


def _rtti_name(x, q):
    r = q - IMG
    o = x.rva2off(r) if 0 < r < 0x7FFFFFFF else None
    if o is None:
        return None
    sig, _offs, _cd, td, _chd, selfr = struct.unpack_from("<IIIIII", x.D, o)
    if sig != 1 or selfr != r:
        return None
    to = x.rva2off(td)
    return x.D[to + 16:to + 120].split(b"\0")[0].decode("latin1")


def _vtable_class(x, slot_rva):
    a = slot_rva
    for _ in range(400):
        q = struct.unpack_from("<Q", x.D, x.rva2off(a - 8))[0]
        n = _rtti_name(x, q)
        if n:
            return {"vtable": hex(a), "slot": (slot_rva - a) // 8, "class": n}
        a -= 8


def exe_facts() -> dict:
    x = _exe()
    D = x.D
    out = {}
    # --- chaine item_uq_mallKey et ses 2 references (lea rdx) dans la fonction de mise a jour de l'ascenseur
    s_off = D.find(b"item_uq_mallKey\0")
    s_rva = x.off2rva(s_off)
    refs = [(k, r) for k, r in x.refs(s_rva)]
    out["mallKey_string"] = hex(s_rva)
    out["mallKey_refs"] = [{"kind": k, "rva": hex(r), "function": hex(x.func_of(r)[0])} for k, r in refs]
    # --- table de sauts : id d'ascenseur (1..12) -> nom de variable de deblocage (fonction 0x8291c0)
    jt = 0x82AB18
    unlock = {}
    for i in range(12):
        tgt = struct.unpack_from("<I", D, x.rva2off(jt) + 4 * i)[0]
        lt = _lea_target(x, tgt)
        nm = _cstr(x, lt) if lt else None
        if tgt == 0x82976B:  # cible commune = pas de variable de deblocage
            nm = None
        elif nm is None:
            # cas 8/9/10 : test d'une variable Serious_* (lea rcx) puis lea r12 <X>_C_ElevatorUnlock
            o = x.rva2off(tgt)
            blk = D[o:o + 0x100]
            m1 = re.search(rb"\x48\x8D\x0D", blk)
            m2 = re.search(rb"\x4C\x8D\x25", blk)
            test = _cstr(x, _lea_target(x, tgt + m1.start())) if m1 else None
            var = _cstr(x, _lea_target(x, tgt + m2.start())) if m2 else None
            nm = {"unlock_var": var, "also_tests": test, "and_tests": "Runaway"}
        unlock[i + 1] = nm
    out["elevator_unlock_vars"] = unlock
    # --- verification des octets cle (cmp [rbx+8],0xc avant le test mallKey)
    o = x.rva2off(0x8345EA)
    out["mallKey_test_requires_elevator_id_12"] = D[o:o + 4] == bytes.fromhex("837b080c")
    # --- classes RTTI
    out["classes"] = {
        "LoopElevatorAction (hap, appelle 0x810730 = mise en place)": _vtable_class(x, 0xC43C08),
        "ElevatorAction (hap)": _vtable_class(x, 0xC43B88),
        "Ba0200 (entite ascenseur)": _vtable_class(x, 0xC565E8),
        "BehaviorElevDoor": _vtable_class(x, 0xC5A170),
    }
    # --- fabrique : objId 0xf0200 (ba0200) -> createFn -> vtable Ba0200
    fo = x.rva2off(0xF456A0)
    for i in range(0x46F):
        oid = struct.unpack_from("<I", D, fo + i * 0x28)[0]
        if oid == 0xF0200:
            fn = struct.unpack_from("<Q", D, fo + i * 0x28 + 8)[0] - IMG
            out["factory_ba0200"] = {"index": i, "createFn": hex(fn)}
    # --- id d'ascenseur = [Ba0200 + 0x590] (copie en [mgr+8] par 0x810730 a 0x8109be)
    o = x.rva2off(0x8109BE)
    out["elevator_id_from_ba0200_0x590"] = D[o:o + 9] == bytes.fromhex("8b9090050000895708")
    # --- Scanner : aucune chaine skill_act_sonar dans l'exe (remise par donnees)
    out["exe_has_skill_act_sonar_string"] = D.find(b"skill_act_sonar") >= 0
    out["exe_isActiveSkillSonar"] = hex(x.off2rva(D.find(b"isActiveSkillSonar"))) if D.find(b"isActiveSkillSonar") >= 0 else None
    return out


# ============================================================================ donnees
def _crc_dict() -> dict:
    names = set()
    rf = json.loads((RESEARCH / "routes_full.json").read_text(encoding="utf-8"))

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and k in ("subphase", "name", "sub_phase"):
                    names.add(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(rf)
    del rf
    names.update(["Route/A", "Route/B", "Route/C", "Route/D", "PL/2B", "PL/9S", "PL/A2"])
    for n in range(1, 8):
        names.add(f"Shop_upgrade/{n}")
    return {zlib.crc32(n.encode()): n for n in names}


def _chain(col, name, gid, crc):
    out = []
    seen = set()
    while gid and gid not in ("0x0", "0xffffffff") and gid not in seen:
        seen.add(gid)
        g = col.groups.get((name, gid))
        if not g:
            out.append({"group_id": gid, "missing": True})
            break
        toks = []
        for c, i in g["tokens"]:
            try:
                toks.append({"kind": c, "id": i, "name": crc.get(int(i, 16))})
            except (TypeError, ValueError):
                toks.append({"kind": c, "id": i})
        out.append({"group": g["name"], "group_id": gid, "attribute": g["attribute"], "tokens": toks})
        gid = g["parent"]
    return out


def _method_dump(root, names, want):
    """Methodes `want` -> liste d'appels (nom, arguments constants) dans l'ordre."""
    res = {}
    for r in mruby.walk(root):
        m = names.get(id(r))
        if m not in want:
            continue
        seq = []
        ins = list(r.ins())
        for k, (op, a, b, c, bx, sbx) in enumerate(ins):
            if op in ("SEND", "FSEND", "SENDB"):
                args = []
                for j in range(k - 1, -1, -1):
                    op2, a2, b2, c2, bx2, sbx2 = ins[j]
                    if a2 == a + 1 and op2 in ("STRING", "LOADSYM", "LOADI"):
                        args.append(r.pool[bx2] if op2 == "STRING" else (":" + str(r.syms[bx2]) if op2 == "LOADSYM" else sbx2))
                        break
                    if a2 == a and op2 not in ("LOADSELF",):
                        break
                seq.append([r.syms[b]] + args)
        res[m] = seq
    return res


def scan_files(no_wd=False) -> dict:
    crc = _crc_dict()
    names = sorted(n for n in er.all_names() if FILE_RE.search(n) and (not no_wd or not n.startswith("wd")))
    hits = {"scripts": [], "ba0200": [], "hap_values": [], "files_scanned": len(names), "errors": []}
    vocab = wp.Vocab()
    for name in names:
        col = wp.Collector()
        col.vocab = vocab
        try:
            col.process_file(name)
        except Exception as ex:  # noqa: BLE001
            hits["errors"].append([name, str(ex)])
            continue
        # scripts (via actions) : chaines/symboles contenant les aiguilles
        d = None
        for s in col.scripts:
            info = s["info"]
            strs = set(info.get("strings", ())) | set(info.get("syms", ()))
            found = sorted(t for t in strs if any(nd in t for nd in NEEDLES))
            rew = info.get("rewards", [])
            if not found and not ({"105", "224"} & set(rew)):
                continue
            if d is None:
                d = wp.members(name)
            ms = {m: sorted(st) for m, st in info.get("method_strings", {}).items()
                  if any(any(nd in t for nd in NEEDLES) for t in st) or {"105", "224"} & set(st)}
            dump = {}
            if s["script_member"] in d:
                root = mruby.parse(d[s["script_member"]])
                mn = resolve_quests.method_names(root)
                dump = _method_dump(root, mn, set(ms))
            hits["scripts"].append({"file": name, "script": s["script_member"], "hap": s["hap"], "action": s["action"],
                                    "variables": s["variables"], "needles": found, "rewards": rew,
                                    "methods": {m: {"strings": st, "calls": dump.get(m)} for m, st in ms.items()},
                                    "group_chain": _chain(col, name, s["group"], crc)})
        # entites : ba0200 (ascenseur) et toute valeur de parametre qui cite les aiguilles
        for ents in col.by_id.values():
            for e in ents:
                pv = " ".join(str(v) for v in e["params"].values() if v)
                if e["objId"] == "ba0200" or any(nd in pv for nd in NEEDLES):
                    rec = {k: e.get(k) for k in ("file", "member", "hap", "action", "entity_id", "objId", "position",
                                                 "rotation", "params", "alias", "setType", "comment")}
                    rec["group_chain"] = _chain(col, name, e["group"], crc)
                    (hits["ba0200"] if e["objId"] == "ba0200" else hits["hap_values"]).append(rec)
        del col, d
    return hits


def tables() -> dict:
    """DQR / BoxData / drops / ShopInfoTable : ou apparait l'id 2024 (Scanner) et item_uq_mallKey."""
    out = {}
    v = er.dat_member("core/coregm.dat", "QuestRewordData.drp")
    _m, _f, offA, szA, _szB, nA, _nB = struct.unpack_from("<4sfIIIHH", v)
    offB = offA + szA * nA
    for i in range(nA):
        rid, st, ni, nm, ne, *_r = struct.unpack_from("<HHHHHBBBB", v, offA + i * szA)
        ents = [struct.unpack_from("<II", v, offB + 8 * (st + j)) for j in range(ni)]
        for iid, w in ents:
            if iid == 2024:
                out.setdefault("dqr_2024", []).append({"reward_id": rid, "weight": w})
    for f in ("BoxData.drp", "CommonEmDropData.drp", "UniqueEmDropData.drp"):
        b = er.dat_member("core/coregm.dat", f)
        _m, _f, offA, szA, _szB, nA, nB = struct.unpack_from("<4sfIIIHH", b)
        offB = offA + szA * nA
        out[f + "_has_2024"] = any(struct.unpack_from("<I", b, offB + 8 * j)[0] == 2024 for j in range(nB))
    shops = json.loads((RESEARCH / "shops.json").read_text(encoding="utf-8"))["shops"]
    for s in shops:
        for it in s.get("items", []):
            if it.get("unique_id") in (2024,) or it.get("internal_name") in ("skill_act_sonar", "item_uq_mallKey"):
                out.setdefault("shops", []).append({"shop": s["internal_name"], "state_names": s.get("state_names"),
                                                    "item": it["internal_name"], "states": it.get("states")})
    return out


def statebind(needles=("Shop_upgrade", "ShoppingMall_ElevatorUnlock", "ElevatorUnlock", "sonar")) -> list:
    """core/corehap.dat:core_hap.pak, hap 'StateBind' : par sous-phase, listes StateOn/StateOff (une ligne par
    etat, '[condition] *etat'). Garde les lignes qui contiennent les aiguilles."""
    import cpk
    b = wp.members("core/corehap.dat")["core_hap.pak"]
    v = wp.Vocab()
    out = []
    for t in cpk.pak_yax(b):
        if not any("[Route/A] *Shop_upgrade" in x for _i, _t, x in t):
            continue
        cur = key = None
        for ind, tag, val in t:
            nm = v.name(tag)
            if ind == 3 and nm == "h_0389b783":
                cur = val
            elif ind == 4 and nm == "h_0389b783":
                key = val
            elif ind == 4 and nm == "value":
                ls = [ln for ln in val.split("\n") if any(n in ln for n in needles)]
                if ls:
                    out.append({"subphase": cur, "list": key, "lines": ls})
    return out


def raw_groups(b: bytes, vocab) -> dict:
    """Bloc de groupes d'un .pak, y compris NON compresse (taille stockee = taille decompressee, ex. qb95) :
    (world_positions.pak_groups lit maintenant aussi ce format via cpk.pak_group_block.)"""
    import cpk
    _a, usz, off = struct.unpack_from("<III", b, 0)
    csz = struct.unpack_from("<I", b, off)[0]
    try:
        raw = zlib.decompress(b[off + 4:off + 4 + csz])
    except zlib.error:
        raw = b[off:off + usz]
    out, cur = {}, None
    for ind, tag, val in cpk.yax(raw):
        nm = vocab.name(tag)
        if ind == 0 and nm == "group":
            cur = {"tokens": []}
        elif cur is not None and ind == 1 and nm in ("id", "name", "parent", "attribute"):
            cur[nm] = val
            if nm == "id":
                out[val] = cur
        elif cur is not None and ind == 3 and nm in ("code", "id"):
            if nm == "code":
                cur["tokens"].append({"kind": val})
            else:
                cur["tokens"][-1]["id"] = val
    return out


def mall_elevator() -> dict:
    """quest/qb95 (ascenseur id 12 + point 'utiliser la cle') et quest/q330 (etats RUN_5 / DONE)."""
    d = wp.members("quest/qb95.dat")
    vocab = wp.Vocab()
    names = {zlib.crc32(f"q330/{s}".encode()): f"q330/{s}" for s in
             [f"RUN_{i}" for i in range(1, 10)] + ["DONE", "FIN", "CLR"]}
    groups = raw_groups(d["qb95_hap.pak"], vocab)
    for g in groups.values():
        for t in g["tokens"]:
            t["name"] = names.get(int(t.get("id", "0"), 16))
    col = wp.Collector()
    col.process_file("quest/qb95.dat")
    ents = []
    for es in col.by_id.values():
        for e in es:
            ents.append({k: e.get(k) for k in ("objId", "entity_id", "position", "hap", "action", "setType", "alias",
                                               "group")})
    return {"qb95_groups": groups, "qb95_entities": ents}


def summary(r: dict) -> dict:
    scanner_calls = [s for s in r["data"]["scripts"] if "105" in s["rewards"]]
    shop_sb = [x for x in r["statebind"] if any("Shop_upgrade" in ln for ln in x["lines"])]
    elev12 = [e for e in r["mall_elevator"]["qb95_entities"] if e["objId"] == "ba0200"]
    key_pt = [e for e in r["mall_elevator"]["qb95_entities"] if e["objId"] == "bga102"]
    return {
        "A170_Scanner": {
            "confidence": "high",
            "grant_1": {"how": "getReWard('105') (DQR 105 = 2024 skill_act_sonar x1)",
                        "script": [(s["file"], s["script"], s["hap"], s["action"]) for s in scanner_calls],
                        "method": "dp_ans1 (choix 1 du dialogue Devola/Popola dp_talk1/dp_talk2 ; choix 2 reboucle)",
                        "npc": "Devola pl1040 / Popola pl1050, Camp de la Resistance st1/r110 (269.3, 9.5, 666.3)",
                        "when": "groupe 'A(Bルートは通らない)' sous la sous-phase 100_A_Submerge_City_2B "
                                "(route A ch 08-01 '2B Searches for 9S') : route A uniquement"},
            "grant_2": {"how": "boutique shop_Upgrade (PNJ Bunker bk_npc_ns1, pl2060), objet en vente aux etats "
                               "Shop_upgrade/3 et /4", "states_set_by_StateBind": shop_sb},
            "not_found_in": "BoxData, CommonEmDropData, UniqueEmDropData, addItem des scripts, exe (pas de chaine "
                            "skill_act_sonar)"},
        "Elevator_Key": {
            "confidence": "high (code + donnees) ; semantique exacte de 0x8c76b0 (type d'invite 3/4) = medium",
            "exe": "0x8344b0 (appele par 0x8291c0 = mise a jour du gestionnaire global d'ascenseur RVA 0x13df730, "
                   "appele par 0x763450) : si ascenseur verrouille ([mgr+0x1c]!=0, lockEv 0x800b70 / unlockEv "
                   "0x801080) et id [mgr+8]==12, count(item_uq_mallKey)>0 (0x7e3210 nom->id, 0x7e3b90 nombre) "
                   "-> pas d'appel 0x8c76b0(obj,1) (invite 'verrouille'). id = setType de l'entite Ba0200 "
                   "([ent+0x590], copie a 0x8109be par 0x810730, appelee par hap::LoopElevatorAction).",
            "elevator_12": elev12, "unlock_var_12": "ShoppingMall_ElevatorUnlock (scene state teste par 0x8291c0)",
            "key_use_point": key_pt,
            "data_gate": "qb95 hap '鍵の使用' (groupe 'エレベーターの鍵を開ける', jeton q330/RUN_5) place bga102 "
                         "'key' ; q330 key_ON_CHECK_ev0 -> set_scene_state ShoppingMall_ElevatorUnlock. "
                         "q330 RUN_5 est pose par flower_ON_CHECK_run_N (4e Lunar Tear), meme script que finish "
                         "-> getReWard 224 (Elevator Key). StateBind remet ShoppingMall_ElevatorUnlock si q330_DONE.",
            "ap_note": "Le verrou reel est l'etat q330/RUN_5 -> ShoppingMall_ElevatorUnlock, pas la possession de "
                       "la cle (l'exe ne teste la cle que pour l'invite)."},
    }


def run(no_wd=False) -> dict:
    r = {"_source": "tools/logic_gaps_keyitems.py", "exe": exe_facts(), "tables": tables(),
         "statebind": statebind(), "mall_elevator": mall_elevator(), "data": scan_files(no_wd)}
    r["summary"] = summary(r)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-wd", action="store_true")
    a = ap.parse_args()
    res = run(a.no_wd)
    out = Path(a.out) if a.out else Path(__file__).resolve().parent / "_lg_keyitems.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ecrit", out, "scripts", len(res["data"]["scripts"]), "ba0200", len(res["data"]["ba0200"]))


if __name__ == "__main__":
    main()
