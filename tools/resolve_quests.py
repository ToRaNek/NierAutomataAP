"""Relie les quetes a leurs tables de recompense (QuestRewordData.drp) et decode les disponibilites (qch).

Usage : python tools/resolve_quests.py [--out docs/research]

- Les scripts *_scp.bin sont du bytecode mruby 1.x (tools/mruby.py). Les recompenses sont donnees par
  l'appel `getReWard("NNN")` (chaine decimale = identifiant de table DQR). Dans l'exe : liaison mruby
  RVA 0x303fdf (mrb_define_method "getReWard" -> 0x32d660), qui fait strtol(arg, 0, 10) puis appelle
  0x7ca970 = attribution de la recompense (recherche lineaire de l'id dans la table A de QuestRewordData).
- Fichiers lus un par un (cache disque d'extract_research), aucune ecriture dans le dossier du jeu.
Produit : docs/research/quest_rewards.json, docs/research/quest_availability.json.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import mruby  # noqa: E402

# Repertoires contenant des scripts (taille raisonnable). Les wd*/em*/bg* ne sont pas parcourus.
SCRIPT_DIRS = ("quest/", "ph1/", "ph2/", "ph3/", "ph4/", "phf/", "core/", "novel/", "st1/", "st2/", "st5/")
MAX_DAT = 30_000_000

# Noms des programmes de Pod (ids 2001-2024 : pas de texte anglais relie ; nom interne + code deduit du wiki)
POD_PROGRAM_GUESS = {2008: "A080: Wave", 2009: "A090: Wire", 2011: "A110: Slow", 2012: "A120: Repair",
                     2015: "A130: Bomb", 2019: "A140: Gravity"}


# Appels hors fichier de quete sans etat de quete dans la methode : attribution DEDUITE (a confirmer)
OWNER_GUESS = {
    ("st1/r160.dat", "animalrobo1_ON_TALK_4_ev1"):
        ("q072", "DEDUIT : salle de la foret (r160) ou leader1_DONE (q072) donne aussi un objet ; contenu "
                 "(Auto-Heal +5) = recompense de Turf War selon web_reference"),
}


def dqr_tables(b: bytes):
    """QuestRewordData.drp : en-tete '<4sfIIIHH' ('DQR', 1.0, 0x18, 14, 8, nA, nB).
    A (14 o) = '<HHHHHBBBB' : id, debut B, nb objets, nb argent, nb EXP, tirages objets, tirages argent,
    tirages EXP, 0. B (8 o) = (u32 id|montant, u32 poids). Les entrees sont dans l'ordre objets, argent, EXP.
    Tirages = nombre de tirages ponderes (si = nb, tout est donne ; poids 100 = garanti)."""
    magic, ver, off, sa, sb, na, nb = struct.unpack_from("<4sfIIIHH", b, 0)
    bo = off + sa * na
    B = [struct.unpack_from("<II", b, bo + i * sb) for i in range(nb)]
    out = {}
    for i in range(na):
        rid, st, ni, nm, ne, pi, pm, pe, pad = struct.unpack_from("<HHHHHBBBB", b, off + i * sa)
        items = B[st:st + ni]
        money = B[st + ni:st + ni + nm]
        exp = B[st + ni + nm:st + ni + nm + ne]
        out[rid] = dict(id=rid, record_index=i, items=items, money=money, exp=exp, picks=(pi, pm, pe))
    return out


def method_names(root: mruby.Irep):
    """irep -> nom de la methode ruby (def) qui le contient (via LAMBDA + METHOD du parent)."""
    names = {}

    def visit(r, inherited):
        if id(r) not in names:
            names[id(r)] = inherited
        lam = {}
        for k, i in enumerate(r.iseq):
            op = i & 0x7F
            if op == 64:  # LAMBDA A, Bz, Cz
                lam[i >> 23] = (i >> 9) & 0x3FFF
            elif op == 70:  # METHOD A, B(sym)
                a, b = i >> 23, (i >> 14) & 0x1FF
                child = lam.get(a + 1)
                if child is not None and child < len(r.kids):
                    names[id(r.kids[child])] = r.syms[b]
        for c in r.kids:
            visit(c, names.get(id(c), inherited))

    visit(root, None)
    return names


def scan_scripts():
    """Tous les appels getReWard / addItem des scripts : liste de dicts."""
    toc = er._toc_index()
    found = []
    for name in sorted(toc):
        if not name.startswith(SCRIPT_DIRS) or not name.endswith(".dat"):
            continue
        if int(toc[name][1]["ExtractSize"]) > MAX_DAT:
            continue
        files = cpk.dat_files(er.game_file(name))
        for member, data in files.items():
            if not member.endswith("_scp.bin"):
                continue
            root = mruby.parse(data)
            mn = method_names(root)
            by_name = {}
            for r in mruby.walk(root):
                if mn.get(id(r)):
                    by_name.setdefault(mn[id(r)], r)
            for fn in ("getReWard", "addItem"):
                for r, k, a, c, args in mruby.calls(root, fn):
                    e = dict(file=name, script=member, method=mn.get(id(r)), call=fn, args=args)
                    # etats de quete cites dans la meme methode (ex. "q250/RUN_1") : indice du proprietaire
                    e["quest_refs"] = sorted({m.group(1) for p in r.pool if isinstance(p, str)
                                              for m in [re.match(r"(q[0-9a-f]{3})/", p)] if m})
                    # argument = valeur de retour d'une methode du script (ex. q550 reward_item) :
                    # constantes LOADI / chaines numeriques de cette methode = valeurs possibles
                    if fn == "getReWard" and args and isinstance(args[0], tuple) and args[0][0] == "call":
                        src = by_name.get(args[0][1])
                        if src is not None:
                            vals, conds, last = [], {}, None
                            for op, _a, _b, _c, bx, sbx in src.ins():
                                if op == "STRING":
                                    last = src.pool[bx]
                                elif op == "LOADI":
                                    vals.append(str(sbx))
                                    conds[str(sbx)] = last  # derniere chaine testee (ex. "q550/RUN_1")
                            vals += [p for p in src.pool if isinstance(p, str) and p.isdigit()]
                            e["via_method"] = args[0][1]
                            e["possible_args"] = vals
                            e["arg_conditions"] = conds
                    found.append(e)
        del files
    return found


def item_namer():
    d = json.loads((Path(__file__).resolve().parents[1] / "docs/research/items.json").read_text("utf-8"))
    names = {}
    for k in ("items", "weapons", "chips"):
        for e in d[k]:
            names[e["UniqueID"]] = (e.get("english_name"), e.get("internal_name"))
    ctx_txt = {}

    def name(uid):
        n, internal = names.get(uid, (None, None))
        if n is None and uid >= 1000000:
            n = ctx_txt.get(uid)
        if n is None and uid in POD_PROGRAM_GUESS:
            n = POD_PROGRAM_GUESS[uid] + " (deduit)"
        return n, internal

    return name, ctx_txt


def decode_table(t, name):
    items = []
    agg = defaultdict(int)
    for uid, w in t["items"]:
        agg[(uid, w)] += 1
    seen = set()
    for uid, w in t["items"]:
        if (uid, w) in seen:
            continue
        seen.add((uid, w))
        n, internal = name(uid)
        items.append(dict(id=uid, name=n, internal_name=internal, count=agg[(uid, w)], weight=w))
    pi, pm, pe = t["picks"]
    guaranteed = pi >= len(t["items"]) and all(w == 100 for _, w in t["items"])
    return dict(reward_id=t["id"], items=items,
                item_mode="all" if guaranteed else f"random: {pi} tirage(s) pondere(s) parmi {len(t['items'])}",
                money=[m for m, _ in t["money"]] or None, exp=[e for e, _ in t["exp"]] or None)


def archive_names():
    """Noms des archives (ids >= 1000000) via les textes deja extraits par extract_research."""
    out = {}
    try:
        texts = er.english_texts()
    except Exception:  # noqa: BLE001
        return out
    for k, (v, _) in texts.items():
        m = re.match(r"CORE_ARCHIVE_(\d{3})_(\d{3})$", k)
        if m:
            out[1000000 + int(m.group(1)) * 1000 + int(m.group(2))] = v
    return out


def build_rewards(out_dir: Path):
    tables = dqr_tables(er.dat_member("core/coregm.dat", "QuestRewordData.drp"))
    quests = json.loads((out_dir / "quests.json").read_text("utf-8"))["quests"]
    name, arch = item_namer()
    arch.update(archive_names())
    calls = scan_scripts()
    per_quest = defaultdict(list)
    used = set()
    unresolved = []
    for c in calls:
        if c["call"] != "getReWard":
            continue
        a = c["args"][0] if c["args"] else None
        m = re.match(r"q[0-9a-f]{3}", c["file"].split("/")[-1])
        owner = m.group(0) if (m and c["file"].startswith("quest/")) else c["file"]
        how_owner = "fichier quest/qXXX.dat" if owner != c["file"] else "fichier de phase/salle"
        mm = re.search(r"(?:^|_)(q[0-9a-f]{3})_", c["method"] or "")
        if mm and mm.group(1) != owner and mm.group(1) in quests:
            owner, how_owner = mm.group(1), f"nom de methode {c['method']} ({c['file']})"
        if owner == c["file"] and len(c.get("quest_refs", [])) == 1:
            owner, how_owner = c["quest_refs"][0], f"etat {c['quest_refs'][0]}/* teste dans la methode ({c['file']})"
        elif (c["file"], c["method"]) in OWNER_GUESS:
            owner, how_owner = OWNER_GUESS[(c["file"], c["method"])]
        if isinstance(a, int):
            a = str(a)
        if isinstance(a, str) and a.isdigit():
            cands, how = [a], "getReWard"
        elif c.get("possible_args"):
            cands, how = c["possible_args"], None
        else:
            unresolved.append(c)
            continue
        for v in cands:
            if how is None or how.startswith("getReWard("):
                if c.get("possible_args"):
                    how = (f"getReWard({c['via_method']}) : valeur {v} si etat "
                           f"{c.get('arg_conditions', {}).get(v)}")
            rid = int(v)
            used.add(rid)
            t = tables.get(rid)
            per_quest[owner].append(dict(reward_id=rid, script=c["script"], method=c["method"], source=how,
                                         owner_evidence=how_owner, file=c["file"],
                                         table=decode_table(t, name) if t else None))
    # Pieces jointes des mails (MailTable.bxm 'Attachment' = id DQR) : accordees par 0x7cacc0 (meme table)
    for qid, q in quests.items():
        for m in q.get("mails", []):
            att = m.get("attachment")
            if att and att.isdigit() and int(att) in tables:
                rid = int(att)
                used.add(rid)
                per_quest[qid].append(dict(reward_id=rid, script="MailTable.bxm", method=f"mail {m['mail']}",
                                           source=f"piece jointe du mail {m['mail']} ({m['state_before']})",
                                           owner_evidence="MailTable QuestId", file="core/coregm.dat",
                                           table=decode_table(tables[rid], name)))
    res = {}
    for owner in sorted(per_quest):
        lst = per_quest[owner]
        uniq = {}
        for e in lst:
            u = uniq.setdefault(e["reward_id"], dict(e, methods=[], sources=set(), ev=set(), files=set()))
            u["methods"].append(e["method"])
            u["sources"].add(e["source"])
            u["ev"].add(e["owner_evidence"])
            u["files"].add(e["file"])
        rows = []
        for rid in sorted(uniq):
            e = uniq[rid]
            rows.append(dict(reward_id=rid, called_from=sorted(set(x for x in e["methods"] if x)),
                             source=sorted(e["sources"]), files=sorted(e["files"]),
                             owner_evidence=sorted(e["ev"]),
                             **{k: v for k, v in (e["table"] or {}).items() if k != "reward_id"}))
        q = quests.get(owner, {})
        main = [r["reward_id"] for r in rows if r["reward_id"] < 100 or r.get("money") or r.get("exp")]
        res[owner] = dict(english_name=q.get("english_name"), main_reward_ids=main, rewards=rows)
    unused = sorted(set(tables) - used)
    other_calls = [c for c in calls if c["call"] == "addItem"]
    doc = dict(
        _source="tools/resolve_quests.py ; getReWard(\"NNN\") dans les *_scp.bin (mruby) -> id de table DQR",
        _notes=["main_reward_ids = ids < 100 ou tables avec argent/EXP (recompense de fin de quete ; l'exe "
                "passe un drapeau 'id < 100' a 0x7cbcd0). Autres ids >= 100 = objets d'etape / DLC.",
                "item_mode 'all' : tout est donne ; sinon tirage pondere (poids = pourcentage).",
                "money / exp : montants ; argent multiplie par le bonus de chance G de l'exe (0x7cac0e)."],
        quests=res,
        unreferenced_reward_ids=unused,
        unreferenced_tables={str(r): decode_table(tables[r], name) for r in unused},
        unresolved_calls=[{k: v for k, v in c.items()} for c in unresolved],
        add_item_calls=other_calls,
    )
    doc["web_validation"] = validate(res)
    (out_dir / "quest_rewards.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    return doc, tables


# Recompenses notables de web_reference.md (section 5 SIDE QUESTS). str = nom d'objet, int = id,
# ("money", n) / ("exp", n) = montant present dans une des tables de la quete.
WEB_EXPECT = {
    "q020": ["EXP Gain Up +3"], "q031": ["Engels 110-B Record 0005"], "q032": ["Fast Cooldown +6", "Max HP Up +6"],
    "q040": ["Deadly Heal +3", "Impact Bracer (L)"], "q071": ["Quality Sachet"],
    "q072": ["Auto-Heal +5", "Record of a Bestial Machine"], "q101": ["Melee Defense +1"],
    "q102": ["Ranged Attack Up +2"], "q103": ["Ranged Defense +3"], "q104": ["Powerup Part S"],
    "q110": ["Pink Ribbon", "Blue Ribbon"], "q121": ["Anti Chain Damage +3"], "q122": ["Down-Attack Up +3"],
    "q123": ["Powerup Part S"], "q130": [2009, "Offensive Heal +3"], "q140": ["Max HP Up +3"],
    "q150": ["E-Drug"], "q160": [("money", 3000)], "q162": [("exp", 320)],
    "q171": ["Type-4O Sword", 2015], "q181": ["Type-4O Blade", 2011],
    "q210": ["Vengeance +3", "Last Stand +3", "Taunt Up +3"], "q222": [("money", 10000)],
    "q240": ["Alien Mask", "Choice Sachet"], "q250": ["Hijack Boost +6"], "q292": ["Hijack Boost +4"],
    "q300": ["Moving Speed Up +3"], "q330": ["Elevator Key", "Lunar Tear"], "q340": ["Charge Attack +3"],
    "q410": ["YoRHa-issue Blade", "Melee Defense +6"], "q500": [2008, "Overclock +3"],
    "q520": ["Heal Drops Up +6"], "q540": ["Type-4O Lance"], "q550": ["Cure All + Heal All", ("money", 17000)],
    "q561": ["Gold Ore", "Meteorite"], "q562": ["Popola's Booze"], "q590": ["Spear of the Usurper"],
    "q640": [2019, "Large G Luck+"], "q650": ["Evade Range Up +3"], "q651": ["Drop Rate Up +3"],
    "q652": [2012, "Jackass's Bomb Recipe"], "q660": ["Precious Earrings", "Fast Cooldown +3"],
    "q680": ["Reset +3"], "q720": ["Max HP Up +6"], "q800": ["Evade Range Up +3"], "q801": ["Resilience +3"],
    "q802": ["Damage Absorb +3"],
}


def validate(res):
    out = {}
    for q, exp in WEB_EXPECT.items():
        rows = res.get(q, {}).get("rewards", [])
        names = {i["name"] for r in rows for i in r["items"]}
        ids = {i["id"] for r in rows for i in r["items"]}
        money = {m for r in rows for m in (r.get("money") or [])}
        exps = {m for r in rows for m in (r.get("exp") or [])}
        ok, ko = [], []
        for e in exp:
            hit = (e in names if isinstance(e, str) else e in ids if isinstance(e, int)
                   else e[1] in (money if e[0] == "money" else exps))
            (ok if hit else ko).append(e if not isinstance(e, tuple) else f"{e[0]}={e[1]}")
        out[q] = dict(status="match" if not ko else "partial" if ok else "missing", found=ok, not_found=ko)
    return out


# --- disponibilites (QuestChapterData.qch) ----------------------------------------------------------

QCH_VALUE = {1: "2B", 2: "9S", 3: "A2", 4: "tout personnage"}
ROUTE = {0: "A", 1: "B", 2: "A+B", 3: "C/D"}
# Colonne Route de web_reference.md section 5 : Sh = partage, All3 = 2B/9S/A2, A2+9S = route C/D
WEB_ROUTE = {
    **{q: "Sh" for q in "q020 q031 q032 q040 q071 q072 q100 q101 q102 q103 q104 q110 q120 q121 q122 q123 q140 "
                        "q160 q162 q210 q300 q330 q340 q500 q532 q540 q640 q650 q660 q680 q770".split()},
    **{q: "2B" for q in "q150 q170 q171 q410".split()},
    **{q: "9S" for q in "q130 q180 q181 q250 q290 q291 q292 q520 q550 q720 q800 q801 q802".split()},
    **{q: "A2" for q in "q220 q221 q222".split()},
    **{q: "All3" for q in "q240 q440 q590 q900".split()},
    **{q: "A2+9S" for q in "q560 q561 q562 q651 q652".split()},
}
WEB_TO_QCH = {"Sh": {4}, "All3": {4}, "A2+9S": {4}, "2B": {1}, "9S": {2}, "A2": {3}}


def build_availability(out_dir: Path):
    quests = json.loads((out_dir / "quests.json").read_text("utf-8"))["quests"]
    res, agree, disagree = {}, [], []
    for qid, q in sorted(quests.items()):
        av = q.get("availability")
        if not av:
            continue
        windows = defaultdict(list)
        vals = set()
        for a in av:
            vals.add(a["flag"])
            if a["chapter"] is None:
                windows["hors table (indice %d)" % a["chapter_index"]].append(QCH_VALUE.get(a["flag"]))
                continue
            windows[ROUTE.get(a["route_group"], str(a["route_group"]))].append(
                f"{a['chapter']}" + (f"[{QCH_VALUE[a['flag']]}]" if a["flag"] != 4 else ""))
        res[qid] = dict(english_name=q.get("english_name"), values=sorted(vals),
                        character=[QCH_VALUE.get(v, v) for v in sorted(vals)],
                        windows={k: v for k, v in windows.items()})
        w = WEB_ROUTE.get(qid)
        if w:
            in_range = {a["flag"] for a in av if a["chapter"] is not None}
            (agree if in_range <= WEB_TO_QCH[w] else disagree).append(
                dict(quest=qid, web=w, qch=sorted(in_range)))
    doc = dict(_source="tools/resolve_quests.py ; QuestChapterData.qch",
               value_meaning=QCH_VALUE,
               evidence=f"{len(agree)}/{len(agree) + len(disagree)} quetes : valeurs conformes a la colonne Route "
                        "de web_reference.md (Sh/All3/A2+9S -> 4, 2B -> 1, 9S -> 2, A2 -> 3)",
               disagreements=disagree, quests=res)
    (out_dir / "quest_availability.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    md = ["# Disponibilite des quetes (QuestChapterData.qch)", "",
          "Genere par `tools/resolve_quests.py`. Une ligne de la qch = `u16 quete` + 128 octets, octet i = entree i "
          "de `ChapterData.cha` (point de selection de chapitre). 0 = quete absente de ce chapitre.", "",
          "| valeur | sens |", "|---|---|"]
    md += [f"| {k} | quete jouable avec **{v}** uniquement |" if k != 4 else f"| 4 | jouable avec {v} |"
           for k, v in QCH_VALUE.items()]
    md += ["", f"Preuve : {doc['evidence']}.",
           "Ecarts : " + (", ".join(f"{d['quest']} (web {d['web']}, qch {d['qch']})" for d in disagree) or "aucun") +
           ".", "",
           "Les fenetres sont celles de la selection de chapitre (chapitres ou la quete existe), pas les "
           "prerequis : ex. q170/q171 (06-02..09-01 dans la qch) ne sont faisables qu'apres q162 (web : 07-01..07-03).",
           "Valeur entre crochets = personnage requis (rien = tout personnage). Routes : A, B, A+B (chapitres "
           "communs 2B/9S), C/D.", "",
           "| quete | nom | personnage | fenetres |", "|---|---|---|---|"]
    for qid, r in res.items():
        win = " ; ".join(f"{k}: {_compress(v)}" for k, v in r["windows"].items())
        md.append(f"| {qid} | {r['english_name'] or ''} | {', '.join(r['character'])} | {win} |")
    (out_dir / "quest_availability.md").write_text("\n".join(md) + "\n", "utf-8")
    return doc


def _compress(chs):
    """['05-03','05-04[2B]','06-01'] -> '05-03/04[2B], 06-01' (groupe par chapitre, sans trou cache)."""
    groups = {}
    for c in chs:
        if c is None:
            continue
        m = re.match(r"(\d+)-(\d+)(.*)$", c)
        if not m:
            groups.setdefault(c, [])
            continue
        g = groups.setdefault(m.group(1), [])
        s = m.group(2) + m.group(3)
        if s not in g:
            g.append(s)
    return ", ".join(f"{k}-{'/'.join(v)}" if v else k for k, v in groups.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "docs/research"))
    a = ap.parse_args()
    out = Path(a.out)
    doc, tables = build_rewards(out)
    n = len(doc["quests"])
    print(f"{n} proprietaires (quetes/fichiers) avec getReWard ; {len(tables)} tables ; "
          f"{len(doc['unreferenced_reward_ids'])} non referencees ; {len(doc['unresolved_calls'])} appels non resolus")
    v = doc["web_validation"]
    print("validation web :", {k: sum(1 for x in v.values() if x["status"] == k) for k in ("match", "partial", "missing")})
    av = build_availability(out)
    print("disponibilites :", av["evidence"])


if __name__ == "__main__":
    main()
