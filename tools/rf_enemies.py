"""Ennemis et donnees d'unite (Intel > Unit Data) de NieR:Automata - LECTURE SEULE des CPK.

Usage : python tools/rf_enemies.py [--out docs/research]   -> enemies_by_area.json

- Catalogue : core/coregm.dat:EmList.bxm (189 entrees, 1 entree = (EmID, setType, setFlag) -> SaveID = bit de
  donnee d'unite). Noms : PAUSE_ENEMY_%04x (format lu dans l'exe, RVA 0xce6640) avec la valeur UIID lue en
  hexadecimal ; nom du type = Type[TypeID].UIID, variante = UIID de l'entree ; categorie = PAUSE_ENEMY_CTGR_%02x.
  Noms dans ui/ui_pause_us.dat:messpause.mcd, descriptions dans txtmess/txt_pause_add_us.dat (meme cle).
- Placements : toutes les valeurs ayant un objId em* dans les *_hap.pak (YAX ; FONT FOI : l'exe 0x3b8020 charge
  %s_hap.pak et ne lit %s_hap.z que si le .pak manque ; le hap.z n'est lu que dans ce cas) et les *_grp.pak
  (YAX, balises = crc32 du nom de balise) de ph1-4, phf, st1/st2/st5, quest/, core/corehap.dat et des cellules
  wd*. Groupes lus dans le bloc de groupes de chaque .pak (zlib v4 ou YAX brut v1, cpk.pak_group_block).
- Donnees debloquees par la mort d'un placement : regle de l'exe 0x8257C0 (death_match, toutes les lignes).
  Deux sortes : 'layout' (enemi pose, position fixe) et 'generator' (敵発生機 : liste d'objId tires au hasard
  autour de points).
- Proprietaire : jetons des groupes (code 0xf3b97443 = crc32(nom de sous-phase), 0x35c92545 = crc32('qXXX/ETAT')),
  en remontant les parents.
Un fichier .dat a la fois (cache disque de extract_research).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import bxm  # noqa: E402
import extract_research as er  # noqa: E402
import world_positions as wp  # noqa: E402  (members : cache des cellules wd)

TOK_SUBPHASE, TOK_QUEST = 0xF3B97443, 0x35C92545

# Salles (fichiers st*/rNNN.dat) : deduit des noms de groupes/hap japonais de chaque fichier (confiance moyenne)
ROOMS = {
    "r100": "City Ruins", "r110": "Resistance Camp", "r120": "Abandoned Factory", "r130": "Amusement Park",
    "r140": "Pascal's Village", "r150": "Desert Zone", "r160": "Forest Zone / Forest Castle",
    "r170": "Flooded City", "r200": "City Ruins (crater / underground)", "r500": "Tower",
    "r501": "Copied City", "r502": "Hidden underground cave (Emil's Residence route?)",
    "r520": "Abandoned Factory (underground)", "r530": "Amusement Park (theater underground)",
    "r5a2": "Resource Recovery Unit (Amusement Park, God Box)",
}
ROOM_EVIDENCE = {
    "r100": "groupes 遊園地へのバリケード, 復帰ポイント_都市側森前/パスカル村前, EM_巨大ロボ襲来用",
    "r110": "groupes レジスタンスキャンプ, レジスタンスリーダー, 双子, q650/q651",
    "r120": "groupes ロボット山-オブジェクト関連, 狂った宗教後, 工場停止後",
    "r130": "groupes 遊園地NPC, コースター, パレード, 資源回収ユニットエレベータ",
    "r140": "groupes パスカル村_*", "r150": "groupes 砂漠, 砂レジ女, 小砂漠/大砂漠",
    "r160": "groupes 森の城_城内, 森の城_森部分, パスカル村へ続く大扉",
    "r170": "groupes 釣りポイント_水没, 怪獣ボスの残骸, 資源回収ユニット",
    "r200": "groupes 陥没内, 地下都市, コピー都市のエレベーターロック, 塔_*, 谷の主, ロボット山連絡路",
    "r500": "groupes 図書館, 赤い少女戦の扉, 塔上層部", "r501": "groupes アダム戦中無効, ヨルハ死体",
    "r502": "groupe 隠し地下洞窟", "r520": "groupes ロボット山地下, 地下工場, 教祖部屋",
    "r530": "groupe エリア切り替えエリア_劇場地下", "r5a2": "groupe エリア切り替え_資源回収ユニット(遊園地)",
}

# mots-cles -> zone (ordre = priorite ; japonais des noms de hap/groupes/commentaires, anglais des sous-phases)
AREA_KEYS = [
    (r"^Hack\(|^Stage\(", "Hacking space (virtual)"), ("谷底", "Ravine / valley floor (谷底)"),
    ("コピー都市", "Copied City"), ("Copy_City", "Copied City"),
    ("水没都市", "Flooded City"), ("Submerge", "Flooded City"), ("怪獣", "Flooded City (sea / Grun)"),
    ("Kaiju", "Flooded City (sea / Grun)"),
    ("エイリアンシップ", "Alien Ship"), ("Alien_Ship", "Alien Ship"),
    ("資源回収ユニット", "Resource Recovery Unit"),
    ("ショッピングモール", "Commercial Facility"), ("ShopM", "Commercial Facility"),
    ("森の城", "Forest Castle"), ("Forest_Castle", "Forest Castle"), ("城内", "Forest Castle"),
    ("団地", "Desert Housing"), ("Danchi", "Desert Housing"),
    ("レジスタンスキャンプ", "Resistance Camp"), ("レジキャン", "Resistance Camp"),
    ("Resistance_Camp", "Resistance Camp"), ("ResiCamp", "Resistance Camp"),
    ("パスカル村", "Pascal's Village"), ("パスカルの村", "Pascal's Village"), ("Pascal_Village", "Pascal's Village"),
    ("遊園地", "Amusement Park"), ("Amusement_Park", "Amusement Park"), ("Park", "Amusement Park"),
    ("地下工場", "Abandoned Factory (underground)"), ("ロボット山", "Abandoned Factory"),
    ("RobotM", "Abandoned Factory"), ("工場", "Abandoned Factory"),
    ("バンカー", "Bunker"), ("バンカ-", "Bunker"), ("bunker", "Bunker"), ("Bunker", "Bunker"),
    ("Banker", "Bunker"), ("buker", "Bunker"),
    (r"(?<!鉄)塔(?!出現)", "Tower"), ("Tower", "Tower"),
    ("砂漠", "Desert Zone"), ("Desert", "Desert Zone"),
    ("廃墟都市", "City Ruins"), ("ハイキョ都市", "City Ruins"), ("虚構都市", "City Ruins"), ("Ruined_City", "City Ruins"),
    ("陥没", "City Ruins (crater)"),
    ("森", "Forest Zone"), ("Forest", "Forest Zone"),
]


def area_of(text: str | None):
    if not text:
        return None
    for k, a in AREA_KEYS:
        if re.search(k, text):
            return a
    return None


def route_hint(names):
    """'Aルート', 'C,Dルート', 'Bルート以降'... dans la chaine de noms -> liste de lettres."""
    out = []
    for n in names:
        for m in re.finditer(r"([A-DＡ-Ｄ](?:\s*[,、・/]\s*[A-DＡ-Ｄ])*)\s*ルート(以降)?", n or ""):
            s = m.group(1).translate(str.maketrans("ＡＢＣＤ", "ABCD"))
            letters = re.findall(r"[A-D]", s)
            if m.group(2):
                letters = [c for c in "ABCD" if c >= letters[0]]
            out.append("".join(letters))
    return sorted(set(out))


# --- textes -------------------------------------------------------------------------------------

def load_texts():
    names = er.mcd(cpk.dat_files(er.game_file("ui/ui_pause_us.dat"))["messpause.mcd"])
    desc = {}
    for f, m in [("txtmess/txt_pause_us.dat", "txt_pause.tmd"), ("txtmess/txt_pause_add_us.dat", "txt_pause_add.tmd")]:
        for k, v in er.tmd(cpk.dat_files(er.game_file(f))[m]).items():
            if k.startswith("PAUSE_ENEMY_"):
                desc[k] = v
    core = {}
    for f, m in [("ui/ui_dlc1_us.dat", "messdlc1.mcd"), ("ui/ui_core_us.dat", "messcore.mcd")]:
        for k, v in er.mcd(cpk.dat_files(er.game_file(f))[m]).items():
            if k.startswith(("CORE_RECORD_ENEMY_", "CORE_ENEMY_")):
                core.setdefault(k, v)
    quests = {}
    for f, m in [("txtmess/txt_pause_us.dat", "txt_pause.tmd"), ("txtmess/txt_pause_add_us.dat", "txt_pause_add.tmd")]:
        for k, v in er.tmd(cpk.dat_files(er.game_file(f))[m]).items():
            mm = re.match(r"PAUSE_QUEST_NAME_(q[0-9a-f]+)$", k)
            if mm:
                quests.setdefault(mm.group(1), v)
    return names, desc, core, quests


def _hexkey(v):
    if v in (None, "", "-1"):
        return None
    return int(v, 16)


def build_catalogue(gm, names, desc, core):
    tree, _ = bxm.parse(gm["EmList.bxm"])
    sec = {c["name"]: c for c in tree["children"]}

    def rows(n):
        return [{k["name"]: k["value"] for k in r["children"]} for r in sec[n]["children"]]

    def nm(key):
        return names.get(key + "_US") or names.get(key)

    cat_ui = {int(r["CategoryID"]): _hexkey(r["UIID"]) for r in rows("Category")}
    type_ui = {int(r["TypeID"]): _hexkey(r["UIID"]) for r in rows("Type")}
    entries = []
    for i, r in enumerate(rows("EmList")):
        cat, typ = int(r["Category"]), int(r["Type"])
        tk = f"PAUSE_ENEMY_{type_ui[typ]:04x}" if type_ui.get(typ) is not None else None
        vu = _hexkey(r.get("UIID"))
        vk = f"PAUSE_ENEMY_{vu:04x}" if vu is not None else None
        rep = _hexkey(r.get("RepUIID"))
        tname, vname = nm(tk) if tk else None, nm(vk) if vk else None
        full = tname + (f" ({vname})" if vname else "") if tname else vname
        ck = f"PAUSE_ENEMY_CTGR_{cat_ui[cat]:02x}" if cat_ui.get(cat) is not None else None
        rec_key = None
        for k in ([f"CORE_RECORD_ENEMY_{vu:04x}"] if vu is not None else []) + \
                 ([f"CORE_RECORD_ENEMY_{type_ui[typ]:04x}", f"CORE_ENEMY_{type_ui[typ]:04x}"] if tk else []):
            if k in core:
                rec_key = k
                break
        entries.append({
            "list_index": i, "SortID": int(r["SortID"]), "SaveID": int(r["SaveID"]), "EmID": r["EmID"],
            "UmID": r["UmID"], "setType": int(r["setType"]), "setFlag": int(r["setFlag"]),
            "bDie": int(r["bDie"]), "bTalk": int(r["bTalk"]), "QueID": r["QueID"],
            "category": cat, "category_name": names.get(ck) if ck else None, "type": typ,
            "type_key": tk, "type_name": tname, "variant_key": vk, "variant_name": vname,
            "unit_data_name": full,
            "description": desc.get(vk) or desc.get(tk) if (vk or tk) else None,
            "alt_description_key": f"PAUSE_ENEMY_{rep:04x}" if rep is not None else None,
            "core_record_key": rec_key, "core_record_name": core.get(rec_key) if rec_key else None,
        })
    acdb, _ = bxm.parse(gm["AcdbEnemySet.bxm"])
    acdb_rows = [{k["name"]: k["value"] for k in r["children"]} for r in acdb["children"]]
    hr, _ = bxm.parse(gm["HackingRandom_EmId.bxm"])
    hr_rows = [{k["name"]: k["value"] for k in r["children"]} for r in hr["children"]]
    return entries, acdb_rows, hr_rows


# --- regle de deblocage de l'exe v1.04 (0x8257C0, mode 'mort') -------------------------------------------------
# (deplacee ici depuis logic_gaps_enemies.py, qui la reutilise) : toutes les lignes EmList qui correspondent sont
# debloquees : EmID egal, setType egal, (setFlag du placement & masque) == masque (EmList setFlag 0 -> 0x10,
# 1 -> 0x10000010) ; lignes de mode 0 (bDie=1, bTalk=0) seulement ; exclusions codees en dur.
OBJ_PREFIX_NUM = {"pl": 0x1, "em": 0x2, "bg": 0xC}


def objid_num(s):
    m = re.match(r"(pl|em|bg)([0-9a-f]{4})$", s or "")
    return (OBJ_PREFIX_NUM[m.group(1)] << 16) | int(m.group(2), 16) if m else None


def mask_of(emlist_setflag: int) -> int:
    return {0: 0x10, 1: 0x10000010}.get(emlist_setflag, 0)


def mode_of(rec) -> int:
    if rec["bTalk"]:
        return 1 if not rec["bDie"] else -1
    return 0 if rec["bDie"] else -1


def death_match(rec, objId, setType, setFlag, emp=False):
    """Regle de 0x8257C0 en mode 'mort' pour une ligne d'EmList."""
    if mode_of(rec) != 0 or rec["EmID"] != objId:
        return False
    st = 10 if emp else (setType or 0)
    sf = setFlag or 0
    if objId == "em0000" and st == 2:
        sf |= 0x10
    num = objid_num(objId)
    excluded = {(0x21030, 6), (0x25000, 1), (0x25000, 5), (0x26000, 1), (0x26000, 2)}
    if (num, st) in excluded or num in (0x2B010, 0x2B041, 0x2B051, 0x2B061):
        return False
    ignore_st = num in (0x20060, 0x20061, 0x20090) or (num == 0x20040 and st != 10)
    if num == 0x20040 and rec["setType"] == 10:
        ignore_st = False
    if not ignore_st and rec["setType"] != st:
        return False
    m = mask_of(rec["setFlag"])
    return not m or (sf & m) == m


def talk_match(rec, objId, setType, setFlag):
    """Regle de 0x825CB0 (dialogue, appele par 0x35776F) : lignes de mode 1 (bDie=0, bTalk=1), EmID egal.
    Categorie 5 (Village Machines, [ligne+4]) : PAS de test de setType ; exige la variable 'UI_namePV' (nom du
    village de Pascal connu, sinon rien) ; em005b avec setType 1 -> seulement SortID 0x4d (aucune ligne em005b :
    rien), em001b avec setType 1 -> SortID != 0x4e. Autres categories : setType egal et (masque == 0 ou
    setFlag & masque != 0). setType = celui du PNJ a qui l'on parle (DEDUIT de l'argent r8d)."""
    if mode_of(rec) != 1 or rec["EmID"] != objId:
        return False
    st, sf = setType or 0, setFlag or 0
    if rec["category"] == 5:
        if objId == "em005b" and st == 1:
            return rec["SortID"] == 0x4D
        if objId == "em001b" and st == 1:
            return rec["SortID"] != 0x4E
        return True
    if rec["setType"] != st:
        return False
    m = mask_of(rec["setFlag"])
    return not m or bool(sf & m)


def match_records_talk(by_em, em, st, sf):
    return sorted({e["SaveID"] for e in by_em.get(em, []) if talk_match(e, em, st, sf)})


def match_records_exe(by_em, em, st, sf):
    """SaveIDs debloques par la mort de ce placement (regle exe, toutes les lignes)."""
    return sorted({e["SaveID"] for e in by_em.get(em, []) if death_match(e, em, st, sf)})


def match_record(by_em, em, st, sf):
    """Entree EmList pour un placement (EmID, setType, setFlag). Renvoie (entree, qualite)."""
    c = by_em.get(em)
    if not c:
        return None, "no_emlist_entry"
    st = 0 if st is None else st
    same = [e for e in c if e["setType"] == st]
    if same:
        # le sens de setFlag (EmList : 0 / 1 = variantes bouclier / bouclier EM) n'est pas relie au champ setFlag
        # (masque de bits) des placements : non resolu -> variante sans setFlag si elle existe
        base = [e for e in same if e["setFlag"] < 0]
        if base:
            return base[0], "setType" if len(same) == 1 else "setType_flag_variants_unresolved"
        return same[0], "setType_ambiguous_setFlag"
    if len(c) == 1:
        return c[0], "emid_only"
    base = [e for e in c if e["setType"] == 0 and e["setFlag"] < 0]
    if base:
        return base[0], "fallback_setType0_low"
    return None, "emid_multiple_no_setType_match"


# --- arbres hap (XML ou YAX) ----------------------------------------------------------------------

TAGS = set("""root version group count id name parent tokens size value code attribute priority comment hap action
layouts normal location position rotation objId setType setFlag param body items points nodes point radius rate
spawnRange createRange levelRange min max relativeLevel area dist puid""".split())


def yax_to_et(tree, H):
    root = ET.Element("hap")
    stack = [(-1, root)]
    for ind, tag, val in tree:
        while stack[-1][0] >= ind:
            stack.pop()
        e = ET.SubElement(stack[-1][1], H.get(tag, f"h{tag:08x}"))
        e.text = val
        stack.append((ind, e))
    return root


def _t(e, tag):
    x = e.find(tag)
    return x.text if x is not None else None


def _int(v):
    try:
        return int(v, 0)
    except (TypeError, ValueError):
        return None


def _pos(s):
    try:
        v = [float(x) for x in s.split()]
        return [round(x, 2) for x in v[:3]] if len(v) >= 3 else None
    except (AttributeError, ValueError):
        return None


def hap_placements(hap):
    """[(action, value_element, kind)] pour toutes les valeurs ayant un objId em*."""
    out = []

    def walk(e, act):
        for c in e:
            if c.tag == "action":
                walk(c, c)
                continue
            oid = c.find("objId")
            if oid is not None and (oid.text or "").startswith("em") and act is not None:
                out.append((act, c))
            walk(c, act)

    walk(hap, None)
    return out


def describe(act, val):
    oid = _t(val, "objId")
    params = {}
    for pv in val.findall("param/value"):
        n, b = _t(pv, "name"), _t(pv, "body")
        if n:
            params[n] = b
    d = {"objId": oid, "setType": _int(_t(val, "setType")), "setFlag": _int(_t(val, "setFlag")),
         "action": _t(act, "name"), "action_code": _t(act, "code")}
    pos = _pos(_t(val, "location/position"))
    pts = act.find("points")
    if pts is not None and act.find("items") is not None:
        d["kind"] = "generator"
        d["rate"] = _int(_t(val, "rate"))
        d["points"] = [p for p in (_pos(_t(v, "point")) for v in pts.findall("nodes/value")) if p]
        lr = act.find("levelRange")
        if lr is not None:
            d["level_range"] = [_int(_t(lr, "min")), _int(_t(lr, "max"))]
        sr = act.find("spawnRange")
        if sr is not None:
            d["spawn_range"] = [_int(_t(sr, "min")), _int(_t(sr, "max"))]
        d["position"] = d["points"][0] if d["points"] else None
    else:
        d["kind"] = "layout"
        d["position"] = pos
    lv = {k: v for k, v in params.items() if k.startswith("Lv")}
    if lv:
        d["level"] = lv
    other = {k: v for k, v in params.items() if not k.startswith("Lv") and k != "puid" and v}
    if other:
        d["params"] = other
    return d


# --- fichiers ------------------------------------------------------------------------------------

def source_files():
    names = er.all_names()
    return sorted(n for n in names
                  if re.match(r"(ph\w|phf|quest|st\d)/[^/]+\.dat$", n) or n == "core/corehap.dat") + \
        sorted(n for n in names if wp.WD_RE.match(n))


def _members(n):
    """Membres d'un .dat (cellules wd : seulement hap/pak/scp/lay, cache world_positions)."""
    return wp.members(n)


def owner_of_file(n, member=None):
    base = n.split("/")[1][:-4]
    if n == "core/corehap.dat" and member:
        base = member.split("_")[0]
    if n.startswith("quest/") or re.match(r"q[0-9a-f]{3}", base):
        return "quest", base.split("_")[0]
    if base.startswith("p"):
        return "phase", base
    if base.startswith("r"):
        return "room", base
    return "other", base


def build(out_dir: Path) -> dict:
    names, desc, core, qnames = load_texts()
    gm = cpk.dat_files(er.game_file("core/coregm.dat"))
    catalogue, acdb, hrand = build_catalogue(gm, names, desc, core)
    by_em = defaultdict(list)
    for e in catalogue:
        by_em[e["EmID"]].append(e)
    del gm

    # dictionnaire de hachages (sous-phases, etats de quete, chaines vues)
    phases = json.load(open(out_dir / "phases.json", encoding="utf8"))
    sp_hash = {}
    for p in phases["phase_info"]:
        for s in p["subphases"]:
            sp_hash.setdefault(zlib.crc32(s.encode()), (p["phase"], s))
    q_hash = {}
    states = ["RUN_%d" % i for i in range(0, 20)] + ["DONE", "CLR", "FIN", "FAIL", "FAIL_1", "FAIL_2", "FAIL_3",
                                                      "NONE", "START", "RUN"]
    for q in [f"q{i:03d}" for i in range(1000)] + [f"q{x}{i:02x}" for x in "abcef" for i in range(256)]:
        for st in states:
            for sep in "/_":
                q_hash.setdefault(zlib.crc32(f"{q}{sep}{st}".encode()), f"{q}/{st}")
    sub_meta = {}
    for ph, rows in phases["sub_phase_files"].items():
        for r in rows:
            sub_meta[(ph, r["Name"])] = r
    chap_of = subphase_chapters(phases)

    tag_names = set(TAGS)
    placements = []
    seen = set()
    files = source_files()
    # 1re passe legere : vocabulaire des balises (pour les arbres YAX)
    diag = Counter()
    for n in files:
        d = _members(n)
        for k, v in d.items():
            if k.endswith("_hap.z") and len(v) > 100:
                t = zlib.decompress(v).decode("shift_jis", "replace")
                tag_names |= set(re.findall(r"<([A-Za-z_][A-Za-z0-9_]*)>", t))
        del d
    H = {zlib.crc32(t.encode()): t for t in tag_names}

    for n in files:
        d = _members(n)
        groups = {}
        haps = []  # (hap element, member)
        # Le *_hap.pak fait foi (exe RVA 0x3b8020 charge %s_hap.pak, %s_hap.z seulement si le .pak manque) :
        # le hap.z n'est lu que pour un prefixe sans .pak. Groupes : bloc de groupes de chaque .pak (hap.pak et
        # grp.pak, zlib version 4 ou YAX brut version 1 : cpk.pak_group_block).
        pak_stems = {k[:-len("_hap.pak")] for k in d if k.endswith("_hap.pak")}
        for k, v in d.items():
            if k.endswith("_hap.z") and len(v) > 100 and k[:-len("_hap.z")] not in pak_stems:
                root = er.hap_xml(v)
                diag["hap_z_used_no_pak"] += 1
                for g in root.iter("group"):
                    gid = _t(g, "id")
                    if gid is None or g.find("name") is None:
                        continue
                    toks = [(_int(_t(tv, "code")), _int(_t(tv, "id"))) for tv in g.findall("tokens/value")]
                    groups[_int(gid)] = {"name": _t(g, "name"), "parent": _int(_t(g, "parent")), "tokens": toks}
                for h in root.iter("hap"):
                    haps.append((h, k))
            elif k.endswith("_hap.z"):
                diag["hap_z_skipped_pak_exists"] += 1
        for k, v in d.items():
            if not k.endswith(".pak"):
                continue
            raw = cpk.pak_group_block(v)
            if raw is not None:
                for g in yax_to_et(cpk.yax(raw), H).findall("group"):
                    gid = _int(_t(g, "id"))
                    if gid is None:
                        continue
                    toks = [(_int(_t(tv, "code")), _int(_t(tv, "id"))) for tv in g.findall("tokens/value")]
                    groups[gid] = {"name": _t(g, "name"), "parent": _int(_t(g, "parent")), "tokens": toks}
                diag["pak_group_blocks"] += 1
            try:
                trees = cpk.pak_yax(v)
            except Exception:
                diag["pak_unreadable"] += 1
                continue
            diag["pak_read"] += 1
            for t in trees:
                if t and any(tag == cpk.TAG_OBJ and val.startswith("em") for _, tag, val in t):
                    haps.append((yax_to_et(t, H), k))
        for h, member in haps:
            pl = hap_placements(h)
            if not pl:
                continue
            gid = _int(_t(h, "group"))
            chain, toks, g, guard = [], [], groups.get(gid), 0
            while g and guard < 30:
                chain.append(g["name"])
                toks += g["tokens"]
                g = groups.get(g["parent"])
                guard += 1
            subs = sorted({sp_hash[i] for c, i in toks if c == TOK_SUBPHASE and i in sp_hash})
            unres_sp = sum(1 for c, i in toks if c == TOK_SUBPHASE and i not in sp_hash)
            qst = sorted({q_hash[i] for c, i in toks if c == TOK_QUEST and i in q_hash})
            other_toks = sorted({f"{c:#x}:{i:#x}" for c, i in toks if c not in (TOK_SUBPHASE, TOK_QUEST)})
            kind, owner = owner_of_file(n, member)
            hname = _t(h, "name")
            for act, val in pl:
                e = describe(act, val)
                key = (n, _t(h, "id"), _t(act, "id"), e["objId"], tuple(e.get("position") or ()), e["setType"],
                       _t(val, "id"))
                if key in seen:
                    continue
                seen.add(key)
                rec, q = match_record(by_em, e["objId"], e["setType"], e["setFlag"])
                exe_ids = match_records_exe(by_em, e["objId"], e["setType"], e["setFlag"])
                talk_ids = match_records_talk(by_em, e["objId"], e["setType"], e["setFlag"])
                e.update({
                    "file": n, "member": member, "owner_kind": kind, "owner": owner, "hap": hname,
                    "group_chain": chain, "subphases": [f"{p}:{s}" for p, s in subs],
                    "chapters": sorted({chap_of[(p, s)] for p, s in subs if (p, s) in chap_of}),
                    "unresolved_subphase_tokens": unres_sp, "quest_states": qst,
                    "route_hint": route_hint(chain + [hname, e["action"]]),
                    "unit_data_saveid": rec["SaveID"] if rec else None,
                    "unit_data_name": rec["unit_data_name"] if rec else None, "unit_data_match": q,
                    "unit_data_saveids_exe": exe_ids,
                    "unit_data_saveids_talk": talk_ids,
                })
                if other_toks:
                    e["other_tokens"] = other_toks
                if kind == "quest":
                    e["quest_name"] = qnames.get(owner)
                e.update(assign_area(e, kind, owner, subs, sub_meta))
                placements.append(e)
        del d, haps, groups

    # zone par plus proche voisin (positions etiquetees par salle / mot-cle) pour les placements restants
    labelled = [(p["position"], p["area"]) for p in placements
                if p.get("position") and p["area_source"] in ("room_file", "name_keyword")]
    for p in placements:
        if p["area"] is None and p.get("position"):
            best = None
            for pos, a in labelled:
                dd = sum((x - y) ** 2 for x, y in zip(pos, p["position"])) ** 0.5
                if best is None or dd < best[0]:
                    best = (dd, a)
            if best and best[0] < 120:
                p["area"], p["area_source"], p["area_confidence"] = best[1], "nearest_labelled", "low"
                p["area_nearest_dist_m"] = round(best[0])

    return summarise(catalogue, acdb, hrand, placements, files, diag)


def subphase_chapters(phases):
    """(phase, sous-phase) -> 'CC-SS route' : derniere entree de ChapterData avant la sous-phase dans l'ordre du
    fichier _sub, de groupe de routes compatible (A: 0/2, B: 1/2, AB: 2, CD: 3). DEDUIT."""
    starts = defaultdict(list)
    for c in phases["chapters"]:
        starts[c["phase"]].append(c)
    out = {}
    comp = {"A": (0, 2), "B": (1, 2), "AB": (2, 0, 1), "CD": (3,), "C": (3,), "D": (3,)}
    gname = {0: "A", 1: "B", 2: "A+B", 3: "C/D"}
    for ph, rows in phases["sub_phase_files"].items():
        order = {r["Name"]: r["order"] for r in rows}
        for r in rows:
            m = re.search(r"_(AB|CD|A|B|C|D)_", r["Name"] + "_")
            if not m:
                continue
            ok = comp[m.group(1)]
            best = None
            for c in starts.get(ph, []):
                o = order.get(c["subphase"])
                if o is not None and o <= r["order"] and c["route_group"] in ok and (best is None or o >= best[0]):
                    best = (o, c)
            if best:
                c = best[1]
                out[(ph, r["Name"])] = f"{c['chapter']:02d}-{c['sub']:02d} {gname[c['route_group']]}"
    return out


def assign_area(e, kind, owner, subs, sub_meta):
    names = [e["action"], e["hap"]] + e["group_chain"]
    for nm in names:
        a = area_of(nm)
        if a:
            return {"area": a, "area_source": "name_keyword", "area_confidence": "medium"}
    if kind == "room" and owner in ROOMS:
        return {"area": ROOMS[owner], "area_source": "room_file", "area_confidence": "medium"}
    areas = set()
    for p, s in subs:
        m = sub_meta.get((p, s), {})
        a = area_of(m.get("Comment")) or area_of(s)
        if a:
            areas.add(a)
    if len(areas) == 1:
        return {"area": areas.pop(), "area_source": "owner_subphase", "area_confidence": "medium"}
    if areas:
        return {"area": " / ".join(sorted(areas)), "area_source": "owner_subphases_multi", "area_confidence": "low"}
    return {"area": None, "area_source": None, "area_confidence": None}


def summarise(catalogue, acdb, hrand, placements, files, diag=None):
    by_area = defaultdict(lambda: {"placements": 0, "em": Counter(), "unit_data": {}})
    by_phase = defaultdict(lambda: {"placements": 0, "em": Counter(), "unit_data": {}})
    by_quest = defaultdict(lambda: {"placements": 0, "em": Counter(), "unit_data": {}})
    rec_where = defaultdict(lambda: {"areas": Counter(), "subphases": Counter(), "quests": Counter(), "n": 0})
    sid_name = {}
    for e in catalogue:
        sid_name.setdefault(e["SaveID"], e["unit_data_name"])
    for p in placements:
        a = p["area"] or "(unknown)"
        targets = [by_area[a]]
        for s in p["subphases"] or ([f"{p['owner']}:(no subphase token)"] if p["owner_kind"] == "phase" else []):
            targets.append(by_phase[s])
        if p["owner_kind"] == "quest":
            targets.append(by_quest[p["owner"]])
        sids = (p.get("unit_data_saveids_exe") or []) + (p.get("unit_data_saveids_talk") or [])
        for t in targets:
            t["placements"] += 1
            t["em"][p["objId"]] += 1
            for sid in sids:
                t["unit_data"][sid] = sid_name.get(sid)
        for sid in sids:
            r = rec_where[sid]
            r["n"] += 1
            r["areas"][a] += 1
            for s in p["subphases"]:
                r["subphases"][s] += 1
            if p["owner_kind"] == "quest":
                r["quests"][p["owner"]] += 1

    def fin(dct):
        return {k: {"placements": v["placements"], "em_types": dict(v["em"].most_common()),
                    "unit_data": [{"SaveID": s, "name": n} for s, n in sorted(v["unit_data"].items())]}
                for k, v in sorted(dct.items())}

    saveids = {}
    for e in catalogue:
        saveids.setdefault(e["SaveID"], e)
    records = []
    for sid, e in sorted(saveids.items()):
        w = rec_where.get(sid)
        records.append({"SaveID": sid, "name": e["unit_data_name"], "EmID": e["EmID"], "category": e["category_name"],
                        "placements": w["n"] if w else 0,
                        "areas": dict(w["areas"].most_common()) if w else {},
                        "subphases": dict(w["subphases"].most_common(12)) if w else {},
                        "quests": dict(w["quests"]) if w else {}})
    em_no_list = Counter(p["objId"] for p in placements if p["unit_data_match"] == "no_emlist_entry")
    match_q = Counter(p["unit_data_match"] for p in placements)
    unplaced = [r for r in records if not r["placements"]]
    return {
        "_source": "tools/rf_enemies.py ; core/coregm.dat EmList.bxm, AcdbEnemySet.bxm, HackingRandom_EmId.bxm ; "
                   "*_hap.pak / *_grp.pak (hap.z si pas de .pak) de ph*, phf, st1, st2, st5, quest, core/corehap.dat, wd*",
        "notes": [
            "unit data record = EmList SaveID (bit de sauvegarde). Nom = PAUSE_ENEMY_%04x(Type.UIID) + "
            "' (' + PAUSE_ENEMY_%04x(UIID) + ')' ; format %04x lu dans l'exe (RVA 0xce6640), UIID lus en hexa "
            "(Type UIID '110' -> PAUSE_ENEMY_0110 'Multi-tier Type').",
            "lien placement -> donnees (unit_data_saveids_exe, utilise pour unit_data_records / by_*) = regle de "
            "l'exe 0x8257C0 en mode mort : toutes les lignes EmList avec EmID et setType egaux et (setFlag & masque) "
            "== masque (EmList setFlag 0 -> 0x10, 1 -> 0x10000010), mode 0 seulement, exclusions codees en dur. "
            "unit_data_saveids_talk : regle de 0x825CB0 (dialogue, lignes bTalk=1 ; Village Machines sans test de "
            "setType, apres la variable UI_namePV). Les lignes bDie=0/bTalk=0 (evenement seulement : boss, PNJ, "
            "quetes) ne se debloquent ni par mort ni par dialogue : voir records_resolved_logic_gaps "
            "(tools/logic_gaps_enemies.py --update-enemies).",
            "unit_data_saveid / unit_data_match = ancien appariement 1 ligne (garde pour comparaison).",
            "sources : *_hap.pak (fait foi, exe 0x3b8020) + *_grp.pak + groupes de chaque .pak (zlib v4 ou YAX brut "
            "v1) ; *_hap.z seulement pour un prefixe sans .pak. Cellules wd* incluses.",
            "kind=generator : objId tire au hasard (rate = poids) autour de points ; position = 1er point.",
            "area : name_keyword (noms japonais de l'action/hap/groupes) > room_file (salle st*) > owner_subphase "
            "(commentaire de la sous-phase) > nearest_labelled (plus proche placement etiquete, < 120 m, faible).",
            "chapters : deduits de l'ordre des fichiers _sub et des entrees de ChapterData.cha (meme route).",
            "Non lus : apparitions par scripts mruby (EmBase.callEnemy...), ennemis de hacking (HackingEnemy) et STG.",
        ],
        "room_files": {k: {"area": v, "evidence": ROOM_EVIDENCE.get(k)} for k, v in ROOMS.items()},
        "coverage": {
            "files_scanned": len(files), "emlist_entries": len(catalogue), "unit_data_records": len(saveids),
            "em_types_placed": len({p["objId"] for p in placements}), "placements": len(placements),
            "placements_with_record": sum(1 for p in placements if p["unit_data_saveid"] is not None),
            "placements_with_subphase": sum(1 for p in placements if p["subphases"]),
            "placements_with_area": sum(1 for p in placements if p["area"]),
            "records_with_placement": len(saveids) - len(unplaced), "records_without_placement": len(unplaced),
            "match_quality": dict(match_q),
            "placements_with_record_exe_rule": sum(1 for p in placements if p.get("unit_data_saveids_exe")),
            "placements_with_record_talk_rule": sum(1 for p in placements if p.get("unit_data_saveids_talk")),
            "load_diag": dict(diag or {}),
        },
        "catalogue": catalogue,
        "unit_data_records": records,
        "records_without_placement": [{"SaveID": r["SaveID"], "name": r["name"], "EmID": r["EmID"],
                                       "category": r["category"]} for r in unplaced],
        "placed_em_without_emlist": dict(em_no_list.most_common()),
        "by_area": fin(by_area), "by_subphase": fin(by_phase), "by_quest": fin(by_quest),
        "acdb_enemy_set": {"note": "AcdbEnemySet.bxm : ID (= em hexa sans 'em'), MesId, setType, setFlag ; role non "
                                   "confirme", "rows": acdb},
        "hacking_random_emid": {"note": "HackingRandom_EmId.bxm : id (= em hexa), dif, type ; ennemis tires pour les "
                                        "mini-jeux de hacking (deduit du nom)", "rows": hrand},
        "placements": placements,
    }


def write(out: Path) -> dict:
    """build + ecriture de enemies_by_area.json (utilise par main et par routes_full.py enemies).
    Les resolutions de tools/logic_gaps_enemies.py (records_resolved_logic_gaps) sont a re-appliquer ensuite :
    python tools/logic_gaps_enemies.py --update-enemies."""
    res = build(out)
    (out / "enemies_by_area.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
    print(json.dumps(res["coverage"], indent=1))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs" / "research"))
    a = ap.parse_args()
    write(Path(a.out))


if __name__ == "__main__":
    main()
