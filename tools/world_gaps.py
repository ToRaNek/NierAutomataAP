"""Lacunes de world_positions.json : donneurs de quete non identifies, magasins sans position (Emil, arenes DLC),
terminaux d'acces sans placement (ft_AP_C / ft_AP_T / ft_AP_T2). LECTURE SEULE sur le dossier du jeu.

Usage (apres tools/world_positions.py, qui reecrit world_positions.json sans les renvois) :
    python tools/world_gaps.py [--out docs/research] [--no-wd] [--refresh] [--collect-only]

Etapes :
1. Collecte (meme parcours que world_positions.py : ph*, phf, quest, st*, core, wd*) avec en plus, pour chaque
   script mruby, la liste des appels de chaque methode (nom + arguments constants), et pour chaque action hap
   le texte de toutes ses valeurs (command/label/args, codeName...). Resultat mis en cache (pickle) dans
   %TEMP%/nier_research_cache/world_gaps.pkl (--refresh pour refaire).
2. Resolution (voir data_formats.md, section "Lacunes resolues") -> docs/research/world_gaps_resolved.json,
   puis ajout d'un champ `gaps_resolved` (renvoi) dans world_positions.json pour les entrees concernees.
"""
from __future__ import annotations

import argparse
import json
import json
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_research as er  # noqa: E402
import mruby  # noqa: E402
import resolve_quests  # noqa: E402
import world_positions as wp  # noqa: E402

# Cache local ecrit par ce script lui-meme (pas une donnee externe) : pickle acceptable.
CACHE = er.CACHE / "world_gaps.pkl"
INTEREST = re.compile(r"q[0-9a-f]{3}|ft_|ba1100|ba1000|shop_|[Mm]ail|emil|Emil|emile")


def method_calls(b: bytes) -> dict:
    """{methode: [(nom appele, [args constants])]} ; methode anonyme = '?<indice>'."""
    root = mruby.parse(b)
    names = resolve_quests.method_names(root)
    out = {}
    for i, r in enumerate(mruby.walk(root)):
        m = names.get(id(r)) or f"?{i}"
        calls = []
        ins = list(r.ins())
        for k, (op, a, bb, c, bx, sbx) in enumerate(ins):
            if op not in ("SEND", "FSEND", "SENDB"):
                continue
            args = []
            for reg in range(a, a + 1 + c):  # R(a) = receveur, puis arguments
                val = None
                for j in range(k - 1, -1, -1):
                    op2, a2, b2, c2, bx2, sbx2 = ins[j]
                    if op2 in ("JMP", "JMPIF", "JMPNOT"):
                        break
                    if a2 != reg:
                        continue
                    if op2 == "STRING":
                        val = r.pool[bx2]
                    elif op2 == "LOADSYM":
                        val = ":" + str(r.syms[bx2])
                    elif op2 == "LOADI":
                        val = sbx2
                    elif op2 == "LOADSELF":
                        val = "self"
                    elif op2 in ("SEND", "FSEND"):
                        val = "." + str(r.syms[b2])
                    break
                args.append(val)
            calls.append((r.syms[bb], args))
        # toutes les chaines / symboles charges (arguments de menus de choix, tableaux...) : pseudo-appel __refs__
        refs = sorted({str(r.syms[bx]) for op, a, bb, c, bx, sbx in ins if op == "LOADSYM"} |
                      {r.pool[bx] for op, a, bb, c, bx, sbx in ins if op == "STRING" and isinstance(r.pool[bx], str)})
        calls.append(("__refs__", [None] + refs))
        out[m] = calls
    return out


class GapCollector(wp.Collector):
    def __init__(self):
        super().__init__()
        self.actions = []   # actions hap au texte interessant
        self.calls = {}     # (fichier, membre scp) -> method_calls
        self.action_index = {}  # (fichier, id d'action) -> resume (nom, code, position, scale)
        self.script_vars = {}   # (fichier, membre scp) -> {variable: (code, valeur)} (toutes les variables)
        self.action_index_z = {}  # idem depuis les hap.z perimes (secours)

    def process_file(self, name: str):
        d = wp.members(name)
        for k, v in d.items():
            if k.endswith("_scp.bin"):
                try:
                    self.calls[(name, k)] = method_calls(v)
                except Exception as ex:  # noqa: BLE001
                    self.calls[(name, k)] = {"_error": str(ex)}
        # actions : on relit les haps (meme logique que la classe de base)
        has_pak = any(k.endswith("_hap.pak") for k in d)
        trees = []
        for k, v in d.items():
            if k.endswith(".pak"):
                try:
                    for t in wp.cpk.pak_yax(v):
                        trees.append((k, wp.yax_to_elem(t, self.vocab)))
                except Exception:  # noqa: BLE001
                    pass
            elif k.endswith("_hap.z"):
                root = wp.ET.fromstring(wp.hap_xml_text(v))
                if not has_pak:
                    trees += [(k, h) for h in root.findall("hap")]
                else:
                    # hap.z perime : seulement un index de secours (actions absentes du .pak, ex. zones de q400
                    # referencees par q401/q403), marque 'stale_hap_z'
                    for h in root.findall("hap"):
                        for act in h.findall("action"):
                            self.action_index_z[(name, wp.txt(act, "id"))] = {
                                "name": wp.txt(act, "name"), "code": wp.txt(act, "code"), "hap": wp.txt(h, "name"),
                                "group": wp.txt(h, "group"), "member": k, "stale_hap_z": True,
                                "position": wp.floats(next((x.text for x in act.iter() if x.tag == "position"),
                                                           None)),
                                "scale": wp.floats(next((x.text for x in act.iter() if x.tag == "scale"), None))}
        del d
        base = name.split("/")[-1][:-4]
        for k, h in trees:
            for act in h.findall("action"):
                sid = wp.txt(act, "script/id")
                if sid:
                    sv = self.script_vars.setdefault((name, f"{base}_{int(sid, 16):x}_scp.bin"), {})
                    for vv in act.findall("variables/value"):
                        sv[wp.txt(vv, "name")] = (wp.txt(vv, "value/code"), wp.txt(vv, "value/value"))
                vals = [x.text for x in act.iter() if x.text]
                text = " | ".join(vals)
                # toutes les actions : id -> nom/code/position (zones INSIDE/OUTSIDE referencees par id)
                self.action_index[(name, wp.txt(act, "id"))] = {
                    "name": wp.txt(act, "name"), "code": wp.txt(act, "code"), "hap": wp.txt(h, "name"),
                    "group": wp.txt(h, "group"), "member": k,
                    "position": wp.floats(next((x.text for x in act.iter() if x.tag == "position"), None)),
                    "scale": wp.floats(next((x.text for x in act.iter() if x.tag == "scale"), None))}
                if not (INTEREST.search(text) or "Action.signal" in text):
                    continue
                self.actions.append({"file": name, "member": k, "hap": wp.txt(h, "name"), "hap_id": wp.txt(h, "id"),
                                     "group": wp.txt(h, "group"), "action": wp.txt(act, "name"),
                                     "action_id": wp.txt(act, "id"), "code": wp.txt(act, "code"),
                                     "location": wp.floats(wp.txt(act, "location/position")),
                                     "text": text[:4000]})
        super().process_file(name)


def collect(no_wd: bool, refresh: bool) -> GapCollector:
    if CACHE.exists() and not refresh:
        col = GapCollector.__new__(GapCollector)
        with CACHE.open("rb") as f:
            col.__dict__.update(pickle.load(f))
        return col
    col = GapCollector()
    names = sorted(er.all_names())
    logic = [n for n in names if wp.LOGIC_RE.match(n)]
    wd = [] if no_wd else [n for n in names if wp.WD_RE.match(n)]
    for n in logic:
        for k, v in wp.members(n).items():
            if k.endswith("_hap.z"):
                for tag in set(re.findall(r"<(\w+)>", wp.hap_xml_text(v))):
                    col.vocab.add(tag)
    for i, n in enumerate(logic + wd):
        print(f"[{i + 1}/{len(logic) + len(wd)}] {n}", file=sys.stderr, flush=True)
        col.process_file(n)
    with CACHE.open("wb") as f:
        pickle.dump(col.__dict__, f)
    return col


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(wp.RESEARCH))
    ap.add_argument("--no-wd", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--collect-only", action="store_true")
    args = ap.parse_args()
    col = collect(args.no_wd, args.refresh)
    if args.collect_only:
        print(len(col.actions), "actions", len(col.calls), "scripts", len(col.scripts), "script actions")
        return
    resolve(col, Path(args.out))


# --------------------------------------------------------------------------------------------- graphe des scripts

CALLERS = ("call", "call_fiber", "call_on", "call_bg", "fiber")


def script_graph(meths: dict):
    """Arcs methode -> methodes appelees (call/call_fiber(:sym|'nom')) et declencheurs `event_trigger(label,
    entites, evenement[, condition])` (label 'm/ev0' -> methode 'm_ev0')."""
    edges = defaultdict(set)
    triggers = []
    for m, calls in meths.items():
        if m == "_error":
            continue
        prefix = m.rsplit("_", 1)[0]
        for name, args in calls:
            if name != "event_trigger":
                # call/call_fiber(:sym), mais aussi menus de choix (sele_ex : 'ev1' = methode '<prefixe>_ev1')
                # etc. : tout argument qui nomme une methode
                for a in args[1:]:
                    if isinstance(a, str) and a != "self":
                        t = a.lstrip(":").replace("/", "_")
                        for cand in (t, f"{prefix}_{t}"):
                            if cand in meths and cand != m:
                                edges[m].add(cand)
            if name in meths and name != m:
                edges[m].add(name)
            if name == "event_trigger" and len(args) >= 4 and isinstance(args[1], str):
                triggers.append({"method": args[1].replace("/", "_"), "label": args[1],
                                 "entities": args[2], "event": args[3],
                                 "condition": args[4] if len(args) > 4 else None})
    return edges, triggers


def reaches(edges, start, target, seen=None):
    if start == target:
        return [start]
    seen = seen if seen is not None else set()
    seen.add(start)
    for n in edges.get(start, ()):
        if n not in seen:
            p = reaches(edges, n, target, seen)
            if p:
                return [start] + p
    return None


# --------------------------------------------------------------------------------------------- resolution

GAP_QUESTS = ["q070", "q095", "q150", "q162", "q170", "q181", "q221", "q360", "q540", "q561", "q900",
              "q085", "q171", "q401", "q403", "q920"]
GAP_SHOPS = ["shop_chipEmile", "shop_rareEmile", "shop_rareChipEmile", "shop_CS_Grocery", "shop_CD_Grocery"]
GAP_TERMINALS = ["ft_AP_C", "ft_AP_T", "ft_AP_T2"]
VAR_ACTION = "0xa6aaf7a4"
HEX = re.compile(r"0x[0-9a-f]{5,8}")

# Lecture humaine des preuves (tout est re-derive par le code ci-dessous ; ces notes ne font que resumer ce que
# les preuves montrent, avec la confiance). Mecanismes : npc_talk, area, hacking, mail, signal, auto.
QUEST_NOTES = {
    "q070": ("area_talk", "high", "Foret (r160) : zone 'talk' '会話予期-クエスト開始' devant la cabane ; TALK quand "
             "q070/REQ -> q070/RUN_1. Donneur = machine de la cabane emb050 'animalrobo' (NameTag animallike) placee "
             "par quest/q070 (400.17, -20.14, -559.93)."),
    "q085": ("mail", "high", "Mail 35 (expediteur 'unknownletter') envoye par quest/q080 (hap 'メール送信' -> "
             "this_q080_mailSend : send_mail 35, q085/REQ) ; q080 est monte par core_hap 'クエストマウント' (groupe "
             "'DLC_installed', p200/p300). Lecture du mail (q080Mail/OPEN) -> hap q080 '会話発生させられたら発生' "
             "-> q085/RUN_1. Pas de PNJ ; cibles = 3 marques (desert, ville inondee, foret)."),
    "q095": ("mail", "high", "Mail 36 (unknownletter) envoye par l'exe (RVA 0x8d59a0 : si les drapeaux 0x1b63, "
             "0x1b64, 0x1b65 sont mis -> mail 0x24, etat q095Mail/CLOSE, 'you_got_mail') ; q095 est monte par "
             "core_hap 'クエストマウント' quand q090/q091/q092 DONE. Lecture (q095Mail/OPEN) -> signal "
             "q095_readMail -> hap q095 'メール受信' : q095/RUN_1. Pas de PNJ."),
    "q150": ("npc_route_end", "high", "Jackass (pl2030, NameTag 'jackas', st1/r150 hap 'NPC_砂レジ(2)', camp du "
             "desert) : quand elle arrive au bout de son trajet (ON_ROUTE_END, hap q150 'NPC移動') -> signal "
             "q150_talk2 -> q150/RUN_1 (dialogue de depart)."),
    "q162": ("area", "high", "Zone HIT 'area_talk_start' (ville en ruines, pres de l'usine) si !auto/blocked -> "
             "q162/RUN_1 (dialogue Pod/operatrice). Pas de PNJ ; bk_ope_6O (Bunker) parle seulement si !q162/REQ."),
    "q170": ("area", "high", "Apres q162 DONE : etre DANS la zone 'エリア_通信発生エリア' (meme zone que q162, "
             "-42.6, -16.8, 506.9) et HORS de la zone du terminal X (X = ft_CC, ft_CRb ou ft_CS, active) -> "
             "signal q170_talk1 -> send_mail 3 + q170/RUN_1 ; le terminal X passe en panne (setvar 'ft_X false', "
             "etat q170_ft/X_break). Pas de PNJ."),
    "q171": ("mail", "high", "Route A, q171/REQ : entrer dans la zone du camp de la Resistance -> send_mail 30 "
             "(q171Mail/CLOSE) ; lecture du mail (q171Mail/OPEN) -> signal q171_talk1 -> q171/RUN_1. Pas de PNJ."),
    "q181": ("area_auto", "high", "Route B, q181/REQ, apres q180_FIN : SORTIR de la zone du camp de la "
             "Resistance (hors Bunker, pas de dialogue en cours) -> signal q181_talk1 -> send_mail 10 + "
             "q181/RUN_1. Pas de PNJ (operateur 21O par mail)."),
    "q221": ("area_talk", "high", "Village de Pascal, q221/REQ : entrer dans la petite zone '流れ(2)' (467.19, "
             "14.81, -34.91 ; marque de quete 469.10, 14.94, -30.32) -> signal q221_start -> this_q221_start_ev0 "
             "(dialogue des enfants machines 'robochild(ren)' + choix sele_ex) -> ev1/ev2 -> q221/RUN_1."),
    "q360": ("hacking", "high", "Pirater (ON_HACKING_CLEAR) une des 3 machines em0050 robo1/robo2/robo3 de "
             "quest/q360 -> hack_branch -> clear_first -> q360/RUN_1."),
    "q401": ("area", "medium", "Hap '進行制御(14)' : condition INSIDE des 3 zones 0x7d07b30a / 0x9984d6fc / "
             "0xfa8d73a0 -> signal q401_talk2 -> q401/RUN_1. Ces zones ne sont definies que dans quest/q400_hap.z "
             "(perime, 'クエスト受託エリア' ville / 'desert' / 'ville inondee', 15x10x15) : absentes de tous les "
             ".pak. Pas de PNJ donneur."),
    "q403": ("area", "medium", "Comme q401 (memes 3 zones de q400_hap.z) : hap '進行制御(15)' -> signal "
             "q403_talk2 -> q403/RUN_1."),
    "q540": ("mail", "high", "q540/REQ : zone HIT 'mail_area1' -> play_a1 (Route A : send_mail 6, 6O) ou play_b1 "
             "(Route B : send_mail 12, 21O) ; MailTable : lecture du mail = q540/REQ -> q540/RUN_1. Pas de PNJ."),
    "q561": ("npc_talk", "high", "Parler a Devola (pl1040) ou Popola (pl1050) au camp de la Resistance (st1/r110) "
             "quand q561/REQ -> q561_talk1_a2 -> q561_talk1_ok -> q561/RUN_1."),
    "q900": ("npc_route_end", "high", "Emil (pl1010, entite du hap 'エミール' de quest/q900) au bout de son trajet "
             "(ON_ROUTE_END) -> signal q900_talk1 -> q900/RUN_1 ; eml_1 ON_TALK quand q900/REQ."),
    "q920": ("examine", "medium", "Aucun etat q920/* dans les scripts/hap : la quete suit des etats emil_*. Maison "
             "d'Emil (sous-sol) : examiner (ON_CHECK) l'objet place (it0000) du hap '住居初回侵入' -> signal "
             "theft_talk (si emil_queststart, pose par r200 first_end apres la 1re rencontre) -> "
             "emil_itemsteele ; ensuite parler a Emil (r200 emile_* ON_TALK si emil_itemsteele) puis combat."),
}


def resolve(col, out):
    phases = json.loads((wp.RESEARCH / "phases.json").read_text(encoding="utf-8"))
    quests = json.loads((wp.RESEARCH / "quests.json").read_text(encoding="utf-8"))["quests"]
    quest_ids = sorted(set(quests) | {m for w in col.words for m in re.findall(r"\bq[0-9a-f]{3}\b", w)})
    tok = wp.build_token_names(col, phases, quest_ids)

    def cond(f, gid):
        c = wp.conditions_of(col, f, gid, tok, {})
        return {k: v for k, v in c.items() if v and k not in ("raw",)}

    def entity_refs(eid, limit=3):
        return [{"objId": e["objId"], "position": e["position"], "file": e["file"], "hap": e["hap"],
                 "action": e["action"], "entity_id": eid, "params": e["params"] or None}
                for e in col.by_id.get(eid, [])[:limit]]

    by_aid, by_aid_z = defaultdict(list), defaultdict(list)
    for (ff, i), a in col.action_index.items():
        by_aid[i].append((ff, a))
    for (ff, i), a in col.action_index_z.items():
        by_aid_z[i].append((ff, a))

    def action_ref(f, aid):
        """Action par id : meme fichier (.pak), sinon autre fichier (.pak), sinon hap.z perime (meme fichier puis
        autre) ; la source est indiquee."""
        a, src = col.action_index.get((f, aid)), f
        if not a and by_aid.get(aid):
            src, a = by_aid[aid][0]
        if not a:
            a, src = col.action_index_z.get((f, aid)), f
        if not a and by_aid_z.get(aid):
            src, a = by_aid_z[aid][0]
        if not a:
            return None
        r = {"action_id": aid, "name": a["name"], "code": a["code"], "hap": a["hap"], "member": a["member"],
             "position": a["position"], "scale": a["scale"]}
        if src != f:
            r["defined_in"] = src
        if a.get("stale_hap_z"):
            r["source"] = "stale_hap_z (action absente des .pak)"
        return r

    def var_ref(f, mem, name):
        code, val = col.script_vars.get((f, mem), {}).get(name, (None, None))
        if code == wp.VAR_ENTITY:
            return {"variable": name, "kind": "entity", "placements": entity_refs(val)}
        if code == VAR_ACTION:
            return {"variable": name, "kind": "hap_action", "action": action_ref(f, val)}
        return {"variable": name, "kind": code, "value": val}

    def emitter_info(a):
        """Action hap : ids references -> zones (actions positionnees) et entites, + autres actions positionnees
        du meme hap, + conditions de groupe."""
        refs_a, refs_e = [], []
        for h in dict.fromkeys(HEX.findall(a["text"])):
            r = action_ref(a["file"], h)
            if r and r["position"]:
                refs_a.append(r)
            elif col.by_id.get(h):
                refs_e += entity_refs(h, 2)
        same_hap = [action_ref(a["file"], i) for (f, i), v in col.action_index.items()
                    if f == a["file"] and v["hap"] == a["hap"] and v["member"] == a["member"] and v["position"]]
        return {"file": a["file"], "member": a["member"], "hap": a["hap"], "action": a["action"],
                "action_id": a["action_id"], "text": a["text"][:600], "referenced_areas": refs_a[:8],
                "referenced_entities": refs_e[:8], "positioned_actions_in_hap": same_hap[:10],
                "group_conditions": cond(a["file"], a["group"])}

    def signal_emitters(f, event):
        pat = re.compile(r'Action\.signal \| "%s(?: |")' % re.escape(event))
        return [emitter_info(a) for a in col.actions if a["file"] == f and pat.search(a["text"])]

    graphs = {k: script_graph(m) for k, m in col.calls.items() if "_error" not in m}
    scr_meta = {}
    for s in col.scripts:
        if s["script_member"]:
            scr_meta.setdefault((s["file"], s["script_member"]), s)

    def triggers_to(f, mem, method):
        edges, trig = graphs[(f, mem)]
        out_ = []
        for t in trig:
            p = reaches(edges, t["method"], method)
            if not p:
                continue
            ents = [var_ref(f, mem, n) for n in (t["entities"] or "").split(",") if n]
            r = {"script": mem, "file": f, "event": t["event"], "entities": t["entities"],
                 "trigger_condition": t["condition"], "call_path": p, "resolved": ents}
            if t["entities"] == "this":
                r["signal_emitters"] = signal_emitters(f, t["event"])
            out_.append(r)
        meta = scr_meta.get((f, mem))
        return out_, (cond(f, meta["group"]) if meta else None)

    def calls_with(pred):
        for (f, mem), meths in col.calls.items():
            if "_error" in meths:
                continue
            for m, cs in meths.items():
                for n, a in cs:
                    if n != "__refs__" and pred(n, a):
                        yield f, mem, m, n, a

    mail_b = er.dat_member("core/coregm.dat", "MailTable.bxm")
    mails = []
    import bxm  # noqa: E402
    mroot = bxm.parse(mail_b)
    mroot = mroot[0] if isinstance(mroot, tuple) else mroot
    for m in mroot["children"]:
        d = {c["name"]: c["value"] for c in m["children"]}
        mails.append(d)

    def state_setters(state):
        res = []
        for f, mem, m, n, a in calls_with(lambda n, a: n == "set_scene_state" and state in a[1:]):
            trig, sc = triggers_to(f, mem, m)
            res.append({"via": "script", "file": f, "script": mem, "method": m, "script_group_conditions": sc,
                        "triggers": trig})
        for a in col.actions:
            if re.search(r"SceneStateSystem\.set \| %s(?: |$)" % re.escape(state), a["text"]):
                res.append({"via": "hap", **emitter_info(a)})
        for d in mails:
            if d.get("StateAfter") == state:
                no = int(d["MailNo"])
                senders = []
                for f, mem, m, n, a in calls_with(lambda n, a, no=no: n == "send_mail" and no in a[1:]):
                    trig, sc = triggers_to(f, mem, m)
                    senders.append({"file": f, "script": mem, "method": m, "script_group_conditions": sc,
                                    "triggers": trig})
                res.append({"via": "mail_read", "mail": no, "sender": d.get("Sender"),
                            "state_before": d.get("StateBefore"), "send_2B_9S_A2": [d.get("Send2B"),
                            d.get("Send9S"), d.get("SendA2")], "senders_in_scripts": senders})
        return res

    quest_out = {}
    for q in GAP_QUESTS:
        note = QUEST_NOTES.get(q)
        quest_out[q] = {
            "english_name": (quests.get(q) or {}).get("english_name"),
            "start_mechanism": note[0] if note else None, "confidence": note[1] if note else "unresolved",
            "summary": note[2] if note else None,
            "run_1_setters": state_setters(f"{q}/RUN_1"),
            "req_setters": state_setters(f"{q}/REQ"),
        }
    # q920 : pas d'etat q920/* -> chaine emil_* (maison d'Emil)
    quest_out["q920"]["emil_state_chain"] = {s: state_setters(s) for s in ("emil_queststart", "emil_itemsteele")}
    quest_out["q920"]["signal_theft_talk"] = signal_emitters("quest/q920.dat", "theft_talk")
    # montage des quetes DLC (core_hap 'クエストマウント')
    mount = [emitter_info(a) for a in col.actions if a["file"] == "core/corehap.dat"
             and a["hap"] == "クエストマウント" and "QuestState.mount" in a["text"]]
    for q in ("q085", "q095"):
        quest_out[q]["mount_actions_core_hap"] = mount

    # ------------------------------------------------------------------ magasins d'Emil (shop_branch)
    shops_out = {}
    for (f, mem), meths in col.calls.items():
        if "_error" in meths:
            continue
        direct = {m: a[1] for m, cs in meths.items() for n, a in cs
                  if n == "shop" and len(a) > 1 and a[1] in GAP_SHOPS + ["shop_Emile"]}
        if not direct:
            continue
        edges, trig = graphs[(f, mem)]
        for m, sname in direct.items():
            chain = []
            for t in trig:
                p = reaches(edges, t["method"], m)
                if p:
                    chain.append({"event": t["event"], "entities": t["entities"], "condition": t["condition"],
                                  "call_path": p,
                                  "resolved": [var_ref(f, mem, n) for n in (t["entities"] or "").split(",") if n]})
            branch = {k: [(n, a[1:]) for n, a in meths[k] if n not in ("__refs__",)]
                      for k in ("shop_branch", "shop_slow", "shop_fast") if k in meths}
            shops_out.setdefault(sname, []).append({"file": f, "script": mem, "method": m, "triggers": chain,
                                                    "branch_methods": branch if branch else None})
    emil_vars = {k: var_ref("st2/r200.dat", "r200_d52e3bf5_scp.bin", k)
                 for k in ("emile_first", "emile_slow", "emile_fast", "random")}
    random_setter = {k: [(n, a[1:]) for n, a in col.calls[("st2/r200.dat", "r200_d52e3bf5_scp.bin")].get(k, [])
                         if n != "__refs__"] for k in ("random_DONE_a0", "state_on", "state_off")}
    emil_logic = ("r200_d52e3bf5_scp.bin shop_branch : si emile_slow.ready? ou emile_first.ready? -> shop_slow, "
                  "sinon (Emil rapide 'emile_fast') -> shop_fast. shop_slow : 'emil_normal'.on? -> shop_Emile, "
                  "sinon shop_chipEmile. shop_fast : 'emil_normal'.on? -> shop_rareEmile, sinon "
                  "shop_rareChipEmile. emil_normal : random_DONE_a0 (DONE de la 'ランダムコマンドエリア') -> "
                  "rand(2) : 0 -> set_scene_state emil_normal, 1 -> reset (50/50).")
    shop_final = {}
    for s in GAP_SHOPS:
        if s in ("shop_CS_Grocery", "shop_CD_Grocery"):
            continue
        shop_final[s] = {"confidence": "high", "logic": emil_logic,
                         "npc_variable": "emile_fast" if "rare" in s else "emile_slow|emile_first",
                         "emil_normal_required": "Chip" not in s and "chip" not in s,
                         "npc_placements": ([emil_vars["emile_fast"]] if "rare" in s
                                            else [emil_vars["emile_slow"], emil_vars["emile_first"]]),
                         "random_area": emil_vars["random"], "random_methods": random_setter,
                         "references": shops_out.get(s, [])}
    # arenes DLC : chaines absentes des scripts/hap ; seule reference = table de l'exe
    found = {s: [] for s in ("shop_CS_Grocery", "shop_CD_Grocery")}
    for f, mem, m, n, a in calls_with(lambda n, a: any(x in ("shop_CS_Grocery", "shop_CD_Grocery") for x in a[1:])):
        found[a[1]].append((f, mem, m))
    for a in col.actions:
        for s in found:
            if s in a["text"]:
                found[s].append((a["file"], a["hap"], a["action"]))
    for s in found:
        shop_final[s] = {
            "confidence": "unresolved", "script_or_hap_references": found[s],
            "exe": "seules references : tables de pointeurs de noms de magasin en RVA 0xf65130 (11 noms, contient "
                   "shop_CS_Grocery) et 0xf65190 (12 noms, contient shop_CF_Grocery et shop_CD_Grocery), lues par "
                   "RVA 0x8ef780 (comparaison du magasin courant pour un calcul de prix). Aucun appel shop(...) ni "
                   "commande hap : les arenes q091/q092 n'ouvrent que shop_Upgrade (q091 sc_f15) ; seul q090 "
                   "ouvre shop_CF_Grocery (lobby_em0106_shop). Magasins probablement inutilises (coupes).",
            "note": "Id 56 'Arena Trader' (CS) et 57 'Masked Trader' (CD) : non places."}

    # ------------------------------------------------------------------ terminaux ft_AP_C / ft_AP_T / ft_AP_T2
    term_out = {}
    for code in GAP_TERMINALS:
        pat = re.compile(r"\b%s\b" % re.escape(code))
        hits = [(a["file"], a["hap"], a["action"]) for a in col.actions if pat.search(a["text"])]
        hits += [(f, mem, m) for f, mem, m, n, a in calls_with(lambda n, a: any(isinstance(x, str) and pat.search(x)
                                                                                  for x in a[1:]))]
        ents = [e["file"] for es in col.by_id.values() for e in es if e["params"].get("codeName") == code]
        term_out[code] = {"confidence": "unresolved", "hap_or_script_references": hits, "placements": ents,
                          "files_scanned": len(col.files_done),
                          "exe": "chaine referencee uniquement par les initialiseurs de tables crc32 RVA 0x105a90 "
                                 "et 0x109ee0 (bit de terminal / texte CORE_MAP_TRANS) ; aucun objet ba1100 ni "
                                 "'ファストトラベル出現位置' (code 0xfbac492d) ne porte ce codeName. Seul "
                                 "terminal du parc : ft_AP (r130, 647.59, 13.37, 387.15). Terminal coupe."}

    res = {"_source": "tools/world_gaps.py (lecture seule ; voir data_formats.md 'Lacunes resolues')",
           "method": "Chaine de declenchement : set_scene_state('qXXX/RUN_1') dans un script mruby -> remontee "
                     "du graphe d'appels (call/call_fiber/choix sele_ex) jusqu'a un event_trigger(label, entites, "
                     "evenement, condition) ; entites = variables de l'action script (0xd8efbb45 entite placee, "
                     "0xa6aaf7a4 action hap du meme fichier : zone, signal) ; evenement d'entite 'this' = "
                     "Action.signal \"evenement 0\" envoye par une action hap (zones INSIDE/OUTSIDE par id). "
                     "Aussi : SceneStateSystem.set qXXX/RUN_1 dans un hap, et MailTable StateAfter (lecture "
                     "d'un mail) avec l'appel send_mail(N) qui l'envoie.",
           "quests": quest_out, "shops": shop_final, "access_points": term_out}
    out.mkdir(parents=True, exist_ok=True)
    (out / "world_gaps_resolved.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list),
                                                  encoding="utf-8")

    # ------------------------------------------------------------------ renvoi dans world_positions.json
    wpj = out / "world_positions.json"
    if wpj.exists():
        w = json.loads(wpj.read_text(encoding="utf-8"))
        for q, v in quest_out.items():
            if q in w["quest_npcs"]:
                w["quest_npcs"][q]["gaps_resolved"] = {
                    "start_mechanism": v["start_mechanism"], "confidence": v["confidence"], "summary": v["summary"],
                    "start_positions": start_positions(v), "resolved_in": "world_gaps_resolved.json"}
        for s in w["shops"]:
            if s["shop"] in shop_final:
                sf = shop_final[s["shop"]]
                s["gaps_resolved"] = {"confidence": sf["confidence"], "resolved_in": "world_gaps_resolved.json",
                                      "summary": sf.get("logic") or sf.get("exe"),
                                      "npc_positions": [p["position"] for r in sf.get("npc_placements", [])
                                                        for p in (r.get("placements") or [])]}
        for a in w["access_points"]:
            if a["code"] in term_out:
                a["gaps_resolved"] = {"confidence": "unresolved", "resolved_in": "world_gaps_resolved.json",
                                      "summary": term_out[a["code"]]["exe"]}
        w["summary"]["gaps_resolved"] = {
            "quests": {q: v["confidence"] for q, v in quest_out.items()},
            "shops": {s: v["confidence"] for s, v in shop_final.items()},
            "access_points": {c: v["confidence"] for c, v in term_out.items()}}
        wpj.write_text(json.dumps(w, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(json.dumps({q: (v["confidence"], len(start_positions(v))) for q, v in quest_out.items()}, indent=0))


def start_positions(v):
    """Positions utiles du declencheur de RUN_1 : entites/zones resolues et zones referencees par les emetteurs."""
    pts = []

    def add(kind, name, pos, extra=None):
        if pos:
            d = {"kind": kind, "name": name, "position": pos}
            d.update(extra or {})
            if d not in pts:
                pts.append(d)

    setters = list(v["run_1_setters"])
    if v.get("signal_theft_talk"):  # q920 : declencheur = signal theft_talk
        setters.append({"via": "signal", "triggers": [{"resolved": [], "signal_emitters": v["signal_theft_talk"]}]})
    for s in setters:
        trig = s.get("triggers", [])
        for snd in s.get("senders_in_scripts", []):
            trig = trig + snd["triggers"]
        for t in trig:
            for r in t["resolved"]:
                if r["kind"] == "entity":
                    for p in r["placements"]:
                        add("entity", f"{r['variable']} ({p['objId']})", p["position"], {"file": p["file"]})
                elif r["kind"] == "hap_action" and r["action"]:
                    add("area", f"{r['variable']} ({r['action']['name']})", r["action"]["position"],
                        {"scale": r["action"]["scale"]})
            for em in t.get("signal_emitters", []):
                for ar in em["referenced_areas"]:
                    add("area", ar["name"], ar["position"], {"scale": ar["scale"], "via": em["action"],
                                                       **{k: ar[k] for k in ("defined_in", "source") if k in ar}})
                for en in em["referenced_entities"]:
                    add("entity", en["objId"], en["position"], {"file": en["file"], "via": em["action"]})
                if not em["referenced_areas"]:
                    for ar in em["positioned_actions_in_hap"]:
                        add("area_in_hap", ar["name"], ar["position"], {"scale": ar["scale"], "hap": em["hap"]})
        if s["via"] == "hap":
            for ar in s["referenced_areas"]:
                add("area", ar["name"], ar["position"], {"scale": ar["scale"]})
    return pts


if __name__ == "__main__":
    main()
