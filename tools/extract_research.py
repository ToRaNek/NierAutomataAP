"""Extraction de donnees de recherche depuis les CPK de NieR:Automata (LECTURE SEULE).

Usage :
    python tools/extract_research.py [--cache DIR] [--out docs/research]

- Les fichiers utiles sont extraits un par un des CPK (jamais les archives > 2 Go entieres) et mis en
  cache sur disque (par defaut %TEMP%/nier_research_cache) pour limiter la RAM.
- Rien n'est ecrit dans le dossier du jeu.
Voir docs/research/data_formats.md pour les formats.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import bxm  # noqa: E402

CACHE = Path(os.environ.get("NIER_RESEARCH_CACHE", Path(tempfile.gettempdir()) / "nier_research_cache"))
_TOC: dict[str, tuple[Path, dict]] | None = None


# --- acces aux fichiers -------------------------------------------------------------------------

def _toc_index():
    global _TOC
    if _TOC is None:
        _TOC = {}
        for p in sorted(cpk.DATA.glob("*.cpk")):
            rows, _ = cpk.toc(p)
            for r in rows:
                n = f'{r.get("DirName") or ""}/{r.get("FileName")}'
                _TOC.setdefault(n, (p, r))  # premiere occurrence (ordre des CPK)
    return _TOC


def all_names():
    return list(_toc_index())


def game_file(name: str) -> bytes | None:
    """Octets d'un fichier du jeu ("dir/file.dat"), via le cache disque."""
    c = CACHE / name.replace("/", "__")
    if c.exists():
        return c.read_bytes()
    hit = _toc_index().get(name)
    if not hit:
        return None
    data = cpk.extract(*hit)
    CACHE.mkdir(parents=True, exist_ok=True)
    c.write_bytes(data)
    return data


def dat_member(name: str, member: str) -> bytes | None:
    d = game_file(name)
    if d is None:
        return None
    return cpk.dat_files(d).get(member)


# --- textes ------------------------------------------------------------------------------------

def tmd(b: bytes) -> dict[str, str]:
    """.tmd : u32 n ; n x (u32 nb car. cle (NUL inclus), cle UTF-16LE, u32 nb car. texte, texte UTF-16LE)."""
    n = struct.unpack_from("<I", b, 0)[0]
    p = 4
    out = {}
    for _ in range(n):
        kl = struct.unpack_from("<I", b, p)[0]; p += 4
        k = b[p:p + kl * 2].decode("utf-16-le").rstrip("\0"); p += kl * 2
        tl = struct.unpack_from("<I", b, p)[0]; p += 4
        t = b[p:p + tl * 2].decode("utf-16-le").rstrip("\0"); p += tl * 2
        out[k] = t
    return out


def mcd(b: bytes) -> dict[str, str]:
    """.mcd (fichier) -> {cle d'evenement: texte}. Meme disposition qu'en memoire (offsets relatifs au debut).
    Lignes d'un meme paragraphe jointes par '\\n', paragraphes par '\\n\\n'."""
    mo, mc, so, sc, go, gc, fo, fc, eo, ec = struct.unpack_from("<10I", b, 0)
    symbols = [struct.unpack_from("<HHI", b, so + i * 8) for i in range(sc)]

    def letters_text(to, tc):
        let = struct.unpack_from(f"<{tc}H", b, to)
        out, i = [], 0
        while i < len(let):
            c = let[i]
            if c == 0x8000:
                break
            if c == 0x8001:
                out.append(" "); i += 2; continue
            if c >= 0x8000:  # autres codes de controle : ignores (avec leur argument)
                i += 2; continue
            out.append(chr(symbols[c][1]) if c < sc else "?")
            i += 2  # (symbole, crenage)
        return "".join(out)

    msgs = []
    for k in range(mc):
        po, pc, _, _ = struct.unpack_from("<4I", b, mo + k * 16)
        paras = []
        for j in range(pc):
            lo, lc, _, _, _ = struct.unpack_from("<5I", b, po + j * 20)
            lines = []
            for n in range(lc):
                to, _z, tc, _tc2, _w, _ = struct.unpack_from("<4I2f", b, lo + n * 24)
                if 0 < tc < 8192:
                    lines.append(letters_text(to, tc))
            para = "\n".join(lines)
            if para not in paras:  # certains messages repetent le meme paragraphe (variantes)
                paras.append(para)
        msgs.append("\n\n".join(paras))
    out = {}
    for i in range(ec):
        _h, msg = struct.unpack_from("<II", b, eo + i * 0x28)
        name = b[eo + i * 0x28 + 8:eo + i * 0x28 + 0x28].split(b"\0")[0].decode("ascii", "replace")
        if msg < len(msgs):
            out[name] = msgs[msg]
    return out


TEXT_SOURCES = [
    # (fichier, membre) ; les versions _us contiennent l'anglais, la version sans suffixe le japonais
    ("txtmess/txt_core_us.dat", "txt_core.tmd"),
    ("txtmess/txt_core_add_us.dat", "txt_core_add.tmd"),
    ("txtmess/txt_pause_us.dat", "txt_pause.tmd"),
    ("txtmess/txt_pause_add_us.dat", "txt_pause_add.tmd"),
    ("txtmess/txt_hud_us.dat", "txt_hud.tmd"),
    ("txtmess/txt_hud_add_us.dat", "txt_hud_add.tmd"),
    ("txtmess/txt_shop_us.dat", "txt_shop.tmd"),
    ("txtmess/txt_chapter_us.dat", "txt_chapter.tmd"),
    ("txtmess/txt_support_us.dat", "txt_support.tmd"),
    ("txtmess/txt_credit_us.dat", "txt_credit.tmd"),
    ("txtmess/txt_dlc1_us.dat", "txt_dlc1.tmd"),
    ("txtmess/txt_dlc2_us.dat", "txt_dlc2.tmd"),
    ("txtmess/txt_dlc3_us.dat", "txt_dlc3.tmd"),
    ("ui/ui_core_us.dat", "messcore.mcd"),
    ("ui/ui_core_2_us.dat", "messcore_2.mcd"),
    ("ui/ui_core_pc_us.dat", "messcore_pc.mcd"),
    ("ui/ui_pause_us.dat", "messpause.mcd"),
    ("ui/ui_shop_us.dat", "messshop.mcd"),
    ("ui/ui_hud_us.dat", "messhud.mcd"),
    ("ui/ui_chapter_us.dat", "messchapter.mcd"),
    ("ui/ui_ending_us.dat", "messending.mcd"),
    ("ui/ui_ending_dlc_us.dat", "messending_dlc.mcd"),
    ("ui/ui_ending_dlca_us.dat", "messending_dlca.mcd"),
    ("ui/ui_title_us.dat", "messtitle.mcd"),
    ("ui/ui_dlc1_us.dat", "messdlc1.mcd"),
    ("ui/ui_event_us.dat", "messevent.mcd"),
    ("ui/ui_hud_hacking_us.dat", "messhud_hacking.mcd"),
    ("ui/ui_option_us.dat", "messoption.mcd"),
]


def english_texts() -> dict[str, tuple[str, str]]:
    """{cle: (texte, source)} de toutes les sources anglaises (la premiere source gagne)."""
    out: dict[str, tuple[str, str]] = {}
    for f, m in TEXT_SOURCES:
        b = dat_member(f, m)
        if b is None:
            continue
        table = tmd(b) if m.endswith(".tmd") else mcd(b)
        for k, v in table.items():
            out.setdefault(k, (v, f"{f}:{m}"))
    return out


# --- tables binaires de core/coregm.dat ----------------------------------------------------------

def que(b: bytes):
    """QuestProgressInfo.que : '<4sfIII' (magic, 1.0, offset=0x14, taille=24, nombre) puis enregistrements
    '<HBBIHHiII' : quete (decimal), groupe d'etat, ?, ?, emplacement 1..5, ?, objet requis (-1 = aucun),
    quantite, ?."""
    magic, ver, off, size, n = struct.unpack_from("<4sfIII", b, 0)
    out = []
    for i in range(n):
        q, grp, u1, u2, slot, u3, item, num, u4 = struct.unpack_from("<HBBIHHiII", b, off + i * size)
        out.append(dict(quest=q, group=grp, slot=slot, item=item, count=num, raw_unknown=[u1, u2, u3, u4]))
    return out


def qch(b: bytes):
    """QuestChapterData.qch : '<4sfIII' (magic, 1.0, offset=0x14, taille=130, nombre=60) puis enregistrements :
    u16 quete (decimal) + 128 octets, un par entree de ChapterData.cha (indice), 0 = indisponible."""
    magic, ver, off, size, n = struct.unpack_from("<4sfIII", b, 0)
    out = []
    for i in range(n):
        r = b[off + i * size: off + (i + 1) * size]
        out.append((struct.unpack_from("<H", r, 0)[0], list(r[2:])))
    return out


def cha(b: bytes):
    """ChapterData.cha : '<4sfIII' (magic 'SCH', 1.0, offset=0x14, taille=80, nombre) ; enregistrement :
    u8 indice, u8 chapitre, u8 sous-chapitre, u8 variante, u32 groupe de routes (0=A,1=B,2=A+B,3=C/D),
    u32 personnage (1=2B, 2=9S, 3=2B/9S, 4=A2, 6=?, 0=generique), u16 phase (0x100 -> p100), sous-phase (texte)."""
    magic, ver, off, size, n = struct.unpack_from("<4sfIII", b, 0)
    out = []
    for i in range(n):
        r = b[off + i * size: off + (i + 1) * size]
        idx, ch, sub, var = r[0], r[1], r[2], r[3]
        grp, chara = struct.unpack_from("<II", r, 4)
        phase = struct.unpack_from("<H", r, 12)[0]
        name = r[14:14 + 48].split(b"\0")[0].decode("ascii", "replace")
        out.append(dict(index=idx, chapter=ch, sub=sub, variant=var, route_group=grp, character=chara,
                        phase=f"p{phase:03x}", subphase=name))
    return out


def drp(b: bytes):
    """Tables .drp (DBO/DQR/DEM/DUE) : '<4sfIIIHH' (magic, 1.0, offset, taille A, taille B, nb A, nb B) ;
    table A (enregistrements) puis table B (paires u32 id, u32 valeur). Renvoie (magic, A brut, B)."""
    magic, ver, off, sa, sb, na, nb = struct.unpack_from("<4sfIIIHH", b, 0)
    A = [b[off + i * sa: off + (i + 1) * sa] for i in range(na)]
    bo = off + sa * na
    B = [struct.unpack_from("<II", b, bo + i * sb) for i in range(nb)]
    return magic.rstrip(b"\0").decode(), A, B


# --- hap (logique de phase) ------------------------------------------------------------------------

def hap_xml(z: bytes):
    """*_hap.z = XML compresse zlib (Shift-JIS) ; certains '&' ne sont pas echappes."""
    import xml.etree.ElementTree as ET
    import zlib
    t = zlib.decompress(z).decode("shift_jis", "replace")
    t = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", t)
    return ET.fromstring(t)


def _txt(e, tag):
    x = e.find(tag)
    return x.text if x is not None else None


def xml_layouts(root):
    """Entites placees (objId + position + parametres) avec le nom du hap et de l'action qui les place."""
    out = []
    for hap in root.iter("hap"):
        hname = _txt(hap, "name")
        for act in hap.iter("action"):
            aname = _txt(act, "name")
            for v in act.iter("value"):
                oid = v.find("objId")
                if oid is None:
                    continue
                pos = v.find("location/position")
                params = {}
                for pv in v.findall("param/value"):
                    params[_txt(pv, "name")] = _txt(pv, "body")
                out.append(dict(objId=oid.text, position=[float(x) for x in pos.text.split()] if pos is not None
                                else None, params=params, hap=hname, action=aname))
    return out


def xml_phase_jumps(root):
    out = []
    for hap in root.iter("hap"):
        for act in hap.iter("action"):
            ph, sp = act.find("phase"), act.find("subPhase")
            if ph is not None and sp is not None:
                out.append(dict(hap=_txt(hap, "name"), action=_txt(act, "name"), phase=ph.text, subPhase=sp.text))
    return out


def xml_cmd_args(root):
    """Paires (label, args) : action simple (<command><label/></command><args/>) et listes
    (<commands><items><value><command><command><label/></command><args/></command>)."""
    out = []

    def walk(e, hname, aname):
        kids = list(e)
        for i, k in enumerate(kids):
            if k.tag == "command" and k.find("label") is not None:
                args = None
                if i + 1 < len(kids) and kids[i + 1].tag == "args":
                    args = kids[i + 1].text
                out.append(dict(hap=hname, action=aname, label=k.find("label").text, args=args))
            else:
                walk(k, hname, aname)

    for hap in root.iter("hap"):
        for act in hap.findall("action"):
            walk(act, _txt(hap, "name"), _txt(act, "name"))
    return out


TAG_NAME, TAG_BODY = 0x5E237E06, 0xDBA80BB2


def yax_layouts(trees):
    """Comme xml_layouts pour les arbres YAX d'un .pak (noms de balises haches)."""
    out = []
    for t in trees:
        group = t[0][2] if t else ""
        for i, (ind, tag, v) in enumerate(t):
            if tag != cpk.TAG_OBJ:
                continue
            s = i
            while s > 0 and t[s][0] >= ind:
                s -= 1
            j = s + 1
            while j < len(t) and t[j][0] > t[s][0]:
                j += 1
            pos, params = None, {}
            for k in range(s + 1, j):
                if t[k][1] == cpk.TAG_POS and pos is None:
                    try:
                        pos = [float(x) for x in t[k][2].split()]
                    except ValueError:
                        pass
                if t[k][1] == TAG_NAME and k + 2 < j and t[k + 2][1] == TAG_BODY:
                    params[t[k][2]] = t[k + 2][2]
            out.append(dict(objId=v, position=pos, params=params, hap=group, action=None))
    return out


# --- generation ------------------------------------------------------------------------------------

class Ctx:
    def __init__(self):
        self.texts = english_texts()
        self.gm = cpk.dat_files(game_file("core/coregm.dat"))

    def t(self, key):
        v = self.texts.get(key)
        return v[0] if v else None

    def bxm(self, name):
        tree, _ = bxm.parse(self.gm[name])
        return tree


def kids(n, name=None):
    return [c for c in n["children"] if name is None or c["name"] == name]


def child_val(n, name):
    for c in n["children"]:
        if c["name"] == name:
            return c["value"]
    return None


def build_items(ctx: Ctx):
    items = []
    by_name = {}
    root = ctx.bxm("ItemInfoTable.bxm")
    state_names = {c["name"]: c["value"] for c in kids(kids(root, "StateName")[0])}
    for it in kids(kids(root, "Item")[0]):
        d = {"internal_name": it["name"]}
        for c in it["children"]:
            if c["children"]:
                d.setdefault("prices", {})[c["name"]] = {g["name"]: _int(g["value"]) for g in c["children"]}
            else:
                d[c["name"]] = _int(c["value"])
        uid = d.get("UniqueID")
        d["english_name"] = id_name(ctx, uid)
        d["english_help"] = ctx.t(f"CORE_ITEM_HELP_{uid:03d}") if isinstance(uid, int) and uid < 1000 else None
        items.append(d)
        by_name[it["name"]] = d
    weapons = []
    wroot = ctx.bxm("WeaponInfoTable.bxm")
    for w in kids(kids(wroot, "Weapon")[0]):
        d = {"internal_name": w["name"]}
        for c in w["children"]:
            if c["children"]:
                d.setdefault("levels", {})[c["name"]] = {g["name"]: _int(g["value"]) for g in c["children"]}
            else:
                d[c["name"]] = _int(c["value"])
        uid = d.get("UniqueID")
        d["english_name"] = ctx.t(f"CORE_WP_NAME_{uid}")
        weapons.append(d)
        by_name[w["name"]] = d
    chips = []
    proot = ctx.bxm("PSkillInfoTable.bxm")
    for p in kids(kids(proot, "PSkill")[0]):
        d = {"internal_name": p["name"]}
        for c in p["children"]:
            d[c["name"]] = _int(c["value"])
        d["english_name"] = id_name(ctx, d.get("UniqueID"))
        chips.append(d)
        by_name[p["name"]] = d
    return dict(item_state_names=state_names, items=items, weapons=weapons, chips=chips), by_name


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def id_name(ctx: Ctx, uid):
    """Nom anglais d'un identifiant unique (objets <1000, armes 1000-1999, puces 3000-3999, archives >=1e6)."""
    if not isinstance(uid, int) or uid < 0:
        return None
    if uid < 1000:
        return ctx.t(f"CORE_ITEM_NAME_{uid:03d}") or ctx.t(f"CORE_ITEM_NAME_{uid}")
    if uid < 2000:
        return ctx.t(f"CORE_WP_NAME_{uid}")
    if 3000 < uid < 4000:
        return ctx.t(f"CORE_PSV_SKILL_NAME_{uid - 3000:03d}")
    if uid >= 1000000:
        return ctx.t(f"CORE_ARCHIVE_{(uid // 1000) % 1000:03d}_{uid % 1000:03d}")
    return None


def build_phases(ctx: Ctx):
    out = {"phase_info": [], "sub_phase_files": {}, "chapters": [], "phase_jumps": {}}
    pi, _ = bxm.parse(cpk.dat_files(game_file("core/coreph.dat"))["PhaseInfo.bxm"])
    for ph in kids(kids(pi, "InfoList")[0], "Phase"):
        subs = [c["value"] for s in kids(ph, "SubPhase") for c in s["children"]]
        out["phase_info"].append({"phase": ph["attrs"].get("name"), "subphases": subs})
    files = ["ph1/p100.dat", "ph2/p200.dat", "ph3/p300.dat", "ph4/p400.dat"] + \
        sorted(n for n in all_names() if n.startswith("phf/") and n.endswith(".dat"))
    for f in files:
        d = cpk.dat_files(game_file(f))
        stem = f.split("/")[1][:-4]
        sub = d.get(f"{stem}_sub.bxm")
        if sub:
            tree, _ = bxm.parse(sub)
            rows = []
            for i, sp in enumerate(kids(tree, "SubPhase")):
                r = {"order": i}
                for c in sp["children"]:
                    r[c["name"]] = c["value"]
                rows.append(r)
            out["sub_phase_files"][stem] = rows
        z = d.get(f"{stem}_hap.z")
        if z:
            out["phase_jumps"][stem] = xml_phase_jumps(hap_xml(z))
    for c in cha(ctx.gm["ChapterData.cha"]):
        key = f"CHAPTER_NAME_{c['chapter']:02d}_{c['sub']:02d}"
        c["english_name"] = ctx.t(key + (f"_{c['variant']}" if c["variant"] else "")) or ctx.t(key) \
            or ctx.t(key + "_0")
        c["english_chapter"] = ctx.t(f"CHAPTER_NAME_{c['chapter']:02d}_00")
        out["chapters"].append(c)
    return out


def quest_hap_files():
    return sorted(n for n in all_names() if n.startswith("quest/") and n.endswith(".dat"))


def build_quests(ctx: Ctx, chapters):
    quests = {}

    def q(qid):
        return quests.setdefault(qid, {"id": qid})

    for f in quest_hap_files():
        stem = f.split("/")[1][:-4]
        base = stem.split("_")[0]
        q(base).setdefault("files", []).append(stem)
    for k, (v, src) in ctx.texts.items():
        m = re.match(r"PAUSE_QUEST_NAME_(q[0-9a-f]+)(_US)?$", k)
        if m:
            q(m.group(1))["english_name" + ("_us_variant" if m.group(2) else "")] = v
        m = re.match(r"PAUSE_QUEST_HELP_Q([0-9A-F]+)(_\d+_\d+)?/(.*)$", k)
        if m:
            q("q" + m.group(1).lower()).setdefault("help_texts", {})[(m.group(2) or "") + m.group(3)] = v
    for qid, row in qch(ctx.gm["QuestChapterData.qch"]):
        e = q(f"q{qid:03d}")
        av = []
        for i, val in enumerate(row):
            if val:
                c = chapters[i] if i < len(chapters) else None
                av.append({"chapter_index": i, "flag": val,
                           "subphase": c["subphase"] if c else None,
                           "chapter": f"{c['chapter']:02d}-{c['sub']:02d}" if c else None,
                           "chapter_name": c["english_name"] if c else None,
                           "route_group": c["route_group"] if c else None,
                           "character": c["character"] if c else None})
        e["availability"] = av
    for r in que(ctx.gm["QuestProgressInfo.que"]):
        if r["item"] < 0:
            continue
        q(f"q{r['quest']:03d}").setdefault("required_items", []).append(
            {"group": r["group"], "slot": r["slot"], "item_id": r["item"], "item_name": id_name(ctx, r["item"]),
             "count": r["count"]})
    mail = ctx.bxm("MailTable.bxm")
    for m in kids(mail):
        d = {c["name"]: c["value"] for c in m["children"]}
        qi = d.get("QuestId")
        if qi and qi != "-1":
            q(f"q{int(qi):03d}").setdefault("mails", []).append(
                {"mail": _int(d.get("MailNo")), "sender": d.get("Sender"), "state_before": d.get("StateBefore"),
                 "state_after": d.get("StateAfter"), "attachment": d.get("Attachment"),
                 "title": ctx.t(f"PAUSE_MAIL_{int(d['MailNo']):03d}")})
    mq = ctx.bxm("MsgQueInfo.bxm")
    for qn in kids(mq):
        d = {c["name"]: c["value"] for c in qn["children"] if not c["children"]}
        qi = d.get("QuestId")
        if qi:
            states = []
            for s in qn["children"]:
                if s["children"]:
                    states.append({c["name"]: c["value"] for c in s["children"]})
            q(f"q{qi.lower()}" if not qi.startswith("q") else qi).setdefault("msg_que_info_states", states)
    # recompenses (table de recompense non reliee aux quetes : liste brute)
    magic, A, B = drp(ctx.gm["QuestRewordData.drp"])
    rewards = []
    for r in A:
        idx, start, n, u1, u2, u3, u4 = struct.unpack("<7H", r)
        ent = B[start:start + n]
        extra = B[start + n:start + n + 2] if n else []
        rewards.append({"index": idx, "entries": [{"id": i, "id_name": id_name(ctx, i), "value": v} for i, v in ent],
                        "trailing_pair_entries": [{"id": i, "value": v} for i, v in extra],
                        "raw_unknown": [u1, u2, u3, u4]})
    return dict(quests=dict(sorted(quests.items())), quest_reward_tables=rewards)


def build_shops(ctx: Ctx, by_name):
    root = ctx.bxm("ShopInfoTable.bxm")
    shops = []
    for s in kids(root):
        d = {"internal_name": s["name"], "items": []}
        for c in s["children"]:
            if c["name"] == "Id":
                d["id"] = _int(c["value"])
            elif c["name"] == "StateName":
                d["state_names"] = {g["name"]: g["value"] for g in c["children"]}
            elif c["name"] == "Item":
                for it in c["children"]:
                    meta = by_name.get(it["name"], {})
                    d["items"].append({"internal_name": it["name"], "unique_id": meta.get("UniqueID"),
                                       "english_name": meta.get("english_name"),
                                       "states": {g["name"]: _int(g["value"]) for g in it["children"]}})
            else:
                d[c["name"]] = c["value"]
        sid = d.get("id")
        if isinstance(sid, int):
            nm = ctx.t(f"CORE_MAP_SHOP_{sid:04d}")
            d["english_name"] = nm.split("\n")[0] if nm else None
        shops.append(d)
    return {"shops": shops}


def all_layouts():
    """Entites placees dans tous les fichiers de logique (hap.z des phases/quetes/salles + core_hap.pak)."""
    out = []
    for n in sorted(all_names()):
        if not re.match(r"(ph\w|quest|st\d)/[^/]+\.dat$", n):
            continue
        d = cpk.dat_files(game_file(n))
        for k, v in d.items():
            if k.endswith("_hap.z"):
                root = hap_xml(v)
                for e in xml_layouts(root):
                    e["file"] = n
                    out.append(e)
                for c in xml_cmd_args(root):
                    c["file"] = n
                    out.append(c)
                for j in xml_phase_jumps(root):
                    j["file"] = n
                    out.append(j)
        del d
    trees = cpk.pak_yax(cpk.dat_files(game_file("core/corehap.dat"))["core_hap.pak"])
    for e in yax_layouts(trees):
        e["file"] = "core/corehap.dat:core_hap.pak"
        out.append(e)
    return out


def build_chests(ctx: Ctx, layouts):
    magic, A, B = drp(ctx.gm["BoxData.drp"])
    recs = []
    for i, r in enumerate(A):
        a0, a1, box, room, start, n, u6, u7 = struct.unpack("<HHIIHHII", r)
        recs.append({"index": i, "box_id": hex(box), "room_or_group": hex(room), "flags_a": a0, "flags_b": a1,
                     "unknown_u32_16": u6, "unknown_u32_20": u7,
                     "entries": [{"id": x, "id_name": id_name(ctx, x), "weight_or_rate": w}
                                 for x, w in B[start:start + n]]})
    by_box = {}
    for r in recs:
        by_box.setdefault(r["box_id"], []).append(r["index"])
    ents = []
    for e in layouts:
        if "objId" not in e or "ItemTable" not in e["params"]:
            continue
        tbl = e["params"]["ItemTable"]
        try:
            tbl = hex(int(tbl, 0))
        except (TypeError, ValueError):
            pass
        cand = by_box.get(tbl, [])
        try:
            kind = int(e["objId"][2:], 16)  # ba2014 -> 0x2014 = champ flags_a de BoxData
        except ValueError:
            kind = None
        exact = [i for i in cand if recs[i]["flags_a"] == kind]
        ent = {"objId": e["objId"], "item_table": tbl, "position": e["position"], "file": e["file"],
               "hap": e["hap"], "action": e["action"], "boxdata_records_with_same_box_id": cand,
               "boxdata_records_matching_box_id_and_objid": exact}
        if len(exact) == 1:
            ent["contents"] = recs[exact[0]]["entries"]
        ents.append(ent)
    return {"boxdata_records": recs, "chest_entities": ents}


# Correspondance code de terminal -> nom affiche : DEDUITE (pas de table explicite trouvee), avec la preuve.
AP_CODE_GUESS = {
    "ft_BK": ("CORE_MAP_TRANS_0001", "high", "objets ba1000 de la Bunker (qb40), MiscState 'ft_BK' dans p300 'バンカーセーブ禁止'"),
    "ft_RC": ("CORE_MAP_TRANS_0002", "high", "ba1000 dans r110 ; p200 'レジキャン端末故障/復旧' (terminal du camp)"),
    "ft_CC": ("CORE_MAP_TRANS_0003", "high", "ba1100 groupe '自販機＿中央エリア' (zone centrale)"),
    "ft_CRb": ("CORE_MAP_TRANS_0004", "medium", "ba1100 groupe '自販機＿ロボット山入り口' (entree de l'usine)"),
    "ft_CS": ("CORE_MAP_TRANS_0005", "low", "ba1100 groupe '自販機＿ショッピングモール付近' (pres du centre commercial) ; "
              "seul terminal de ville restant"),
    "ft_DC": ("CORE_MAP_TRANS_0006", "medium", "ba1100 r150 groupe '砂漠入口' (entree du desert)"),
    "ft_DI": ("CORE_MAP_TRANS_0007", "medium", "ba1100 r150 groupe '砂漠内部' (interieur du desert)"),
    "ft_DO": ("CORE_MAP_TRANS_0008", "high", "ba1100 r150 groupe '砂漠油田' (champ petrolifere)"),
    "ft_DD": ("CORE_MAP_TRANS_0009", "high", "ba1100 r150 groupe '砂漠団地' (complexe residentiel)"),
    "ft_AP": ("CORE_MAP_TRANS_0010", "low", "ba1100 r130 groupe '遊園地' action '飛行機遊具前' (parc d'attractions)"),
    "ft_AP_C": ("CORE_MAP_TRANS_0011", "low", "chaine de l'exe uniquement (C = Coaster ?)"),
    "ft_AP_T": ("CORE_MAP_TRANS_0012/0013", "low", "chaine de l'exe uniquement (T = Theater ?)"),
    "ft_AP_T2": ("CORE_MAP_TRANS_0012/0013", "low", "chaine de l'exe uniquement (T2 = 2e terminal du theatre ?)"),
    "ft_PV": ("CORE_MAP_TRANS_0014", "medium", "MiscState 'ft_PV' dans p200 ; PV = Pascal Village (cf. shop_PV_*)"),
    "ft_FC": ("CORE_MAP_TRANS_0015", "medium", "ba1100 r160 groupe '森' (foret)"),
    "ft_FC2": ("CORE_MAP_TRANS_0016", "high", "ba1100 r160 groupe '城前' (devant le chateau)"),
    "ft_FC3": ("CORE_MAP_TRANS_0017", "high", "ba1100 r160 groupe '王室前' (devant la salle royale)"),
    "ft_RME": ("CORE_MAP_TRANS_0018", "medium", "ba1100 r120 (RM = Robot Mountain = usine, E = entree ?)"),
    "ft_RMI2": ("CORE_MAP_TRANS_0019/0020", "low", "ba1100 r520 groupe '開始地点' (point de depart, interieur usine)"),
    "ft_RMI": ("CORE_MAP_TRANS_0019/0020", "low", "ba1100 r520 groupe 'ボス前' (avant le boss, interieur usine)"),
    "ft_SC": ("CORE_MAP_TRANS_0021", "high", "ba1100 r170 ; p200 '水没都市端末故障' (terminal de la ville engloutie)"),
    "ft_AS": ("CORE_MAP_TRANS_0022", "medium", "ba1100 r200 (y=-105, souterrain) ; p200 'エイリアンシップ端末故障' "
              "(vaisseau alien, situe dans la caverne)"),
}
AP_CODES_IN_EXE = ["ft_BK", "ft_RMI", "ft_RMI2", "ft_AP", "ft_RC", "ft_CC", "ft_CRb", "ft_CS", "ft_DC", "ft_DI",
                   "ft_DO", "ft_DD", "ft_AP_C", "ft_AP_T", "ft_AP_T2", "ft_RME", "ft_AS", "ft_PV", "ft_FC", "ft_FC2",
                   "ft_FC3", "ft_SC"]


def build_access_points(ctx: Ctx, layouts):
    names = {k: v[0] for k, v in sorted(ctx.texts.items()) if k.startswith("CORE_MAP_TRANS_")}
    terminals = [{"objId": e["objId"], "codeName": e["params"].get("codeName"), "position": e["position"],
                  "file": e["file"], "hap": e["hap"], "action": e["action"]}
                 for e in layouts if "objId" in e and "codeName" in e["params"]]
    setvars = [{"file": c["file"], "hap": c["hap"], "action": c["action"], "args": c["args"]}
               for c in layouts if c.get("label") == "MiscState.setvar" and c.get("args")
               and "ft_" in c["args"]]
    locks = [{"file": c["file"], "hap": c["hap"], "action": c["action"], "label": c["label"], "args": c["args"]}
             for c in layouts if c.get("label", "").startswith("BehaviorTransporter")]
    found = {t["codeName"] for t in terminals} | {re.sub(r'^"?(ft_\w+).*', r"\1", s["args"]) for s in setvars}
    mapping = []
    for code in AP_CODES_IN_EXE:
        key, conf, why = AP_CODE_GUESS.get(code, (None, None, None))
        keys = key.split("/") if key else []
        if len(keys) > 1:
            keys = [keys[0], keys[0][:-4] + keys[1]]
        mapping.append({"code": code, "inferred_name_keys": keys,
                        "inferred_names": [names.get(k) for k in keys], "confidence": conf, "evidence": why,
                        "seen_in_layouts_or_commands": code in found})
    return {"note": "Terminaux = objets ba1000 (Bunker/camp) et ba1100 ('自販機' = distributeur) avec le parametre "
                    "codeName ft_XX ; deverrouillage par la variable MiscState 'ft_XX true/false'. La correspondance "
                    "code -> nom affiche est DEDUITE (voir confidence/evidence), pas lue dans une table.",
            "english_names": names, "code_to_name_inferred": mapping,
            "codes_in_exe_v104": AP_CODES_IN_EXE, "terminal_entities": terminals,
            "unlock_variable_commands": setvars, "transporter_commands": locks}


# Traduction NON officielle (par l'assistant) des commentaires japonais de pf30_sub.bxm.
ENDING_COMMENT_EN = {
    "E": "unused", "F": "route B prologue: leave the rebuild mini-game idle for a long time",
    "G": "route B prologue: run away without boarding the flight unit",
    "H": "routes A/B: run away when encountering the giant machine",
    "I": "route A: abandon 9S in the Copied City and run away", "J": "route A: kill the peace-seeking machines",
    "K": "anytime: eat the mackerel",
    "L": "routes A/B: leave the area between the Resistance Camp attack and the Eve fight",
    "M": "routes C/D: run from the village during the Pascal's Village attack mission",
    "N": "routes C/D: wipe out the Pascal's Village residents", "O": "routes C/D: run away during the big melee",
    "P": "routes C/D: run away while 2B is moving to the shopping mall",
    "Q": "routes C/D: run away while 9S is moving to the shopping mall",
    "R": "routes C/D: kill the evacuated Pascal's Village residents",
    "S": "routes C/D: flee the City Ruins leaving Devola and Popola behind",
    "T": "anytime: remove the OS chip", "U": "anytime: self-destruct in the Bunker",
    "V": "routes C/D: leave the Tower main unit without hacking it",
    "W": "routes A/B: die at the prologue factory (Robot Mountain)",
    "X": "routes C/D: as A2, run away without saving 2B", "Y": "routes C/D: run away during the final Emil battle",
    "Z": "routes C/D: kill Pascal in front of the Resistance Camp",
}


def build_endings(ctx: Ctx, phases, layouts):
    out = {"endings": [], "ending_jumps": [], "scene_state_endings": []}
    pf30 = {r["Name"]: r for r in phases["sub_phase_files"].get("pf30", [])}
    for i in range(1, 27):
        letter = ctx.t(f"CREDIT_END_{i:02d}")
        sub = pf30.get(f"Ending_{letter}") if letter else None
        out["endings"].append({"letter": letter, "title": ctx.t(f"CREDIT_END_TITLE_{i:02d}"),
                               "pf30_subphase": sub["Name"] if sub else None,
                               "pf30_comment_ja": sub.get("Comment") if sub else None,
                               "pf30_comment_en_unofficial": ENDING_COMMENT_EN.get(letter) if sub else None})
    for j in layouts:
        if "subPhase" in j and j["subPhase"] and j["subPhase"].startswith(("Ending_", "EndRoll", "BackTitle")):
            out["ending_jumps"].append(j)
        if j.get("label") in ("SceneStateSystem.set", "MiscState.unlockAchievement") and                 j.get("file", "").startswith("phf/"):
            out["scene_state_endings"].append(j)
        elif j.get("label") == "SceneStateSystem.set" and (j.get("args") or "").startswith("ending_"):
            out["scene_state_endings"].append(j)
    out["other_ending_subphases"] = {k: v for k, v in phases["sub_phase_files"].items() if k.startswith("pf")}
    return out


def build_all(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = Ctx()

    def dump(name, obj):
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        print("ecrit", out_dir / name)

    items, by_name = build_items(ctx)
    dump("items.json", items)
    phases = build_phases(ctx)
    dump("phases.json", phases)
    dump("quests.json", build_quests(ctx, phases["chapters"]))
    dump("shops.json", build_shops(ctx, by_name))
    layouts = all_layouts()
    dump("endings.json", build_endings(ctx, phases, layouts))
    dump("chests.json", build_chests(ctx, layouts))
    dump("access_points.json", build_access_points(ctx, layouts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs" / "research"))
    a = ap.parse_args()
    print("cache:", CACHE)
    build_all(Path(a.out))
