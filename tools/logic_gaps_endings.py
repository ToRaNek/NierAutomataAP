"""Lacunes logiques : fins W / E (invite du Pod 153) / saut fin B -> generique, et C vs D.

LECTURE SEULE (CPK via le cache de extract_research, exe via xref/capstone). Faible RAM : un .dat a la fois.
Usage : python tools/logic_gaps_endings.py [--out FICHIER.json] [--flow ph3/p300.dat REGEX]
`run()` -> dict (utilise par tools/logic_gaps.py).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import rf_endings as rf  # noqa: E402

K_NAME, K_ENTRY = "0x0389b783", "0x22b35429"  # balises YAX de la table core_hap 'StateBind' / 'SceneState'

_T = None


def T():
    global _T
    if _T is None:
        _T = rf.tag_names()
    return _T


# ------------------------------------------------------------------------------------------- hap
def file_flow(name: str, pat: str | None = None, with_groups=True):
    """Toutes les actions des hap d'un .dat : hap, groupes (jetons de sous-phase), nom, commandes, saut, script,
    references (puid). `pat` filtre (regex sur le nom du hap / de l'action / commandes / cible)."""
    tt = T()
    SP = rf.subphase_hashes()
    d = cpk.dat_files(er.game_file(name))
    haps, groups = [], []
    for k, v in d.items():
        if not k.endswith(".pak"):
            continue
        if k.endswith("_hap.pak"):
            groups += rf.group_table(v, tt)
        try:
            for t in cpk.pak_yax(v):
                h = rf.tree(t, tt)
                h["member"] = k
                haps.append(h)
        except Exception:
            continue
    gidx = {rf.ihex(rf.kv(g, "id")): g for g in groups}
    ids = {}
    for top in haps:
        if True:
            hn = rf.kv(top, "name")
            ids[rf.ihex(rf.kv(top, "id"))] = f"hap:{hn}"
            for a in top["k"]:
                if a["t"] == "action":
                    ids[rf.ihex(rf.kv(a, "id"))] = f"{hn}/{rf.kv(a, 'name')}"

    def chain(gid):
        out, seen = [], set()
        while gid in gidx and gid not in seen:
            seen.add(gid)
            g = gidx[gid]
            toks = []
            tk = rf.kid(g, "tokens")
            for v in (tk["k"] if tk else []):
                if v["t"] != "value":
                    continue
                c, i = rf.ihex(rf.kv(v, "code")), rf.ihex(rf.kv(v, "id"))
                if c == rf.TOK_SUBPHASE:
                    toks.append(SP.get(i, (None, f"0x{i:08x}"))[1])
                elif c == rf.TOK_SCENE:
                    toks.append(f"state:0x{i:08x}")
            out.append({"group": rf.kv(g, "name"), "tokens": toks, "attribute": rf.kv(g, "attribute")})
            gid = rf.ihex(rf.kv(g, "parent"))
        return out

    rx = re.compile(pat) if pat else None
    out = []
    for top in haps:
        if True:
            hn = rf.kv(top, "name")
            gch = chain(rf.ihex(rf.kv(top, "group"))) if with_groups else []
            for a in top["k"]:
                if a["t"] != "action":
                    continue
                s = rf.action_summary(a, ids)
                scr = rf.kid(a, "script")
                if scr is not None and rf.kv(scr, "id"):
                    s["script"] = f"{name.split('/')[1][:-4]}_{rf.ihex(rf.kv(scr, 'id')):x}_scp.bin"
                rec = {"member": top["member"], "hap": hn, **s, "groups": gch}
                if rx and not rx.search(json.dumps(rec, ensure_ascii=False)):
                    continue
                out.append(rec)
    return out


def script_strings(name: str, member: str, pat: str = "."):
    b = cpk.dat_files(er.game_file(name)).get(member) or b""
    rx = re.compile(pat)
    return [m.group().decode("latin-1") for m in re.finditer(rb"[\x20-\x7e]{3,}", b) if rx.search(m.group().decode())]


# ------------------------------------------------------------------------------------ StateBind
def state_bind(phase_filter=None):
    """core/corehap.dat:core_hap.pak, arbre 'StateBind' : phase -> sous-phase -> {StateOn, StateOff, QuestOn,...}.
    Semantique des prefixes (exe 0x354bb0 / 0x354f60) : 'X' ou '*X' ajoute une plage commencant a cette sous-phase
    (0x341ac0) ; '!X' ferme la plage ouverte (fin = indice de cette sous-phase, 0x354ec1..0x354f1f) ;
    '[cond] X' = conditionnel."""
    tt = T()
    trees = cpk.pak_yax(cpk.dat_files(er.game_file("core/corehap.dat"))["core_hap.pak"])
    out = {}
    for t in trees:
        root = rf.tree(t, tt)
        if not root["k"] or rf.kv(root["k"][0], "name") != "StateBind" and not any(
                n["t"] == "name" and n["v"] == "StateBind" for n in root["k"]):
            continue
        top = [n for n in rf.walk(root) if n["t"] == "0x857fe845"][0]
        for ph in top["k"]:
            if ph["t"] != K_ENTRY:
                continue
            pn = rf.kv(ph, K_NAME)
            if phase_filter and pn not in phase_filter:
                continue
            for sp in ph["k"]:
                if sp["t"] != K_ENTRY:
                    continue
                rec = {}
                for f in sp["k"]:
                    if f["t"] == K_ENTRY:
                        rec[rf.kv(f, K_NAME)] = [x for x in (rf.kv(f, "value") or "").strip('"').split("\n") if x]
                out.setdefault(pn, []).append((rf.kv(sp, K_NAME), rec))
        break
    return out


def state_ranges(sb, states):
    """Plages (ordre du fichier) ou chaque etat est mis (StateOn) / force a faux (StateOff)."""
    res = {}
    for ph, rows in sb.items():
        for idx, (sub, rec) in enumerate(rows):
            for lst in ("StateOn", "StateOff"):
                for line in rec.get(lst, []):
                    cond = None
                    m = re.match(r"\[([^\]]*)\]\s*(.*)", line)
                    if m:
                        cond, line = m.group(1), m.group(2)
                    base = line.lstrip("*!")
                    if base not in states:
                        continue
                    key = (base, lst)
                    lst_r = res.setdefault(key, [])
                    if line.startswith("!"):
                        for r in reversed(lst_r):
                            if r["end"] is None and r["open"]:
                                r["end"] = f"{ph}:{sub}"
                                break
                        else:
                            lst_r.append({"start": None, "end": f"{ph}:{sub}", "open": False, "cond": cond})
                    else:
                        lst_r.append({"start": f"{ph}:{sub}", "end": None, "open": line.startswith("*"),
                                      "cond": cond})
    return {f"{k[0]} [{k[1]}]": v for k, v in res.items()}


def scene_state_desc(names):
    """Table 'SceneState' de core_hap : nom d'etat -> description japonaise."""
    tt = T()
    trees = cpk.pak_yax(cpk.dat_files(er.game_file("core/corehap.dat"))["core_hap.pak"])
    out = {}
    for t in trees:
        root = rf.tree(t, tt)
        if not any(n["t"] == "name" and n["v"] == "SceneState" for n in root["k"]):
            continue
        for n in rf.walk(root):  # plusieurs arbres 'SceneState' (11, 15..19) : tous lus
            if n["t"] == K_ENTRY and rf.kv(n, K_NAME) in names:
                out.setdefault(rf.kv(n, K_NAME), rf.kv(n, "value"))
    return out


# ------------------------------------------------------------------------------------------- exe
def _exe():
    import xref
    return xref


def exe_strings_refs(strings):
    xref = _exe()
    out = {}
    for s in strings:
        b = s.encode() + b"\0"
        lst = []
        for m in re.finditer(re.escape(b), xref.D):
            if m.start() and xref.D[m.start() - 1] != 0:
                continue
            r = xref.off2rva(m.start())
            lst.append({"rva": f"0x{r:x}", "refs": [f"{k}@0x{a:x}" for k, a in xref.refs(r)][:16]})
        out[s] = lst
    return out


def disasm(a, b):
    import capstone
    xref = _exe()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    o = xref.rva2off(a)
    lines = []
    for i in md.disasm(xref.D[o:o + (b - a)], a):
        lines.append(f"{i.address:x}: {i.mnemonic} {i.op_str}")
    return lines


def verify_bytes(rva, hexstr):
    xref = _exe()
    o = xref.rva2off(rva)
    want = bytes.fromhex(hexstr)
    return xref.D[o:o + len(want)] == want


# ---------------------------------------------------------------------------------------- mruby
def script_methods(name: str, member: str):
    """Methodes d'un script mruby : nom -> liste d'appels (SEND) avec arguments constants (chaines courtes)."""
    import mruby
    import resolve_quests as rq
    b = cpk.dat_files(er.game_file(name)).get(member)
    if not b:
        return {}
    root = mruby.parse(b)
    names = rq.method_names(root)
    out = {}
    for r in mruby.walk(root):
        ins = list(r.ins())
        seq = []
        for k, (op, a, bb, c, bx, sbx) in enumerate(ins):
            if op in ("SEND", "FSEND", "SENDB"):
                args = []
                for reg in range(a + 1, a + 1 + c):
                    val = None
                    for j in range(k - 1, -1, -1):
                        op2, a2, b2, c2, bx2, sbx2 = ins[j]
                        if op2 in ("JMP", "JMPIF", "JMPNOT"):
                            break
                        if a2 != reg:
                            continue
                        if op2 == "STRING":
                            val = r.pool[bx2]
                        elif op2 == "LOADI":
                            val = sbx2
                        elif op2 == "LOADSYM":
                            val = ":" + str(r.syms[bx2])
                        elif op2 in ("LOADT", "LOADF"):
                            val = op2 == "LOADT"
                        elif op2 == "SEND":
                            val = f"<{r.syms[b2]}()>"
                        break
                    if isinstance(val, str) and len(val) > 60:
                        val = val[:57] + "..."
                    args.append(val)
                seq.append(f"{k}:{r.syms[bb]}({', '.join(map(repr, args))})")
            elif op in ("JMP", "JMPIF", "JMPNOT"):
                seq.append(f"{k}:{op}->{k + sbx}")
            elif op == "RETURN":
                seq.append(f"{k}:RETURN")
        out.setdefault(names.get(id(r)) or "?", []).append(seq)
    return out


def script_texts(name: str, member: str):
    """Constantes de texte d'un script (STRING x9 langues, ARRAY, SETCONST cle) -> {cle: anglais (indice 1)}."""
    import mruby
    b = cpk.dat_files(er.game_file(name)).get(member)
    out = {}
    if not b:
        return out
    for r in mruby.walk(mruby.parse(b)):
        strs = []
        for op, a, bb, c, bx, sbx in r.ins():
            if op == "STRING":
                strs.append(r.pool[bx])
            elif op == "ARRAY":
                pass
            elif op == "SETCONST":
                if len(strs) >= 2:
                    out[r.syms[bx]] = strs[-8] if len(strs) >= 9 else strs[1]  # 9 langues, [1] = anglais
                strs = []
    return out


def script_flow(name: str, member: str):
    """Methode -> suite d'evenements : textes (cle + anglais), appels (SEND + args constants)."""
    import mruby
    import resolve_quests as rq
    texts = script_texts(name, member)
    b = cpk.dat_files(er.game_file(name)).get(member)
    root = mruby.parse(b)
    names = rq.method_names(root)
    meth = script_methods(name, member)
    out = {}
    for r in mruby.walk(root):
        n = names.get(id(r))
        if not n:
            continue
        ev = []
        for op, a, bb, c, bx, sbx in r.ins():
            if op in ("GETCONST", "LOADSYM") and r.syms[bx] in texts:
                ev.append(f"[{r.syms[bx]}] {texts[r.syms[bx]]}")
        out[n] = {"texts": ev, "calls": [x for seq in meth.get(n, []) for x in seq if "JMP" not in x]}
    return out


# ------------------------------------------------------------------------------- verification exe
def insn(rva):
    """Une instruction a `rva` : (mnemonique, operandes, cible rip/call, chaine a la cible)."""
    import capstone
    xref = _exe()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    o = xref.rva2off(rva)
    i = next(md.disasm(xref.D[o:o + 16], rva))
    tgt = s = None
    m = re.search(r"\[rip \+ (0x[0-9a-f]+)\]", i.op_str)
    if m:
        tgt = rva + i.size + int(m.group(1), 16)
        to = xref.rva2off(tgt)
        if to:
            b = xref.D[to:to + 64].split(b"\0")[0]
            s = b.decode("latin-1") if b and all(32 <= c < 127 for c in b) else None
    elif i.mnemonic in ("call", "jmp") and i.op_str.startswith("0x"):
        tgt = int(i.op_str, 16)
    return i.mnemonic, i.op_str, tgt, s


# (rva, attendu : sous-chaine de l'instruction / chaine pointee / cible, sens)
EXE_EVIDENCE = {
    "W_gameover_kind_0x7e00a0": [
        (0x7E00B9, "RobotMt_Prologue/A", "SceneState teste (0x150e70 + 0x495a70 = has)"),
        (0x7E011A, "tutorial_STG", "idem"),
        (0x7E0179, "RobotMt_Boss/A", "idem"),
        (0x7E01D8, "tower_continue", "-> type 4 (continue de la Tour)"),
        (0x7E0243, "Collapse_BK", "-> type 5"),
        (0x7E02C9, "0x1029c30", "un des 3 etats : [0x1029c30] < 0 -> 7 (saut 0xf00 START), sinon 6 (fin speciale)"),
    ],
    "W_gameover_state_machine_0x83d800": [
        (0x83D804, "0x11eac1c", "etat du game over = [0x11eac1c] (table de sauts 0x83dd58, etats 1..8)"),
        (0x83D91C, "0x7e00a0", "etat 2 : si [0x11eac20]==0 -> etat = 0x7e00a0() et [0x11eac20]=0"),
        (0x83DC4B, "0x11eac20", "etat 6 : [0x11eac20]==1 -> Ending_U, ==0 -> Ending_W (saut 0xf30)"),
        (0x83DC66, "Ending_U", ""),
        (0x83DCB8, "Ending_W", ""),
        (0x83DCC1, "START", "etat 7 : saut phase 0xf00 'START'"),
    ],
    "E_post_credits": [
        (0x85EA99, "BGM_Set_Sn_Ending_E", "BGM fin E"),
        (0x85EAC3, "rdx + 3", "0x89ae00(4) : titre CREDIT_END_TITLE_05 (E)"),
    ],
    "B_backtitle_0x85c271": [
        (0x85C271, "BackTitle_B", "pf10 BackTitle_B -> bit de fin 1 (0x9cbd90(1)), etat 9"),
        (0x85C288, "0x9cbd90", ""),
        (0x83DE77, "0x89ae00", "sequence 0x83dd90 : 0x89ae00(1) = titre CREDIT_END_TITLE_02 (B)"),
    ],
    "CD_endroll_0x85c2bf": [
        (0x85C2BF, "EndRoll_CD", "EndRoll_CD : bit de fin 2 si Route/C, 3 si Route/D (Route/D jamais mis)"),
        (0x85C2DA, "Route/C", ""),
        (0x85C32B, "Route/D", ""),
        (0x85C768, "select/9S", "modele 0x21030 si select/9S, 0x21040 si select/A2"),
    ],
    "CD_credits_end_0x863730": [
        (0x86377A, "select/9S", "select/9S -> SceneState ending_C (0x354b20) + succes indice 0x10"),
        (0x8637D9, "ending_C", ""),
        (0x86381F, "rbp + 8", "ecx = 0x10 -> 0x9c6320/0x9c7250 (succes n 17)"),
        (0x863838, "select/A2", "select/A2 -> ending_D + succes indice 0x11"),
        (0x863893, "ending_D", ""),
        (0x8638D9, "0x11", "succes n 18"),
    ],
    "CD_reward_archive_0x863edc": [
        (0x863EDC, "select/A2", "archive 0x12016a (CORE_ARCHIVE_180_010 'Machine Research Report') si select/A2"),
    ],
    "ending_mask_0x9ccd50": [
        (0x9CCE7D, "0x14], 1", "ending_A -> bit 0x1"),
        (0x9CCF4D, "0x14], 2", "ending_B -> 0x2"),
        (0x9CD01D, "0x14], 4", "ending_C -> 0x4 (3e lettre)"),
        (0x9CD0ED, "0x14], 8", "ending_D -> 0x8"),
        (0x9CD1BD, "0x14], 0x10", "ending_CD -> 0x10 (E)"),
    ],
    "achievement_native_0x3aff50": [
        (0x3AFF8E, "%x", "MiscState.unlockAchievement N : sprintf('%x', N) puis strtol base 10 => '0x10' = 10 ; "
                         "indice = valeur-1 ; 1..12 debloque 0..indice"),
        (0x3B0025, "0x9c7250", ""),
    ],
    "credit_title_switch_0x9188fa": [
        (0x9188FA, "0x90", "UIEndRollRoute (RTTI .?AVUIEndRollRoute@@, ctor 0x9d1d50, UI id 0xff) : [ui+0x90] = "
                           "indice -> CREDIT_END_TITLE_%02d (indice+1) ; ecrit par 0x89ae00(indice)"),
    ],
}


def verify_exe():
    out = {}
    for k, lst in EXE_EVIDENCE.items():
        rows = []
        for rva, want, note in lst:
            try:
                mn, ops, tgt, s = insn(rva)
            except Exception as e:  # exe absent ou autre version
                rows.append({"rva": f"0x{rva:x}", "error": str(e), "verified": False})
                continue
            txt = f"{mn} {ops}"
            ok = want in txt or (s and want in s) or (tgt is not None and want == f"0x{tgt:x}")
            rows.append({"rva": f"0x{rva:x}", "insn": txt, "target": f"0x{tgt:x}" if tgt else None, "string": s,
                         "expect": want, "verified": bool(ok), "note": note})
        out[k] = rows
    return out


def achievements():
    t = er.english_texts()
    return {i: t[f"CORE_ACHIEVEMENT_HELP_{i:02d}"][0].replace("Description:\n", "")
            for i in range(1, 60) if f"CORE_ACHIEVEMENT_HELP_{i:02d}" in t}


def end_titles():
    t = er.english_texts()
    return {i: t[f"CREDIT_END_TITLE_{i:02d}"][0] for i in range(1, 27) if f"CREDIT_END_TITLE_{i:02d}" in t}


def _compact(rows, haps=None, subs=None):
    out = []
    for r in rows:
        toks = [t for g in r["groups"] for t in g["tokens"]]
        if haps and r["hap"] not in haps:
            continue
        if subs and not any(re.match(subs, t) for t in toks):
            continue
        e = {"hap": r["hap"], "action": r.get("name"), "group": r["groups"][0]["group"] if r["groups"] else None}
        if r.get("subPhase") and r["subPhase"] not in ('"invalid value"', '""'):
            e["jump"] = r["subPhase"] + (f" (phase {r['phase']})" if r.get("phase") else "")
        if r.get("commands"):
            e["commands"] = [f"{c['label']} {c['args'] or ''}".strip() for c in r["commands"]]
        if r.get("script"):
            e["script"] = r["script"]
        if r.get("conditions"):
            e["conditions"] = r["conditions"]
        if len(e) > 3 or re.search(r"配置_敵|ノベル|イベントの再生_ev12", e["action"] or ""):
            out.append(e)
    return out


# ------------------------------------------------------------------------------------------- run
W_STATES = ["RobotMt_Prologue/A", "RobotMt_Boss/A", "tutorial_STG"]


def run():
    sb = state_bind()
    ranges = state_ranges({k: v for k, v in sb.items() if k in ("p100", "p200", "p300")},
                          set(W_STATES) | {"Route/C", "Route/D", "select/9S", "select/A2", "ending_CD"})
    desc = scene_state_desc(set(W_STATES) | {"tower_continue", "Collapse_BK", "select/9S", "select/A2",
                                              "ending_C", "ending_D", "ending_CD", "Route/C", "Route/D"})
    p100 = file_flow("ph1/p100.dat")
    tut = [{"hap": r["hap"], "action": r.get("name"), "commands": r.get("commands"),
            "group_subphases": [t for g in r["groups"] for t in g["tokens"]][:3]}
           for r in p100 if "tutorial_STG" in json.dumps(r.get("commands"), ensure_ascii=False)]
    for m in ("p100_fa238e7c_scp.bin", "p100_c6ab1d8f_scp.bin", "p100_f633da63_scp.bin"):
        hap = [(r["hap"], [t for g in r["groups"] for t in g["tokens"]][:1]) for r in p100 if r.get("script") == m]
        for k, v in script_methods("ph1/p100.dat", m).items():
            for seq in v:
                for x in seq:
                    if "set_scene_state('tutorial_STG')" in x:
                        tut.append({"script": m, "hap": hap, "method": k, "call": x})
    del p100
    p300 = file_flow("ph3/p300.dat")
    p200 = file_flow("ph2/p200.dat")
    pf10 = file_flow("phf/pf10.dat", with_groups=False)
    pf31 = file_flow("phf/pf31.dat", with_groups=False)
    ach = achievements()
    titles = end_titles()
    exe = verify_exe()

    def flow_texts(f, m, keep=None):
        fl = script_flow(f, m)
        return {k: v for k, v in fl.items() if (keep is None or k in keep) and (v["texts"] or v["calls"])}

    return {
        "_source": "tools/logic_gaps_endings.py (lecture seule : core_hap.pak StateBind/SceneState, hap YAX p100/p200/"
                   "p300/pf10/pf31, scripts mruby, NieRAutomata.exe v1.04 via capstone). Traductions NON OFFICIELLES.",
        "W": {
            "status": "resolved",
            "confidence": "high (exe) / medium (bornes exactes des plages StateBind)",
            "trigger": "Game over (mort) pendant que l'un des etats SceneState RobotMt_Prologue/A, tutorial_STG ou "
                       "RobotMt_Boss/A est actif -> type de game over 6 avec valeur 0 -> saut pf30 Ending_W. Il "
                       "n'existe aucun setBadEnd 0 : 0 est la valeur par defaut ([0x11eac20] remis a 0 a l'etat 2, "
                       "0x83d91c). ContinueState.setBadEnd 1 (qb40, autodestruction au Bunker, natif 0x80e200) force "
                       "l'etat 6 avec 1 -> Ending_U. Si [0x1029c30] < 0 (drapeau global, 0 en jeu normal, mis a 0 a "
                       "l'init 0x75f592 ; meme test avant Ending_T et les succes) -> etat 7 = saut 'START' (0xf00).",
            "exe_flow": "0x83d800 (machine d'etats du game over, etat [0x11eac1c]) : 1 init -> 2 : 0x7e00a0() choisit "
                        "le type : 6/7 si RobotMt_Prologue/A | tutorial_STG | RobotMt_Boss/A ; 4 si tower_continue ; "
                        "5 si Collapse_BK (ou bit 0x10000000 de [0x1029b04]) ; sinon 3 (continue normal). "
                        "Etat 6 = 0x83dc4b.",
            "scene_state_descriptions_ja": desc,
            "statebind_ranges": {k: v for k, v in ranges.items() if any(s in k for s in W_STATES)},
            "statebind_semantics": "core/corehap.dat:core_hap.pak arbre 'StateBind' (phase -> sous-phase -> StateOn/"
                                   "StateOff/QuestOn/QuestOff/Item/Level). Exe 0x35b780 (lit 'StateBind'), 0x354bb0 : "
                                   "'X' / '*X' = nouvelle plage commencant a la sous-phase (0x341ac0), '!X' = ferme la "
                                   "plage ouverte de X a cette sous-phase (fin = indice, 0x354ec1..0x354f1f), "
                                   "'[cond] X' = conditionnel. Ordre = ordre du fichier pXXX_sub.bxm (A et B entrelaces). "
                                   "Application (RESOLU) : hap::scene_state::SubPhaseBind, fonction membre 0x31e0b0 "
                                   "(pointeur pose en 0xb80c1, foncteur vtable 0xc26888) appelee a chaque changement "
                                   "de sous-phase (phase, indice via 0x85deb0) : liste 'X' ([this+8]) = entrees dont "
                                   "debut == indice EXACT (cette sous-phase seule) ; liste '*X' ([this+0x38]) = "
                                   "debut <= indice ET (fin <= 0 ou indice <= fin) : la sous-phase du '!' est "
                                   "INCLUSE. 0x31dcf0 applique l'element (0 StateOn, 1 StateOff = reset 0x34f8e0, "
                                   "2/3 QuestOn/Off...). Les plages portent sur l'indice du fichier (A et B "
                                   "entrelaces) : une plage A qui se ferme sur une entree B inclut les entrees B "
                                   "intermediaires (ex. RobotMt_Boss/A 05_00_A..05_40_B couvre 05_10_B, 05_30_B, "
                                   "05_40_B).",
            "tutorial_STG": tut,
            "where_unofficial": "Prologue route A (2B) : vol STG 00_30..00_50_A (tutorial_STG, mis par les scripts de "
                                "dialogue STG1/2/3, efface en 00_50) ; usine a partir de 00_60_A_RobotM_Pro_Tutorial "
                                "(premier controle de 2B) jusqu'a 00_80_A INCLUS (0x31e0b0 : indice <= fin), 00_85_A..05_10_A, "
                                "05_20/05_30/05_40_A ; boss 05_00_A..05_40_A (RobotMt_Boss/A, ferme par '!' en 05_40_B). "
                                "Route B (9S) : RobotMt_Prologue/A force a faux (StateOff) -> pas de fin W. Efface "
                                "(StateOff) au debut de p200 00_AB_Ruined_City et p300 00_CD_Bunker_2B ; RobotMt_Boss/A "
                                "aussi en 10_A_bunker_Robot_Battle.",
            "resolved_2026_11_24": {
                "range_end": "borne de fin INCLUSE (SubPhaseBind 0x31e0b0 : debut <= i et (fin <= 0 ou i <= fin)) ; "
                             "00_80_A_RobotM_Pro_1stArea est dans RobotMt_Prologue/A. confidence: high.",
                "flag_0x1029c30": "un seul ecrivain dans tout l'exe : 0x75f592 (initialisation 0x75f250, a cote du "
                                  "chemin de donnees de developpement '%s:/project/PRJ_028/p2/win32/data') qui y "
                                  "ecrit ebx = 0 (xor ebx,ebx en 0x75f29b, chemins 0x75f2d4/0x75f309). ~60 lecteurs "
                                  "(UI 0x9c..., fins, succes) testent < 0. En version commerciale il vaut toujours 0 : "
                                  "drapeau de build/debug, l'etat 7 (saut START) est inatteignable. confidence: high.",
                "side_effect": "RobotMt_Boss/A (05_00_A..!05_40_B) s'applique aussi en entrant dans 05_10_B, 05_30_B, "
                               "05_40_B (route B) : une mort a ces sous-phases donnerait statiquement le type 6 "
                               "(fin W). Non verifie en jeu ; persistance des StateOn hors plage non tracee "
                               "(pas d'effacement explicite avant p200/p300 hors StateOff).",
            },
            "open": "persistance d'un StateOn apres la fin de sa plage (le reset n'est fait que par StateOff/"
                    "SceneStateSystem.reset) ; effet reel de RobotMt_Boss/A sur la route B.",
        },
        "E": {
            "status": "resolved",
            "confidence": "high",
            "path": [
                "Fin C ou D : p300 340_C (流れ(26), script p300_987be645) / 340_D (流れ(14), script p300_10112854) "
                "'フェーズジャンプ_TrueEnd' -> pf31 'start' si l'autre fin est deja vue (tests 'ending_D on?' / "
                "'ending_C on?'), sinon EndRoll_CD.",
                "pf31 (= p300 350_CD_TrueEnd_STG, StateOn ending_CD) hap 流れ(27) script pf31_d2ca712b (= "
                "p300_d2ca712b) '..M3060_S7500_GM_スタッフロールSTG' : methode global_start_text_a0 = Pod 153 "
                "'Requesting temporary halt to perform data check.' puis M3060_S7500_S0070_001_sele \"Accept the "
                "Pod's request?\" Oui/Non (texte UI equivalent CREDIT_DIALOG_CD 'Permit suspension requests from pods?').",
                "Non (global_start_text_n0/_n1) -> signal check_no : le generique continue sans STG, sortie "
                "'フェーズジャンプ_諦め' -> pf10 BackTitle_CD.",
                "Oui (global_start_text_y0) -> signal stop_roll, BGM_Stop_Ending, dialogue Pod 042/153 "
                "(S0080..S0300 'Knowing that, do you still wish for them to survive?') Oui/Non ; Oui (y1) -> signal "
                "question_yes -> STG du generique (auto_1_stg / step_0..2).",
                "Pendant la STG : mort -> stg_continue 'GIVE UP HERE?' / lose_0..4 ; continue_help 'RESCUE OFFER "
                "RECEIVED FROM <others>. ACCEPT OFFER?' (signal stg_help). Abandon -> 'フェーズジャンプ_諦め' -> pf10 "
                "BackTitle_CD. Reussite -> 'フェーズジャンプ_STGクリア' -> p300 360_CD_TrueEnd_FIN.",
                "360_CD_TrueEnd_FIN : p300 流れ(28) : script p300_7de5c329 (= pf10_7de5c329) "
                "'..M3060_S9000_GM_セーブデータ消去' + ev1270 + MiscState.unlockAchievement 0x19 (succes 19 'The Minds "
                "That Emerged') + saut START. Exe 0x85ea99 BGM_Set_Sn_Ending_E, 0x89ae00(4) = CREDIT_END_TITLE_05.",
                "Script de suppression : this_fin_start_a0 (Pod 153 : message aux autres joueurs ? 'I have something "
                "I want to say.' / 'Nope, nothing at all.' -> retour titre), puis global_pod_messageend_a0..y6 "
                "(6 confirmations Oui/Non, 'you will lose all of your save data') ; y6 -> signal pod_delete (exe "
                "'SaveDelete Fade', 0xceb2d0) ; global_pod_deleteend_a0 'All of your data has been deleted.' -> "
                "pod_finish. Non a une etape -> 'Understood. Returning to title screen.' (back_title).",
            ],
            "pf31_texts": flow_texts("phf/pf31.dat", "pf31_d2ca712b_scp.bin",
                                     {"global_start_text_a0", "global_start_text_y0", "global_start_text_n0",
                                      "global_start_text_y1", "global_stg_continue_a0", "global_continue_help_a0"}),
            "pf10_texts": flow_texts("phf/pf10.dat", "pf10_7de5c329_scp.bin"),
            "haps": {"pf31": _compact(pf31), "pf10": _compact(pf10), "p300_350_360": _compact(p300, subs=r"3[56]\d_")},
        },
        "B_credits_jump": {
            "status": "resolved",
            "confidence": "high (hap) / medium (titre B via la sequence 0x83dd90)",
            "path": "p200 200_70 '..M1090_S0320_GM_b' -> 200_80_AB_Ruined_City_end ; groupe B '80_HDイベント' hap "
                    "'イベント再生(2)' : evenement HD, MiscState.GAME_OFF 8/9/11/12/13 puis saut direct p300 "
                    "00_CD_Bunker_2B (pas de sous-phase EndRoll_B). p300 00_CD_Bunker_2B : hap 流れ(17) (groupes "
                    "'00_バンカー_束の間の休息' = repos au Bunker) : dialogues PNJ, evenements peva0003/ev0151, puis "
                    "'フェーズジャンプ_f10' -> pf10 BackTitle_B ('Bルート後、タイトル画面へ遷移'). pf10 hap 流れ(3) : "
                    "SceneStateSystem.set ending_B + MiscState.unlockAchievement 0x11 (succes 11 'A New Battle "
                    "Begins'). Exe 0x85c271 : BackTitle_B -> bit de fin 1 (0x9cbd90(1), 0x9cbdc0(1)), etat 9 ; la "
                    "sequence 0x83dd90 affiche 0x89ae00(1) = CREDIT_END_TITLE_02 'or not to [B]e'. La route C/D "
                    "reprend ensuite (sauvegarde) a 00_10_CD_Bunker_Hangar_2B (Route/C ouvert par StateBind).",
            "haps": {"p200_200_80": _compact(p200, subs=r"200_80"), "p300_flow17": _compact(p300, haps={"流れ(17)"}),
                     "pf10": _compact(pf10)},
        },
        "C_vs_D": {
            "status": "resolved (drapeaux internes) ; titre affiche de A/C/D non trace",
            "confidence": "high (donnees + exe)",
            "conclusion": "Choisir 9S (335_CD_Tower_sele9S : le joueur est 9S, 'オブジェ配置_敵A2' = A2 ennemie, "
                          "script M3060_S0820_GM_9S発狂) -> A2 vaincue -> 340_C_Tower_9Swin (StateOn select/9S, saut "
                          "'CEnd') -> pf10 EndRoll_CD ; a la fin du generique l'exe (0x863730) pose ending_C et le "
                          "succes n 17 'Leaving for the New World'. Choisir A2 (335_CD_Tower_seleA2, '敵9S') -> "
                          "340_D_Tower_A2win / 345_D_Tower_A2win_9Shack (select/A2, 'DEnd') -> ending_D, succes n 18 "
                          "'Beautiful World', archive 'Machine Research Report' (0x863edc). Le masque des fins "
                          "(0x9ccd50) code ending_C = 0x4 (3e fin = C), ending_D = 0x8 (D). Pour le jeu : 9S = C, "
                          "A2 = D, a l'inverse de web_reference.md (A2 -> C, 9S -> D).",
            "notes": [
                "'9Swin'/'A2win' = le personnage choisi (controle par le joueur) gagne le combat.",
                "Les deux branches sautent a EndRoll_CD ; l'exe 0x85c2bf pose le bit de fin 2 (C) si Route/C, 3 (D) "
                "si Route/D, mais Route/D n'est mis nulle part (StateBind : seulement '*Route/C' en "
                "00_10_CD_Bunker_Hangar_2B ; aucune chaine 'Route/D' dans hap/scripts ; l'exe ne fait que la tester) : "
                "la distinction vient de ending_C / ending_D poses en fin de generique (0x863730).",
                "Titre affiche : 0x89ae00 (UIEndRollRoute, [ui+0x90] -> CREDIT_END_TITLE_%02d) n'est appele qu'avec "
                "1 (B, 0x83de77), 4 (E, 0x85eac6) et l'indice des fins pf30 (0x862e2f) : les titres A/C/D ne passent "
                "pas par ce chemin. Verifie le 2026-11-24 : l'UI d'affichage (table CREDIT_END_TITLE_01..26 en "
                "0x91890a, indice [ui+0x90]) n'est alimentee que par 0x89ae00, dont les 4 appelants sont B "
                "(0x83de77), le game over (0x842973, indice [obj+0xc]), E (0x85eac6) et pf30 (0x862e2f). "
                "data/movie : 150 fichiers evNNNN.usm (aucun nom par fin, aucun flux de sous-titres @SBT) ; "
                "credit/credit_ver1.dat (creditSq.bxm = indices de sequence) et ui/ui_ending_us.dat (ending00NN.uid "
                "+ messending.mcd) ne lient pas un titre a un drapeau. Titre A/C/D = probablement integre au "
                "generique (EndRoll / EndRollShooting) : NON trace statiquement.",
                "Indices narratifs (evenements par branche, p300) : branche 9S gagnante 340_C_Tower_9Swin = "
                "ev1230 puis une des variantes ev1232..ev1235 'パス◯/×いく◯/×' (choix 'partir / ne pas partir' "
                "qui correspond a la fin ou 9S part avec l'arche) ; branche A2 gagnante 340_D_Tower_A2win = ev1240, "
                "ev1241, ev1250 + 345_D_Tower_A2win_9Shack (piratage de 9S par A2/les Pods). Ces contenus "
                "correspondent aux fins nommees D (9S) et C (A2) par web_reference.md : les noms internes "
                "(sous-phases 340_C/340_D, etats ending_C/ending_D, succes 17/18) sont donc probablement "
                "inverses par rapport au titre affiche, ou le web se trompe. CONFLIT non tranche statiquement ; "
                "pour l'AP : utiliser les drapeaux internes (select/9S -> ending_C, select/A2 -> ending_D) comme "
                "conditions, et l'intitule du web pour l'affichage. confidence (titre) : low.",
                "Succes : MiscState.unlockAchievement 'N' = numero decimal ecrit en hexa (0x10 -> 10 'One Battle "
                "Ends' A, 0x11 -> 11 B, 0x19 -> 19 E) ; l'exe appelle 0x9c7250(indice = numero-1) : 0x10 -> n 17, "
                "0x11 -> n 18. Noms = CORE_ACHIEVEMENT_HELP_NN.",
            ],
            "haps": _compact(p300, subs=r"3(3[0-9]|4[0-9])_"),
            "statebind": {k: v for k, v in ranges.items() if "select" in k or "Route" in k or "ending" in k},
        },
        "achievement_names": {str(k): v for k, v in ach.items() if k in (10, 11, 13, 17, 18, 19)},
        "credit_end_titles": {str(k): v for k, v in titles.items() if k <= 5 or k in (21, 23)},
        "exe_evidence": exe,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--flow", nargs=2, metavar=("DAT", "REGEX"), help="vider les actions hap d'un .dat (filtre)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.flow:
        for r in file_flow(a.flow[0], a.flow[1]):
            print(json.dumps(r, ensure_ascii=False))
        return
    res = run()
    out = Path(a.out) if a.out else Path(tempfile.gettempdir()) / "lg_endings.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for v in res["exe_evidence"].values() for r in v if not r.get("verified")]
    print(f"ecrit {out} ; preuves exe non verifiees : {len(bad)}")
    for r in bad:
        print("  ", r)


if __name__ == "__main__":
    main()
