"""Positions monde (x, y, z) de tout ce qui interesse un randomizer : coffres, points de collecte, PNJ de quete,
marchands, terminaux d'acces, zones de peche, objets uniques. LECTURE SEULE sur le dossier du jeu.

Usage :
    python tools/world_positions.py [--out docs/research] [--no-wd]

Sources (un fichier .dat a la fois, petite RAM) :
- toutes les logiques `*_hap.z` (XML zlib) ET tous les `*.pak` (arbres YAX : `*_hap.pak`, `*_<groupe>_grp.pak`,
  `core/corehap.dat:qa*_hap.pak`) de ph*/, phf/, quest/, st1/2/5, core/, et des cellules monde wd*/g*.dat
  (20 cellules ont un hap ; `Layout.lay` = decors bg uniquement, parcouru pour verification).
  Les balises YAX sont des crc32 (zlib) du nom de balise : on les renomme avec le vocabulaire des hap.z.
- scripts mruby `<prefixe>_<id hexa>_scp.bin` relies a l'action hap qui porte `<script><id>` ; les variables
  de l'action (code 0xd8efbb45) pointent vers des entites placees (id de `layouts/value`).
- jetons de condition des groupes (`<tokens>` : code 0xf3b97443 = sous-phase, 0x35c92545 = etat de scene) :
  id = crc32 du nom (ex. 'Route/B', 'PL/9S', 'q440/RUN_1', nom de sous-phase).
- BoxData.drp : algorithme de l'exe v1.04 (RVA 0x7e37d0, voir data_formats.md).
- core/core.dat:FishParam.csv (tables de peche).
Les archives ba/, em/, bg/, bh/, it/, et/, um/ ont ete parcourues : elles ne contiennent ni hap ni script
(seulement modeles, motions, col, ObjectParam.bxm de rendu) ; rien a en tirer pour les positions.
Cache : %TEMP%/nier_research_cache (extract_research) + sous-dossier world_positions pour les membres wd.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import mruby  # noqa: E402
import resolve_quests  # noqa: E402  (method_names : irep -> nom de methode ruby)

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"
WD_CACHE = er.CACHE / "world_positions"
EXE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\NieRAutomata.exe")

LOGIC_RE = re.compile(r"(ph\w|quest|st\d|core)/[^/]+\.dat$")
WD_RE = re.compile(r"wd[1-5a]/g[0-9a-f]+\.dat$")
WD_KEEP = re.compile(r"(_hap\.z|\.pak|_scp\.bin|Layout\.lay)$")

TOK_SUBPHASE, TOK_STATE = "0xf3b97443", "0x35c92545"
VAR_ENTITY = "0xd8efbb45"
# Prefixe d'objId -> octet haut de la cle BoxData (cle = (prefixe << 16) | nombre hexa) : 'ba' 0xf et 'it' 0x7
# verifies (BoxData 0xf2014 / 0x70000 / 0x70020) ; 'bg' 0xc DEDUIT (enregistrements 0xc0800..0xc0805).
OBJ_PREFIX = {"pl": 0x1, "em": 0x2, "wp": 0x3, "et": 0x4, "ef": 0x5, "it": 0x7, "bg": 0xC, "ba": 0xF}
SEED_TAGS = ("root version group count id name parent tokens value code attribute priority comment hap size action "
             "layouts normal hard extream flags location position rotation scale objId param body script variables "
             "command label args area points height puid setType setRtn alias").split()

CHEST_IDS = {"ba2014", "ba2015", "ba2016"}
TERMINAL_IDS = {"ba1000", "ba1100"}
FISH_AREA_ID = "bga104"


# --------------------------------------------------------------------------------------------- acces fichiers

def members(name: str) -> dict[str, bytes]:
    """Membres utiles d'un .dat. Logique : via le cache d'extract_research ; cellules wd : seuls les membres
    hap/pak/scp/lay sont gardes dans WD_CACHE (le .dat complet n'est pas garde)."""
    if not WD_RE.match(name):
        return cpk.dat_files(er.game_file(name))
    d = WD_CACHE / name.replace("/", "__")
    idx = d / "_index.json"
    if idx.exists():
        return {m: (d / m).read_bytes() for m in json.loads(idx.read_text())}
    p, row = er._toc_index()[name]
    dat = cpk.dat_files(cpk.extract(p, row))
    keep = {k: v for k, v in dat.items() if WD_KEEP.search(k)}
    del dat
    d.mkdir(parents=True, exist_ok=True)
    for k, v in keep.items():
        (d / k).write_bytes(v)
    idx.write_text(json.dumps(sorted(keep)))
    return keep


# --------------------------------------------------------------------------------------------- hap -> arbres

class Vocab:
    def __init__(self):
        self.h = {}
        for t in SEED_TAGS:
            self.add(t)

    def add(self, tag):
        self.h.setdefault(zlib.crc32(tag.encode()), tag)

    def name(self, hsh):
        return self.h.get(hsh, "h_%08x" % hsh)


def hap_xml_text(z: bytes) -> str:
    t = zlib.decompress(z).decode("shift_jis", "replace")
    return re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", t)


def yax_to_elem(nodes, vocab: Vocab) -> ET.Element:
    root = ET.Element("hap")
    stack = [(-1, root)]
    for ind, tag, val in nodes:
        while stack[-1][0] >= ind:
            stack.pop()
        e = ET.SubElement(stack[-1][1], vocab.name(tag))
        e.text = val or None
        stack.append((ind, e))
    return root


def pak_groups(b: bytes, vocab: Vocab):
    """Bloc des groupes d'un .pak : en-tete `u32 ?, u32 taille decompressee, u32 offset` ; a l'offset :
    `u32 taille compressee` + zlib -> arbre YAX (count, group{id, name, parent, tokens, attribute, priority})."""
    try:
        _a, usz, off = struct.unpack_from("<III", b, 0)
        if not usz or off + 4 > len(b):
            return None
        csz = struct.unpack_from("<I", b, off)[0]
        raw = zlib.decompress(b[off + 4:off + 4 + csz])
    except (struct.error, zlib.error):
        return None
    root = ET.Element("root")
    g = ET.SubElement(root, "group")
    stack = [(-1, g)]
    for ind, tag, val in cpk.yax(raw):
        while stack[-1][0] >= ind:
            stack.pop()
        e = ET.SubElement(stack[-1][1], vocab.name(tag))
        e.text = val or None
        stack.append((ind, e))
    return root


def txt(e, path):
    x = e.find(path) if e is not None else None
    return x.text if x is not None else None


def floats(s):
    try:
        return [round(float(v), 4) for v in s.split()] if s else None
    except ValueError:
        return None


def parse_groups(root) -> dict:
    out = {}
    for g in root.findall("group/group"):
        gid = txt(g, "id")
        toks = [(txt(v, "code"), txt(v, "id")) for v in g.findall("tokens/value")]
        out[gid] = {"name": txt(g, "name"), "parent": txt(g, "parent"), "tokens": toks,
                    "attribute": txt(g, "attribute"), "comment": txt(g, "comment")}
    return out


def walk_values(e, bucket, out):
    """Toutes les `value` avec objId sous une action (layouts/normal|hard|extream ou autres)."""
    for c in e:
        b = c.tag if c.tag in ("normal", "hard", "extream") else bucket
        if c.tag == "value" and c.find("objId") is not None:
            out.append((b, c))
        walk_values(c, b, out)


def entity_of(v, bucket):
    params = {}
    for pv in v.findall("param/value"):
        params[txt(pv, "name")] = txt(pv, "body")
    return {"entity_id": txt(v, "id"), "objId": txt(v, "objId"), "position": floats(txt(v, "location/position")),
            "rotation": floats(txt(v, "location/rotation")), "scale": floats(txt(v, "scale")),
            "params": params, "alias": txt(v, "alias"), "comment": txt(v, "comment"),
            "setType": txt(v, "setType"), "setRtn": txt(v, "setRtn"), "difficulty_bucket": bucket}


# --------------------------------------------------------------------------------------------- scripts

def script_info(b: bytes) -> dict:
    try:
        root = mruby.parse(b)
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)}
    strings, syms = set(), set()
    mnames = resolve_quests.method_names(root)
    method_strings = defaultdict(set)
    for r in mruby.walk(root):
        strings.update(s for s in r.pool if isinstance(s, str))
        syms.update(s for s in r.syms if s)
        m = mnames.get(id(r))
        if m:
            method_strings[m].update(s for s in r.pool if isinstance(s, str))
    rewards = sorted({a[0] for *_x, a in mruby.calls(root, "getReWard") if a and isinstance(a[0], str)})
    add_items = []
    for *_x, a in mruby.calls(root, "addItem"):
        add_items.append(a)
    return {"strings": strings, "syms": syms, "rewards": rewards, "add_items": add_items,
            "method_strings": dict(method_strings)}


# --------------------------------------------------------------------------------------------- collecte

class Collector:
    def __init__(self):
        self.vocab = Vocab()
        self.entities = []      # entites retenues (categories utiles)
        self.by_id = defaultdict(list)  # id d'entite -> toutes les entites placees (tous fichiers)
        self.scripts = []       # actions avec script : fichier, action, variables, infos
        self.groups = {}        # (fichier, id) -> groupe
        self.words = set()      # dictionnaire de noms pour les jetons crc32
        self.tokens_seen = Counter()
        self.lay_objects = Counter()
        self.files_done = []

    def keep(self, ent):
        o = ent["objId"] or ""
        return (o in CHEST_IDS or o in TERMINAL_IDS or o == FISH_AREA_ID or o.startswith("it")
                or o.startswith("pl") or o.startswith("um") or "ItemTable" in ent["params"]
                or "codeName" in ent["params"])

    def process_file(self, name: str):
        d = members(name)
        base = name.split("/")[-1][:-4]
        haps = []  # (member, hap element)
        seen_haps = set()
        has_pak = any(k.endswith("_hap.pak") for k in d)
        # hap.z = XML d'edition PERIME (moins de haps, contenus differents) : sert au vocabulaire de balises et
        # seulement si le .dat n'a pas de hap.pak. Donnees d'execution = hap.pak (+ groupes) + *_grp.pak.
        for k, v in d.items():
            if k.endswith("_hap.z"):
                t = hap_xml_text(v)
                for tag in set(re.findall(r"<(\w+)>", t)):
                    self.vocab.add(tag)
                self.words.update(re.findall(r"[A-Za-z_][\w/.\-]{1,60}", t))
                if has_pak:
                    continue
                root = ET.fromstring(t)
                for gid, g in parse_groups(root).items():
                    self.groups[(name, gid)] = g
                for h in root.findall("hap"):
                    haps.append((k, h))
                    seen_haps.add(txt(h, "id"))
        for k, v in d.items():
            if not k.endswith(".pak"):
                continue
            groot = pak_groups(v, self.vocab)
            if groot is not None:
                for gid, g in parse_groups(groot).items():
                    self.groups[(name, gid)] = g
            try:
                trees = cpk.pak_yax(v)
            except Exception:  # noqa: BLE001
                continue
            for t in trees:
                for _i, _t, val in t:
                    if val and not val.startswith("0x"):
                        self.words.update(re.findall(r"[A-Za-z_][\w/.\-]{1,60}", val))
                h = yax_to_elem(t, self.vocab)
                if txt(h, "id") in seen_haps:
                    continue
                seen_haps.add(txt(h, "id"))
                haps.append((k, h))
        if "Layout.lay" in d:
            for m in re.finditer(rb"([a-z]{2}[0-9a-f]{4})_", d["Layout.lay"]):
                self.lay_objects[m.group(1).decode()[:2]] += 1
                o = m.group(1).decode()
                if not o.startswith("bg"):
                    self.lay_objects["NON_BG:" + o] += 1
        scp = {k: v for k, v in d.items() if k.endswith("_scp.bin")}
        ents_by_id = {}
        file_ents = []
        for member, h in haps:
            hname, hid, gid = txt(h, "name"), txt(h, "id"), txt(h, "group")
            for act in h.findall("action"):
                aname, aid, acode = txt(act, "name"), txt(act, "id"), txt(act, "code")
                vals = []
                walk_values(act, None, vals)
                for bucket, v in vals:
                    e = entity_of(v, bucket)
                    e.update(file=name, member=member, hap=hname, hap_id=hid, group=gid, action=aname,
                             action_id=aid)
                    ents_by_id[e["entity_id"]] = e
                    file_ents.append(e)
                sid = txt(act, "script/id")
                if sid:
                    variables = {}
                    for vv in act.findall("variables/value"):
                        if txt(vv, "value/code") == VAR_ENTITY:
                            variables[txt(vv, "name")] = txt(vv, "value/value")
                    cands = [f"{base}_{int(sid, 16):x}_scp.bin", f"global_{int(sid, 16):x}_scp.bin"]
                    sname = next((c for c in cands if c in scp), None)
                    info = script_info(scp[sname]) if sname else {}
                    self.words.update(info.get("strings", ()))
                    self.words.update(info.get("syms", ()))
                    self.scripts.append({"file": name, "member": member, "hap": hname, "group": gid,
                                         "action": aname, "action_location": floats(txt(act, "location/position")),
                                         "script_id": sid, "script_member": sname, "variables": variables,
                                         "info": info})
        for e in file_ents:
            self.by_id[e["entity_id"]].append(e)  # index global : les scripts de quete visent des entites d'autres fichiers
            if self.keep(e):
                self.entities.append(e)
        self.files_done.append({"file": name, "haps": len(haps), "entities": len(file_ents),
                                "scripts": len(scp)})
        del d


# --------------------------------------------------------------------------------------------- contexte

def build_token_names(col: Collector, phases: dict, quest_ids) -> dict:
    words = set(col.words)
    for p in phases["phase_info"]:
        words.update(p["subphases"])
        words.add(p["phase"])
    sufs = ["RUN", "DONE", "CLR", "FIN", "FAIL", "REQ", "END", "GRD", "START", "OFF", "ON"]
    for q in quest_ids:
        for s in sufs:
            words.add(f"{q}/{s}")
            words.add(f"{q}_{s}")
            for n in range(1, 13):
                words.add(f"{q}/{s}_{n}")
        words.add(q)
    for r in "ABCDE":
        words.add(f"Route/{r}")
    for c in ("2B", "9S", "A2"):
        words.add(f"PL/{c}")
    if EXE.exists():
        words.update(m.decode("latin1") for m in re.findall(rb"[A-Za-z_][\w/.\-]{2,60}", EXE.read_bytes()))
    names = {}
    for w in words:
        if not w:
            continue
        try:
            names.setdefault("0x%x" % zlib.crc32(w.encode("shift_jis")), w)
        except UnicodeEncodeError:
            names.setdefault("0x%x" % zlib.crc32(w.encode("utf-8")), w)
    return names


ROUTE_IN_SUBPHASE = re.compile(r"^\d+_\d+_([A-Z]{1,2})_")


def conditions_of(col, file, gid, tok_names, sub_room):
    chain, seen = [], set()
    while gid and (file, gid) in col.groups and gid not in seen:
        seen.add(gid)
        g = col.groups[(file, gid)]
        attr = int(g["attribute"] or "0", 16)
        toks = []
        for code, tid in g["tokens"]:
            nm = tok_names.get(tid)
            kind = {TOK_SUBPHASE: "subphase", TOK_STATE: "scene_state"}.get(code, code)
            toks.append({"kind": kind, "id": tid, "name": nm})
        chain.append({"group": g["name"], "group_id": gid, "attribute": g["attribute"],
                      "negated": bool(attr & 0x10), "tokens": toks})
        gid = g["parent"]
    routes, chars, subphases, states = set(), set(), [], []
    excluded_routes = set()
    for c in chain:
        for t in c["tokens"]:
            n = t["name"]
            if not n:
                continue
            if t["kind"] == "subphase":
                subphases.append(n)
                m = ROUTE_IN_SUBPHASE.match(n)
                if m and not c["negated"]:
                    routes.update(m.group(1))
            elif n.startswith("Route/"):
                (excluded_routes if c["negated"] else routes).add(n[6:])
            elif n.startswith("PL/"):
                chars.add(("not " if c["negated"] else "") + n[3:])
            else:
                states.append(("NOT " if c["negated"] else "") + n)
    unresolved = sum(1 for c in chain for t in c["tokens"] if not t["name"])
    return {"group_chain": [c["group"] for c in chain], "routes": sorted(routes),
            "excluded_routes": sorted(excluded_routes), "characters": sorted(chars),
            "subphases": subphases[:20], "scene_states": states[:20], "unresolved_tokens": unresolved,
            "raw": chain if unresolved or states else None}


def file_context(name, phases):
    stem = name.split("/")[-1][:-4]
    if name.startswith("ph"):
        return {"kind": "phase", "phase": stem}
    if name.startswith("quest/"):
        return {"kind": "quest", "quest_file": stem}
    if name.startswith("st"):
        return {"kind": "room", "room": stem}
    if name.startswith("wd"):
        return {"kind": "world_cell", "cell": stem}
    return {"kind": "core", "file": name}


# --------------------------------------------------------------------------------------------- BoxData

def load_boxdata(ctx_items):
    b = er.dat_member("core/coregm.dat", "BoxData.drp")
    _m, A, B = er.drp(b)
    recs = []
    for i, r in enumerate(A):
        key, box, _hi, room, st, n, _u6, u7 = struct.unpack("<IHHIHHII", r)
        recs.append({"index": i, "key": key, "box": box, "room": room, "draws_u32_20": u7,
                     "entries": [{"id": x, "name": ctx_items.get(x), "weight": w} for x, w in B[st:st + n]]})
    return recs


def box_lookup(recs, key, box, room):
    """Reproduit RVA 0x7e37d0 (v1.04). Renvoie l'enregistrement ou None.
    box < 0xa00 et != 0 : (salle, cle, box) puis (salle, cle, 0) ; box == 0 : (salle, cle, 0) ;
    box > 0xa00 : (0xa00, cle, box) ; dans tous les cas repli final (0xa00, cle, 0xa00)."""
    def find(rm, bx):
        for r in recs:
            if r["room"] == rm and r["key"] == key and r["box"] == bx:
                return r

    steps = []
    if 0 < box < 0xA00:
        steps = [(room, box), (room, 0)]
    elif box == 0:
        steps = [(room, 0)]
    elif box > 0xA00:
        steps = [(0xA00, box)]
    steps.append((0xA00, 0xA00))
    for rm, bx in steps:
        if rm is None:
            continue
        r = find(rm, bx)
        if r:
            return r, (rm, bx)
    return None, None


def obj_key(objId):
    p = OBJ_PREFIX.get(objId[:2])
    try:
        return (p << 16) | int(objId[2:], 16) if p is not None else None
    except ValueError:
        return None


def parse_box(v):
    if v is None:
        return 0
    v = v.strip().lower()
    return int(v[2:] if v.startswith("0x") else v, 16)  # ItemTable lu en hexa (q440 '100' -> 0x100 verifie)


# --------------------------------------------------------------------------------------------- principal

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESEARCH))
    ap.add_argument("--no-wd", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)

    phases = json.loads((RESEARCH / "phases.json").read_text(encoding="utf-8"))
    quests = json.loads((RESEARCH / "quests.json").read_text(encoding="utf-8"))["quests"]
    shops = json.loads((RESEARCH / "shops.json").read_text(encoding="utf-8"))["shops"]
    apres = json.loads((RESEARCH / "access_points_resolved.json").read_text(encoding="utf-8"))
    items_js = json.loads((RESEARCH / "items.json").read_text(encoding="utf-8"))
    qavail = json.loads((RESEARCH / "quest_availability.json").read_text(encoding="utf-8"))["quests"]
    texts = er.english_texts()
    item_info = {}
    for sect in ("items", "weapons", "chips"):
        for x in items_js.get(sect, []):
            uid = x.get("UniqueID")
            nm = x.get("english_name")
            if uid is not None and 8001 <= uid <= 8099 and not nm:
                nm = texts.get("CORE_FISH_%02d" % (uid - 8000), (None,))[0]
            item_info[uid] = dict(name=nm or x.get("internal_name"), internal=x.get("internal_name"),
                                  max=x.get("MaxNum"), cat=x.get("Category"), sect=sect)
    item_names = {k: v["name"] for k, v in item_info.items()}
    by_internal = {v["internal"]: k for k, v in item_info.items() if v["internal"]}

    col = Collector()
    names = sorted(er.all_names())
    # 1er passage : vocabulaire de balises des hap.z de toutes les logiques (avant de lire les YAX)
    logic = [n for n in names if LOGIC_RE.match(n)]
    wd = [] if args.no_wd else [n for n in names if WD_RE.match(n)]
    for n in logic:
        for k, v in members(n).items():
            if k.endswith("_hap.z"):
                for tag in set(re.findall(r"<(\w+)>", hap_xml_text(v))):
                    col.vocab.add(tag)
    for i, n in enumerate(logic + wd):
        print(f"[{i + 1}/{len(logic) + len(wd)}] {n}", file=sys.stderr, flush=True)
        col.process_file(n)

    quest_ids = sorted(set(quests) | {m for w in col.words for m in re.findall(r"\bq[0-9a-f]{3}\b", w)})
    tok_names = build_token_names(col, phases, quest_ids)
    sub_room = {}
    for ph, subs in phases["sub_phase_files"].items():
        for s in subs:
            sub_room[s["Name"]] = s.get("RoomNo")
    phase_routes = defaultdict(set)
    RG = {0: "A", 1: "B", 2: "AB", 3: "CD"}
    for ch in phases["chapters"]:
        phase_routes[ch["phase"]].add(RG.get(ch["route_group"], str(ch["route_group"])))

    def ctx(e):
        c = file_context(e["file"], phases)
        cond = conditions_of(col, e["file"], e["group"], tok_names, sub_room)
        if c["kind"] == "phase":
            c["phase_route_groups_from_chapters"] = sorted(phase_routes.get(c["phase"], []))
        if c["kind"] == "quest":
            q = re.match(r"q[0-9a-f]{3}", c["quest_file"])
            qa = qavail.get(q.group(0)) if q else None
            if qa:
                c["quest_windows"] = qa.get("windows")
                c["quest_character"] = qa.get("character")
        return c, cond

    def pub(e, extra=None):
        c, cond = ctx(e)
        r = {"objId": e["objId"], "position": e["position"], "rotation": e["rotation"], "file": e["file"],
             "member": e["member"], "hap": e["hap"], "action": e["action"], "entity_id": e["entity_id"],
             "difficulty_bucket": e["difficulty_bucket"], "context": c, "conditions": cond}
        for k in ("alias", "comment"):
            if e.get(k):
                r[k] = e[k]
        if e["params"]:
            r["params"] = e["params"]
        if extra:
            r.update(extra)
        return r

    # --- salles connues (fichiers st*/rXXX) -> inference par plus proche voisin
    room_pts = defaultdict(list)
    for e in col.entities:
        if e["file"].startswith("st") and e["position"]:
            room_pts[int(e["file"].split("/")[-1][1:4], 16)].append(e["position"])

    def room_distances(e):
        """Distance minimale de l'entite a chaque salle connue (entites des fichiers st*/rXXX)."""
        x, y, z = e["position"][:3]
        out = {}
        for rm, pts in room_pts.items():
            out[rm] = math.sqrt(min((p[0] - x) ** 2 + (p[1] - y) ** 2 + (p[2] - z) ** 2 for p in pts))
        return out

    recs = load_boxdata(item_names)

    def resolve_box(e):
        key = obj_key(e["objId"])
        try:
            box = parse_box(e["params"].get("ItemTable"))
        except ValueError:
            return {"status": "unparsed_ItemTable", "ItemTable": e["params"].get("ItemTable")}
        res = {"boxdata_key": hex(key) if key is not None else None, "item_table": hex(box)}
        if key is None:
            res["status"] = "no_key"
            return res
        if e["file"].startswith("st"):
            cands = {int(e["file"].split("/")[-1][1:4], 16): 0.0}
            res["room_source"] = "file"
        elif e["position"]:
            dist = room_distances(e)
            best = min(dist.values())
            cands = {rm: d for rm, d in dist.items() if d <= max(60.0, 1.5 * best)}
            res["room_source"] = "proximity (entites des salles st*/rXXX a <= max(60, 1.5 x min))"
        else:
            cands = {None: None}
            res["room_source"] = "none"
        per_room = {}
        for rm, d in sorted(cands.items(), key=lambda kv: (kv[1] is None, kv[1])):
            rec, step = box_lookup(recs, key, box, rm)
            per_room[hex(rm) if rm is not None else "?"] = {
                "distance": round(d, 1) if d is not None else None, "boxdata_index": rec["index"] if rec else None,
                "matched": [hex(step[0]), hex(step[1])] if rec else None}
        idx = {v["boxdata_index"] for v in per_room.values()}
        res["candidate_rooms"] = per_room
        if len(idx) == 1:
            i = next(iter(idx))
            if i is None:
                res["status"] = "no_record"
            else:
                rec = recs[i]
                res.update(status="resolved", boxdata_index=i, contents=rec["entries"],
                           draws_u32_20=rec["draws_u32_20"])
            # salle lue dans le nom du fichier, ou table independante de la salle (box >= 0xa00) : sur ;
            # sinon salle deduite par proximite (toutes les salles candidates donnent le meme enregistrement)
            res["confidence"] = "high" if res["room_source"] == "file" or box >= 0xA00 else "medium"
        else:
            res["status"] = "ambiguous_room"
            res["contents_by_boxdata_index"] = {str(i): recs[i]["entries"] for i in idx if i is not None}
            res["confidence"] = "low"
        return res

    # ------------------------------------------------------------------ 1. coffres et points de collecte
    chests, pickups = [], []
    for e in col.entities:
        o = e["objId"] or ""
        if o in CHEST_IDS or ("ItemTable" in e["params"] and not o.startswith("it")):
            chests.append(pub(e, {"box": resolve_box(e)}))
        elif o.startswith("it"):
            pickups.append(pub(e, {"box": resolve_box(e)}))

    # ------------------------------------------------------------------ scripts : index chaine -> actions
    shop_names = {s["internal_name"]: s for s in shops}
    def script_entities(s):
        """Variables d'entite d'une action de script -> entites placees (meme fichier d'abord, sinon tout
        fichier : un script de quete vise des PNJ places dans st1/rXXX ou les phases)."""
        out = []
        for var, eid in s["variables"].items():
            cands = col.by_id.get(eid, [])
            same = [e for e in cands if e["file"] == s["file"]]
            for e in (same or cands):
                out.append((var, e))
        return out

    # ------------------------------------------------------------------ PNJ parlant d'un script
    def method_var(sc, method):
        """Variable d'entite dont le nom prefixe la methode (`<var>_ON_TALK...`, `<var>_...`) : le PNJ parle."""
        best = None
        for var in sc["variables"]:
            if method == var or method.startswith(var + "_"):
                if best is None or len(var) > len(best):
                    best = var
        return best

    def talkers(sc, pred):
        """[(variable, methode)] des methodes du script dont une chaine satisfait pred."""
        out = []
        for m, strs in sc["info"].get("method_strings", {}).items():
            if any(pred(x) for x in strs):
                v = method_var(sc, m)
                out.append((v, m))
        return out

    def pub_var(sc, var, extra):
        res = []
        for v, e in script_entities(sc):
            if v == var:
                res.append(pub(e, dict(extra, script_variable=v, script=sc["script_member"])))
        return res

    # ------------------------------------------------------------------ 3. marchands
    shop_out = []
    for sn, s in shop_names.items():
        hits = []
        for sc in col.scripts:
            if sn not in sc["info"].get("strings", ()):
                continue
            tk = talkers(sc, lambda x, sn=sn: x == sn)
            npcs = []
            for var, m in tk:
                if var:
                    npcs += pub_var(sc, var, {"method": m})
            cand = [] if npcs else [pub(e, {"script_variable": v, "script": sc["script_member"]})
                                    for v, e in script_entities(sc)
                                    if (e["objId"] or "").startswith(("pl", "em", "um"))]
            hits.append({"file": sc["file"], "script": sc["script_member"], "hap": sc["hap"],
                         "action": sc["action"], "action_location": sc["action_location"],
                         "methods": [m for _v, m in tk], "shop_npcs": npcs,
                         "candidate_entities_no_talk_method": cand,
                         "conditions": conditions_of(col, sc["file"], sc["group"], tok_names, sub_room)})
        shop_out.append({"shop": sn, "shop_id": s.get("id"), "english_name": s.get("english_name"),
                         "references": hits,
                         "confidence": ("high" if any(h["shop_npcs"] for h in hits) else
                                        "low" if hits else "unresolved")})

    # ------------------------------------------------------------------ 2. PNJ de quete
    qnames = {q: v.get("english_name") for q, v in quests.items()}
    quest_out = {}
    qre = re.compile(r"\bq[0-9a-f]{3}\b")
    PLAYERS = ("pl0000", "pl0100", "pl0200", "pl0300")
    for q in sorted(quests):
        quest_out[q] = {"english_name": qnames.get(q), "givers": [], "turn_in": [], "quest_script_entities": [],
                        "placed_in_quest_files": [], "named_haps": [], "_seen": set()}

    def add(q, k, e, extra=None):
        key = (k, e["file"], e["entity_id"], (extra or {}).get("method"))
        if key in quest_out[q]["_seen"]:
            return
        quest_out[q]["_seen"].add(key)
        quest_out[q][k].append(pub(e, extra))

    for sc in col.scripts:
        own = None
        if sc["file"].startswith("quest/"):
            own = re.match(r"q[0-9a-f]{3}", sc["file"].split("/")[-1]).group(0)
        # donneur : la methode de dialogue d'un PNJ qui passe la quete a RUN_1 ; rendu : a DONE
        for q in quest_out:
            if q not in sc["info"].get("strings", ()) and not any(x.startswith(q + "/") for x in
                                                                    sc["info"].get("strings", ())):
                continue
            for kind, st in (("givers", q + "/RUN_1"), ("turn_in", q + "/DONE")):
                for var, m in talkers(sc, lambda x, st=st: x == st):
                    if not var:
                        continue
                    for v, e in script_entities(sc):
                        if v == var and (e["objId"] or "") not in PLAYERS:
                            add(q, kind, e, {"script": sc["script_member"], "script_variable": v, "method": m})
        if own in quest_out:
            for var, e in script_entities(sc):
                if (e["objId"] or "") not in PLAYERS:
                    add(own, "quest_script_entities", e, {"script": sc["script_member"], "script_variable": var})
    for e in col.entities:
        o = e["objId"] or ""
        interesting = (o.startswith(("pl", "um")) and o not in PLAYERS) or o in CHEST_IDS or o.startswith("it")
        if not interesting:
            continue
        if e["file"].startswith("quest/"):
            q = re.match(r"q[0-9a-f]{3}", e["file"].split("/")[-1]).group(0)
            if q in quest_out:
                add(q, "placed_in_quest_files", e)
        else:
            for q in set(qre.findall(" ".join(x for x in (e["hap"], e["action"]) if x))):
                if q in quest_out:
                    add(q, "named_haps", e)
    for q, v in quest_out.items():
        del v["_seen"]
        v["confidence"] = ("high" if v["givers"] else
                           "medium" if v["quest_script_entities"] or v["turn_in"] else
                           "low" if v["named_haps"] or v["placed_in_quest_files"] else "unresolved")
        for k in ("givers", "turn_in", "quest_script_entities", "placed_in_quest_files", "named_haps"):
            v[k] = v[k][:60]

    # ------------------------------------------------------------------ 4. terminaux
    by_code = {a["code"]: a for a in apres["access_points"]}
    term = defaultdict(list)
    for e in col.entities:
        if "codeName" in e["params"]:
            term[e["params"]["codeName"]].append(pub(e))
    ap_out = []
    for code in list(by_code) + sorted(set(term) - set(by_code)):
        a = by_code.get(code, {})
        ap_out.append({"code": code, "english_name": a.get("english_name"), "text_key": a.get("text_key"),
                       "is_access_point": a.get("is_access_point"), "terminals": term.get(code, []),
                       "confidence": "high" if term.get(code) else "unresolved"})

    # ------------------------------------------------------------------ 5. peche
    fish_csv = er.dat_member("core/core.dat", "FishParam.csv").decode("shift_jis", "replace")
    tables = defaultdict(list)
    for line in fish_csv.splitlines():
        p = line.split(",")
        if len(p) >= 3 and p[1]:
            tables[p[0] or "(vide)"].append({"et_object": p[1], "weight": int(p[2]) if p[2].isdigit() else p[2]})
    areas = defaultdict(list)
    for e in col.entities:
        if e["objId"] == FISH_AREA_ID:
            areas[(e["file"], e["hap"])].append(e)
    fish_areas = []
    for (f, h), es in sorted(areas.items()):
        pts = [x["position"] for x in es if x["position"]]
        cen = [round(sum(p[i] for p in pts) / len(pts), 2) for i in range(3)] if pts else None
        c, cond = ctx(es[0])
        fish_areas.append({"file": f, "hap": h, "volumes": len(es), "centroid": cen,
                           "bbox": [[round(min(p[i] for p in pts), 1) for i in range(3)],
                                    [round(max(p[i] for p in pts), 1) for i in range(3)]] if pts else None,
                           "params_seen": sorted({k for x in es for k in x["params"]}),
                           "context": c, "conditions": cond,
                           "volumes_detail": [{"position": x["position"], "rotation": x["rotation"],
                                               "scale": x["scale"]} for x in es]})

    # ------------------------------------------------------------------ 6. objets uniques places
    def unique_item(uid):
        i = item_info.get(uid)
        if not i:
            return False
        return (i["max"] == 1 or 1000 <= uid < 3000) and uid != 10
    uniques = []
    for c in chests + pickups:
        b = c["box"]
        for en in b.get("contents") or []:
            if unique_item(en["id"]):
                uniques.append({"item_id": en["id"], "item": en["name"], "weight": en["weight"],
                                "via": c["objId"], "position": c["position"], "file": c["file"],
                                "hap": c["hap"], "box_confidence": b.get("confidence"),
                                "context": c["context"], "conditions": c["conditions"]})
    script_items = []
    for sc in col.scripts:
        for a in sc["info"].get("add_items", []):
            if not a or not isinstance(a[0], str) or a[0] not in by_internal:
                continue
            uid = by_internal[a[0]]
            if not unique_item(uid):
                continue
            # PNJ/objet qui donne l'objet : variable qui prefixe la methode contenant le nom interne de l'objet
            givers = {v: m for v, m in talkers(sc, lambda x, n=a[0]: x == n) if v}
            ents = [{"objId": e["objId"], "position": e["position"], "variable": v, "method": givers[v]}
                    for v, e in script_entities(sc) if v in givers]
            if not ents:
                ents = [{"objId": e["objId"], "position": e["position"], "variable": v, "method": None}
                        for v, e in script_entities(sc)][:8]
            script_items.append({"item_id": uid, "item": item_names.get(uid), "args": a, "file": sc["file"],
                                 "script": sc["script_member"], "hap": sc["hap"], "action": sc["action"],
                                 "action_location": sc["action_location"], "linked_entities": ents,
                                 "conditions": conditions_of(col, sc["file"], sc["group"], tok_names, sub_room),
                                 "confidence": "high" if any(x["method"] for x in ents) else
                                 "medium" if ents or sc["action_location"] else "low"})

    # ------------------------------------------------------------------ sortie
    def cnt(lst, f):
        return {str(k): v for k, v in Counter(f(x) for x in lst).items()}

    unresolved_tok = Counter(t["id"] for g in col.groups.values() for code, tid in g["tokens"]
                             for t in [{"id": tid}] if tid not in tok_names)
    res = {
        "_source": "tools/world_positions.py (lecture seule ; voir data_formats.md 'Positions monde')",
        "coordinate_note": "positions = coordonnees monde du jeu (x, y vertical, z) lues dans les hap ; rotation = "
                           "radians (y = cap). difficulty_bucket = normal/hard/extream (calque de placement) ; "
                           "la plupart des placements sont dans 'normal', les calques hard/extream sont vides.",
        "boxdata_algorithm": "RVA 0x7e37d0 : cle = objId numerique ('ba'=0xf, 'it'=0x7), ItemTable lu en hexa "
                             "(absent = 0). 0<box<0xa00 : (salle, cle, box) puis (salle, cle, 0) ; box=0 : "
                             "(salle, cle, 0) ; box>0xa00 : (0xa00, cle, box) ; repli (0xa00, cle, 0xa00). "
                             "salle = variable globale RVA 0x130c890 (0x550 force si le drapeau 0x400000 de "
                             "RVA 0x1029b00 est mis ; calcule depuis la position en phase 0xe01/0xe03). Les "
                             "enregistrements de salle 0xb1 ne sont jamais choisis hors salle 0xb1 (test).",
        "summary": {
            "files_processed": len(col.files_done),
            "chests": len(chests), "chests_by_objId": cnt(chests, lambda x: x["objId"]),
            "chests_box_status": cnt(chests, lambda x: (x["box"].get("status"), x["box"].get("confidence"))),
            "pickups": len(pickups), "pickups_by_objId": cnt(pickups, lambda x: x["objId"]),
            "pickups_box_status": cnt(pickups, lambda x: (x["box"].get("status"), x["box"].get("confidence"))),
            "shops": cnt(shop_out, lambda x: x["confidence"]),
            "quests": cnt(list(quest_out.values()), lambda x: x["confidence"]),
            "access_points": cnt(ap_out, lambda x: x["confidence"]),
            "fishing_areas": len(fish_areas), "fish_tables": len(tables),
            "unique_items_in_boxes": len(uniques), "unique_items_from_scripts": len(script_items),
            "group_tokens_unresolved": len(unresolved_tok), "group_tokens_total": len({tid for g in col.groups.values()
                                                                                    for _c, tid in g["tokens"]}),
            "layout_lay_object_prefixes": dict(col.lay_objects),
        },
        "chests": chests,
        "item_pickups": pickups,
        "quest_npcs": quest_out,
        "shops": shop_out,
        "access_points": ap_out,
        "fishing": {"note": "Zones = objets bga104 (BehaviorFishingArea, volumes d'eau). Tables = "
                            "core/core.dat:FishParam.csv (indice de table, objet poisson etfXXX, poids). Le choix "
                            "de l'indice (champs +0x3ec8/+0x3ecc de l'objet de peche, RVA 0x59bf30) et la "
                            "correspondance etfXXX -> objet fish_NN (8001..8041, CORE_FISH_NN) NE SONT PAS "
                            "resolus ; 0x4f040/0x4f041 = etf040/041 selon le personnage (cle 0x10200).",
                    "tables": tables, "areas": fish_areas,
                    "fish_items": {uid: v["name"] for uid, v in item_info.items() if 8001 <= uid <= 8099}},
        "unique_items": {"in_boxes": uniques, "from_scripts_addItem": script_items},
        "files": col.files_done,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "world_positions.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list),
                                             encoding="utf-8")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
