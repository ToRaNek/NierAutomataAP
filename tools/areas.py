"""Noms de zone officiels (HUD / carte) pour toute position monde. LECTURE SEULE sur le dossier du jeu.

Usage :
    python tools/areas.py [--refresh] [--verify-exe] [--no-label] [--out docs/research] [--wp world_positions.json]

Mecanisme du jeu (v1.04 Steam, RVA = adresses relatives a 0x140000000) :
- La zone courante est UN entier global (RVA 0x1494a04, lu par 0x7c4870, ecrit par 0x7c71d0).
- Il est ecrit par `hap::ChangeAreaAction` (vtable 0xc43cf0, code d'action hap 0x1571c131 = crc32('ChangeAreaAction')) :
  slot 9 = 0x39e690, sur l'evenement 0xcc7564cb = crc32('HIT') (le joueur ENTRE dans un des volumes `area` de l'action),
  id = 0x385f20(StageType = [action+0xb0], AreaType = [action+0xb4]) puis 0x7c71d0(id). La valeur reste jusqu'au
  prochain volume traverse (semantique "dernier volume entre"). Quelques sous-phases forcent l'id (0x858a77,
  0x857ca0, 0x8592d0 : STG/combats aeriens -> 200/210/260/95, -1) ; sans lien avec une position.
- Nom affiche : 0x921da0 (UI) appelle 0x86d150(id) -> cle de zone et 0x86f9d0(id) -> cle de sous-zone
  (tables de sauts 0x86d380/0x86d3b8 et 0x86fb48/0x86fbb4). Cas speciaux : id 20 (vaisseau extraterrestre) ->
  CORE_MAP_AREA_160 si la variable UI_nameAS est vraie, sinon CORE_SUB_MAP_AREA_018 '???' ; id 165 -> Pascal's
  Village si UI_namePV, sinon CORE_SUB_MAP_AREA_111 '???' ; phase 0x400 (DLC) -> CORE_MAP_AREA_998.
- Textes : ui/ui_core_us.dat:messcore.mcd (+ ui_dlc1/2/3_us : 'Arena').

Fonction statique : `area_of(pos, file=None, room=None)` -> zone/sous-zone. Volumes de la salle de l'entite (ou du
monde ouvert), volume contenant le plus petit, sinon volume le plus proche (APPROXIMATION de la semantique
'dernier volume entre'). Voir data_formats.md, section 'Zones (areas)'.

Sorties : `docs/research/areas.json` ; ajoute un champ `area` a chaque entree positionnee de world_positions.json
(champs existants conserves). Cache des volumes : %TEMP%/nier_research_cache/areas_volumes.json.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import world_positions as wp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"
VOL_CACHE = er.CACHE / "areas_volumes.json"

CODE_CHANGE_AREA = "0x1571c131"     # crc32('ChangeAreaAction')
CODE_MINIMAP_AREA = "0xa4170d"      # crc32('MinimapAreaAction') (r140, r520 : etage de la mini-carte, pas un nom)
SHAPE = {"0x18cffd98": "box", "0x4238cc7f": "cylinder", "0x8face66d": "sphere"}  # app::area::BoxArea/...

# 0x385f20 (StageType, AreaType) -> id de zone (emule ; verify_exe() le recalcule)
AREA_ID = {
    (0, 0): 0, (0, 2): 10, (0, 3): 15, (0, 4): 20, (0, 5): 25, (0, 6): 170, (0, 7): 175, (0, 8): 180,
    (1, 0): 30, (1, 1): 35, (1, 2): 40, (1, 3): 45, (1, 4): 50, (1, 5): 190,
    (2, 0): 55, (2, 1): 60, (2, 2): 65, (2, 3): 70, (2, 4): 135,
    (3, 0): 75, (3, 1): 85, (3, 2): 90, (3, 3): 125, (3, 4): 185,
    (4, 0): 95, (4, 2): 130, (4, 3): 195,
    (5, 0): 105, (5, 2): 115, (5, 3): 120,
    (6, 0): 140, (6, 1): 145, (6, 2): 150,
    (7, 0): 155, (8, 0): 160, (9, 0): 165,
}
STAGE_TYPE = {0: "City Ruins (StageType 0)", 1: "Desert", 2: "Amusement Park", 3: "Forest", 4: "Flooded City",
              5: "Abandoned Factory", 6: "The Tower", 7: "The Bunker", 8: "Resistance Camp", 9: "Pascal's Village"}
# 0x86d150 : id -> cle de zone (cas a variable : voir SPECIAL)
MAIN_KEY = {}
for _k, _ids in {
    "CORE_MAP_AREA_010": (0, 10, 15, 170, 175, 180), "CORE_SUB_MAP_AREA_014": (25,),
    "CORE_MAP_AREA_030": (30, 35, 40, 45, 50, 190), "CORE_MAP_AREA_040": (55, 60, 65, 70, 135),
    "CORE_MAP_AREA_120": (75, 125), "CORE_MAP_AREA_050": (85, 90, 185), "CORE_MAP_AREA_060": (95, 130, 195),
    "CORE_MAP_AREA_070": (105, 115, 120, 200, 210), "CORE_MAP_AREA_090": (140, 145, 150),
    "CORE_MAP_AREA_020": (155,), "CORE_MAP_AREA_100": (160,),
}.items():
    for _i in _ids:
        MAIN_KEY[_i] = _k
SPECIAL = {20: ("UI_nameAS", "CORE_MAP_AREA_160", "CORE_SUB_MAP_AREA_018"),
           165: ("UI_namePV", "CORE_MAP_AREA_110", "CORE_SUB_MAP_AREA_111")}
# 0x86f9d0 : id -> cle de sous-zone (280 -> 094 Elevator : aucun (StageType, AreaType) ne donne 280)
SUB_KEY = {10: "011", 15: "012", 170: "015", 175: "016", 180: "017", 30: "031", 40: "033", 45: "034", 50: "035",
           55: "041", 60: "042", 65: "043", 70: "044", 85: "051", 90: "052", 185: "121", 195: "061", 115: "071",
           120: "072", 125: "081", 130: "082", 135: "083", 140: "091", 145: "092", 150: "093", 280: "094"}
SUB_KEY = {k: "CORE_SUB_MAP_AREA_" + v for k, v in SUB_KEY.items()}

# Fichiers dont les volumes forment un espace a part (pas le monde ouvert continu)
SEPARATE = {"st5/r500.dat": "r500", "quest/qb40.dat": "bunker"}
# Cellules wd -> salle (jetons de salle 0x5cda8ece des groupes qb30/qb31/qb32 : r5a0/r5a1/r5a2 ; routes_full)
WD_ROOM = {"wd5/g5a000.dat": "r5a0", "wd5/g5a001.dat": "r5a0", "wd5/g5a100.dat": "r5a1", "wd5/g5a200.dat": "r5a2",
           "wd5/g50001.dat": "r500", "wd5/g50010.dat": "r500", "wd5/g50100.dat": "r501", "wd5/g52001.dat": "r520"}
# Salles sans volume : id par defaut DEDUIT (confiance basse), voir areas.json 'room_defaults'
ROOM_DEFAULT = {
    "r5a8": (185, "DEDUIT : salle DLC (data100.cpk) en foret pres de l'ascenseur 8 'Forest_C_ElevatorUnlock' ; id 185 "
                  "= seul id foret DLC de 0x385f20 (sous-zone CORE_SUB_MAP_AREA_121 'Arena', messdlc2) ; aucun volume"),
    "r5a9": (195, "DEDUIT : salle DLC (data100.cpk) a la Cite engloutie pres de l'ascenseur 9 'Submerge_C_ElevatorUnlock' ;"
                  " id 195 (CORE_SUB_MAP_AREA_061 'Arena', messdlc3) ; aucun volume"),
}
# Conflit connu : deux volumes au meme endroit (unite de recuperation du parc) avec des zones differentes
DEPRIORITIZED = {("quest/qb30.dat", "エリア表記切り替え(2)"):
                 "cylindre StageType 4/AreaType 2 (Soul Box, Cite engloutie) dans le fichier de l'unite du PARC (copie "
                 "probable de qb32) ; la boite 'エリア切り替えエリア(2)' (God Box) au meme endroit est preferee"}


# Indices de lieu dans les noms japonais (hap / action / chaine de groupes) de l'ENTITE : memes mots que les noms des
# actions ChangeArea ('エリア切り替えエリア_城内' -> 85...). Utilises seulement HORS volume pour restreindre les volumes
# candidats (la geometrie choisit dans l'ensemble). Ordre = priorite (le plus specifique d'abord). DEDUIT.
HINTS = [
    ("劇場地下", {70}), ("ショッピングモール", {10}), ("エイリアンシップ", {20}), ("コピー都市", {25}),
    ("砂漠_入口", {30}), ("大砂漠", {35}), ("砂漠_団地", {45}), ("団地", {45}), ("竪穴", {50}), ("砂漠地下", {40, 50}),
    ("メインストリート", {55}), ("アトラクション", {60}), ("劇場", {65}),
    ("城内", {85, 90}), ("玉座", {90}), ("森部分", {75}), ("森エリア", {75}),
    ("教祖", {115}), ("地下工場", {120}), ("塔下層", {140}), ("塔上層", {145}),
]


def hint_of(names) -> tuple[str, set] | None:
    for kw, ids in HINTS:
        if any(kw in (n or "") for n in names):
            return kw, ids
    return None


def entity_names(e: dict) -> list[str]:
    out = [e.get("hap"), e.get("action")]
    c = e.get("conditions")
    if isinstance(c, dict):
        out += c.get("group_chain") or []
    return [x for x in out if isinstance(x, str)]


# ------------------------------------------------------------------------------------------- textes

def texts() -> dict[str, str]:
    t = {k: v for k, (v, _src) in er.english_texts().items()}
    for f in ("ui/ui_dlc1_us.dat", "ui/ui_dlc2_us.dat", "ui/ui_dlc3_us.dat"):
        d = er.game_file(f)
        if d is None:
            continue
        for m, b in cpk.dat_files(d).items():
            if m.endswith(".mcd"):
                for k, v in er.mcd(b).items():
                    t.setdefault(k, v)
    return t


def area_names(tx: dict) -> dict[int, dict]:
    """id -> {area, sub_area, keys...} selon 0x86d150 / 0x86f9d0."""
    out = {}
    for (st, at), i in sorted(AREA_ID.items(), key=lambda x: x[1]):
        e = {"id": i, "stage_type": st, "area_type": at}
        if i in SPECIAL:
            var, k_on, k_off = SPECIAL[i]
            e["area_key"] = k_on
            e["area_key_if_not_" + var] = k_off
            e["area"] = tx.get(k_on)
            e["area_if_not_" + var] = tx.get(k_off)
            if e["area"] is None:
                e["area_note"] = f"{k_on} : aucun texte dans les fichiers anglais ; affiche '{tx.get(k_off)}' ({k_off})"
        else:
            e["area_key"] = MAIN_KEY.get(i)
            e["area"] = tx.get(e["area_key"]) if e["area_key"] else None
        sk = SUB_KEY.get(i)
        e["sub_area_key"] = sk
        e["sub_area"] = tx.get(sk) if sk else None
        if i == 20:
            e["unused_text_hint"] = {"CORE_SUB_MAP_AREA_013": tx.get("CORE_SUB_MAP_AREA_013"),
                                     "note": "texte present mais non reference par l'exe (indice, pas le nom affiche)"}
        out[i] = e
    return out


def display(names: dict[int, dict], i: int) -> tuple[str | None, str | None, str]:
    """(zone, sous-zone, libelle) affichables pour un id."""
    e = names.get(i)
    if e is None:
        return None, None, "?"
    a = e.get("area") or e.get("area_if_not_UI_nameAS")
    s = e.get("sub_area")
    return a, s, f"{a}: {s}" if s else (a or "?")


# ------------------------------------------------------------------------------------------- volumes

def _vocab():
    v = wp.Vocab()
    for t in ("StageType AreaType radius MinimapId SubMinimapId bIgnoreHeight".split()):
        v.add(t)
    return v


def collect_volumes(refresh=False) -> list[dict]:
    """Toutes les actions ChangeArea / MinimapArea des *.pak (un .dat a la fois)."""
    if VOL_CACHE.exists() and not refresh:
        return json.loads(VOL_CACHE.read_text(encoding="utf-8"))
    v = _vocab()
    names = sorted(er.all_names())
    files = [n for n in names if wp.LOGIC_RE.match(n)] + [n for n in names if wp.WD_RE.match(n)]
    out = []
    for fi, f in enumerate(files):
        try:
            mem = wp.members(f)
        except Exception as ex:  # noqa: BLE001
            print("ERR", f, ex, file=sys.stderr)
            continue
        groups, found = {}, []
        for n, b in mem.items():
            if not n.endswith(".pak"):
                continue
            g = wp.pak_groups(b, v)
            if g is not None:
                groups.update(wp.parse_groups(g))
            try:
                trees = cpk.pak_yax(b)
            except Exception:  # noqa: BLE001
                continue
            for t in trees:
                root = wp.yax_to_elem(t, v)
                for a in root.iter("action"):
                    c = wp.txt(a, "code")
                    if c not in (CODE_CHANGE_AREA, CODE_MINIMAP_AREA):
                        continue
                    fields = {ch.tag: ch.text for ch in a if len(ch) == 0}
                    vols = []
                    for val in a.findall("area/value"):
                        d = {ch.tag: ch.text for ch in val}
                        vols.append({"shape": SHAPE.get(d.get("code"), d.get("code")),
                                     "position": wp.floats(d.get("position")), "rotation": wp.floats(d.get("rotation")),
                                     "scale": wp.floats(d.get("scale")), "points": wp.floats(d.get("points")),
                                     "height": float(d.get("height") or 1), "radius": float(d.get("radius") or 1)})
                    rec = {"kind": "ChangeArea" if c == CODE_CHANGE_AREA else "MinimapArea", "file": f, "member": n,
                           "hap": wp.txt(root, "name"), "hap_group": wp.txt(root, "group"),
                           "action": fields.get("name"), "action_id": fields.get("id"), "volumes": vols}
                    if c == CODE_CHANGE_AREA:
                        rec["stage_type"] = int(fields.get("StageType") or 0)
                        rec["area_type"] = int(fields.get("AreaType") or 0)
                    else:
                        rec["minimap_id"] = fields.get("h_2faf3883") or fields.get("MinimapId")
                        rec["sub_minimap_id"] = fields.get("h_a3f14842") or fields.get("SubMinimapId")
                        rec["minimap_stage_type"] = fields.get("StageType")
                    found.append(rec)
        for rec in found:  # chaine de groupes (noms + jetons) = conditions d'activation
            chain, gid, seen = [], rec["hap_group"], set()
            while gid and gid in groups and gid not in seen:
                seen.add(gid)
                g = groups[gid]
                chain.append({"id": gid, "name": g["name"], "attribute": g["attribute"],
                              "tokens": [{"code": a, "id": b} for a, b in g["tokens"]]})
                gid = g["parent"]
            rec["group_chain"] = chain
        out.extend(found)
        del mem
        if (fi + 1) % 100 == 0:
            print(f"[{fi + 1}/{len(files)}]", file=sys.stderr, flush=True)
    VOL_CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


# ------------------------------------------------------------------------------------------- geometrie

def _local(vol, p):
    """Coordonnees locales (x, y, z) : translation, rotation Y inverse. y = hauteur au-dessus de la base."""
    cx, cy, cz = vol["position"]
    ry = (vol.get("rotation") or [0, 0, 0])[1]
    dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
    c, s = math.cos(ry), math.sin(ry)
    return c * dx - s * dz, dy, s * dx + c * dz


def _extent(vol):
    sx, sy, sz = (abs(x) for x in vol["scale"])
    return sx, sy * vol.get("height", 1.0), sz


def distance(vol, p) -> float:
    """0 si p est dans le volume. Boite : base = polygone points (-1..1) x scale en x/z, y de pos.y a
    pos.y + scale.y*height (0x3dd290 compare y local a [0, hauteur]). Cylindre : rayon radius*scale.x."""
    lx, ly, lz = _local(vol, p)
    sx, h, sz = _extent(vol)
    dy = max(0.0, -ly, ly - h)
    if vol["shape"] == "cylinder":
        r = vol.get("radius", 1.0) * sx
        dr = max(0.0, math.hypot(lx, lz) - r)
        return math.hypot(dr, dy)
    ddx = max(0.0, abs(lx) - sx)
    ddz = max(0.0, abs(lz) - sz)
    return math.sqrt(ddx * ddx + dy * dy + ddz * ddz)


def size(vol) -> float:
    sx, h, sz = _extent(vol)
    if vol["shape"] == "cylinder":
        return math.pi * (vol.get("radius", 1.0) * sx) ** 2 * h
    return 4 * sx * sz * h


def aabb(vol):
    """Boite englobante monde [[xmin, ymin, zmin], [xmax, ymax, zmax]] (rotation Y prise en compte)."""
    sx, h, sz = _extent(vol)
    cx, cy, cz = vol["position"]
    if vol["shape"] == "cylinder":
        r = vol.get("radius", 1.0) * sx
        return [[round(cx - r, 2), round(cy, 2), round(cz - r, 2)], [round(cx + r, 2), round(cy + h, 2), round(cz + r, 2)]]
    ry = (vol.get("rotation") or [0, 0, 0])[1]
    c, s = math.cos(ry), math.sin(ry)
    xs, zs = [], []
    for a, b in ((-sx, -sz), (sx, -sz), (sx, sz), (-sx, sz)):
        xs.append(cx + c * a + s * b)   # inverse de _local
        zs.append(cz - s * a + c * b)
    return [[round(min(xs), 2), round(cy, 2), round(min(zs), 2)], [round(max(xs), 2), round(cy + h, 2), round(max(zs), 2)]]


# ------------------------------------------------------------------------------------------- resolution

TOK_ROOM = "0x5cda8ece"   # jeton de groupe 'salle' (id 0x100 -> r100)
UNIT_IDS = {125, 130, 135}   # Meat/Soul/God Box : interieurs = salles r5a0/r5a1/r5a2 a part
ROOM_ONLY = {25: "r501"}     # Copied City : salle r501 a part


def rooms_of_conditions(cond) -> list[str]:
    """Salles des jetons 0x5cda8ece des groupes non inverses de l'entite (ex. core_hap 'r100/r200共通')."""
    out = []
    if not isinstance(cond, dict):
        return out
    for g in cond.get("raw") or []:
        if g.get("negated"):
            continue
        for t in g.get("tokens") or []:
            if t.get("kind") == TOK_ROOM:
                try:
                    out.append("r%03x" % int(t["id"], 16))
                except (TypeError, ValueError):
                    pass
    return out


def room_of(file: str | None, context: dict | None = None) -> str | None:
    if file:
        m = re.match(r"st\d/(r[0-9a-f]{3})\.dat$", file)
        if m:
            return m.group(1)
        if file in WD_ROOM:
            return WD_ROOM[file]
        if file == "quest/qb40.dat":
            return "bunker"
    if context and context.get("room"):
        return context["room"]
    return None


class Resolver:
    def __init__(self, actions: list[dict], names: dict[int, dict]):
        self.names = names
        self.vols = []          # (action, volume)
        for a in actions:
            if a["kind"] != "ChangeArea":
                continue
            for v in a["volumes"]:
                if v.get("position") and v.get("scale"):
                    self.vols.append((a, v))
        self.by_scope = defaultdict(list)
        for a, v in self.vols:
            self.by_scope[self.scope_of_action(a)].append((a, v))
        self.by_room = defaultdict(list)
        for a, v in self.vols:
            r = room_of(a["file"])
            if r:
                self.by_room[r].append((a, v))

    @staticmethod
    def scope_of_action(a):
        return SEPARATE.get(a["file"], "world")

    def candidates(self, room):
        """Volumes applicables : la salle si elle a ses propres volumes (r100/r200 : + core_hap commun),
        espace separe (Tour r500, Bunker), sinon tout le monde ouvert (hors r500 / Bunker)."""
        if room in ("r500", "bunker"):
            return self.by_scope[room], f"scope:{room}"
        if room in ("r100", "r200"):
            return self.by_room[room] + [x for x in self.vols if x[0]["file"] == "core/corehap.dat"], f"room:{room}+core"
        if room and self.by_room.get(room):
            return self.by_room[room], f"room:{room}"
        return self.by_scope["world"], "world"

    def resolve(self, p, file=None, context=None, room=None, names=None, conditions=None):
        room = room or room_of(file, context)
        room_src = "file" if room else None
        if room is None and conditions:
            # seulement un groupe d'UNE salle ou 'r100/r200共通' (les listes longues = groupes d'arret, pas un lieu)
            rs = set(rooms_of_conditions(conditions))
            if rs and (len(rs) == 1 or rs == {"r100", "r200"}):
                r = "r200" if rs == {"r100", "r200"} else next(iter(rs))
                if self.by_room.get(r):
                    room, room_src = r, "group_token"
        hint = hint_of(names) if names else None
        if room in ROOM_DEFAULT:
            i, why = ROOM_DEFAULT[room]
            return self._out(i, "room_default_guess", "low", None, None, room, "room_default", note=why,
                             room_source=room_src)
        cands, scope = self.candidates(room)
        if not cands:
            return None
        cand_ids = {AREA_ID.get((a["stage_type"], a["area_type"])) for a, _v in cands}
        if len(cand_ids) == 1:   # espace a une seule zone (Bunker...) : pas d'ambiguite
            a, v = min(cands, key=lambda x: distance(x[1], p))
            d = distance(v, p)
            return self._out(next(iter(cand_ids)), "inside_volume" if d == 0 else "single_area_scope", "high", a,
                             round(d, 1), room, scope, room_source=room_src)
        scored = []
        for a, v in cands:
            d = distance(v, p)
            pen = 1 if (a["file"], a["hap"]) in DEPRIORITIZED else 0
            scored.append((d, pen, size(v), a, v))
        inside = [s for s in scored if s[0] == 0]
        if inside:
            inside.sort(key=lambda s: (s[1], s[2]))
            d, _pen, _sz, a, v = inside[0]
            ids = {AREA_ID.get((x[3]["stage_type"], x[3]["area_type"])) for x in inside}
            conf = "high" if len(ids) == 1 else "medium"
            alt = sorted(i for i in ids if i is not None)
            i = AREA_ID.get((a["stage_type"], a["area_type"]))
            hint_info = None
            if hint:
                hint_info = {"keyword": hint[0], "ids": sorted(hint[1]), "agrees": i in hint[1]}
                if i not in hint[1]:
                    conf = "medium"
            return self._out(i, "inside_volume", conf, a, 0.0, room, scope, room_source=room_src,
                             alternatives=alt if len(alt) > 1 else None, group_hint=hint_info)
        # hors volume : pas d'interieur d'unite de recuperation ni de Copied City (salles a part) sauf dans leur salle
        far = [s for s in scored if not (AREA_ID.get((s[3]["stage_type"], s[3]["area_type"])) in UNIT_IDS
                                         and room not in ("r5a0", "r5a1", "r5a2"))
               and ROOM_ONLY.get(AREA_ID.get((s[3]["stage_type"], s[3]["area_type"])), room) == room]
        scored = far or scored
        scored.sort(key=lambda s: (s[0], s[1]))
        if hint:
            hs = [s for s in scored if AREA_ID.get((s[3]["stage_type"], s[3]["area_type"])) in hint[1]]
            # l'indice n'est retenu que s'il designe un volume de la meme region (distance comparable)
            if hs and hs[0][0] <= scored[0][0] + 150:
                d, _pen, _sz, a, v = hs[0]
                i = AREA_ID.get((a["stage_type"], a["area_type"]))
                return self._out(i, "group_name_hint", "medium", a, round(d, 1), room, scope, room_source=room_src,
                                 group_hint={"keyword": hint[0], "ids": sorted(hint[1])},
                                 nearest_any=AREA_ID.get((scored[0][3]["stage_type"], scored[0][3]["area_type"])))
        d, _pen, _sz, a, v = scored[0]
        i = AREA_ID.get((a["stage_type"], a["area_type"]))
        # 2e volume le plus proche d'une AUTRE zone : marge d'ambiguite
        other = next((s for s in scored[1:] if AREA_ID.get((s[3]["stage_type"], s[3]["area_type"])) != i), None)
        margin = (other[0] - d) if other else None
        conf = "medium" if d <= 40 and (margin is None or margin > 15) else "low"
        return self._out(i, "nearest_volume", conf, a, round(d, 1), room, scope, room_source=room_src,
                         runner_up=(AREA_ID.get((other[3]["stage_type"], other[3]["area_type"])) if other else None),
                         margin=round(margin, 1) if margin is not None else None)

    def _out(self, i, method, conf, a, dist, room, scope, **extra):
        area, sub, label = display(self.names, i)
        o = {"area": area, "sub_area": sub, "label": label, "area_id": i, "method": method, "confidence": conf,
             "room": room, "scope": scope}
        if extra.get("room_source"):
            o["room_source"] = extra.pop("room_source")
        extra.pop("room_source", None)
        if a is not None:
            o["volume"] = {"file": a["file"], "hap": a["hap"], "action": a["action"], "distance": dist}
        for k, v in extra.items():
            if v is not None:
                o[k] = v
        if i == 20:
            o["note"] = "vaisseau extraterrestre : '???' tant que UI_nameAS est faux ; CORE_MAP_AREA_160 sans texte"
        if i == 165:
            o["note"] = "'???' tant que la variable UI_namePV est fausse"
        return o


def area_of(pos, file=None, room=None, context=None, names=None, conditions=None, _cache={}):  # noqa: B006
    """API : position (x, y, z) [+ fichier source ou salle 'r160', noms japonais hap/groupes] -> dict zone
    (area, sub_area, label, area_id, method, confidence...). Voir Resolver.resolve."""
    if "r" not in _cache:
        _cache["r"] = Resolver(collect_volumes(), area_names(texts()))
    return _cache["r"].resolve(pos, file=file, context=context, room=room, names=names, conditions=conditions)


# ------------------------------------------------------------------------------------------- verification exe

def verify_exe():
    """Recalcule AREA_ID (emulation unicorn de 0x385f20) et les cles (tables de sauts 0x86d150/0x86f9d0)."""
    import struct
    import xref  # noqa: PLC0415
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64  # noqa: PLC0415
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_R8, UC_X86_REG_RDX, UC_X86_REG_RSP  # noqa: PLC0415
    base, lo, hi = 0x140000000, 0x385000, 0x387000
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(base + lo, hi - lo)
    mu.mem_write(base + lo, xref.D[xref.rva2off(lo):xref.rva2off(lo) + hi - lo])
    mu.mem_map(0x10000, 0x10000)
    got = {}
    for st in range(10):
        for at in range(10):
            mu.reg_write(UC_X86_REG_RSP, 0x1f000)
            mu.mem_write(0x1f000, (0x18000).to_bytes(8, "little"))
            mu.reg_write(UC_X86_REG_RDX, st)
            mu.reg_write(UC_X86_REG_R8, at)
            mu.emu_start(base + 0x385f20, 0x18000, count=200)
            r = mu.reg_read(UC_X86_REG_EAX)
            if r != 0xFFFFFFFF:
                got[(st, at)] = r
    assert got == AREA_ID, ("AREA_ID", got)

    def keys(fn_bytetab, dwtab, n):
        out = {}
        for i in range(n):
            k = xref.D[xref.rva2off(fn_bytetab) + i]
            tgt = struct.unpack_from("<i", xref.D, xref.rva2off(dwtab) + 4 * k)[0]
            o = xref.rva2off(tgt)
            m = re.search(rb"\x48\x8d\x0d(....)", xref.D[o:o + 64], re.S)
            if m and m.start() < 40:
                a = tgt + m.start() + 7 + struct.unpack("<i", m.group(1))[0]
                s = xref.D[xref.rva2off(a):xref.D.index(b"\0", xref.rva2off(a))].decode()
                if s.startswith("CORE_"):
                    out[i] = s
        return out
    main = keys(0x86d3b8, 0x86d380, 0xd3)
    sub = keys(0x86fbb4, 0x86fb48, 0xd3)
    for i, k in MAIN_KEY.items():
        assert main.get(i) == k, ("main", i, main.get(i), k)
    for i, k in SUB_KEY.items():
        if i <= 0xd2:
            assert sub.get(i) == k, ("sub", i, sub.get(i), k)
    print("verify_exe : OK (", len(got), "couples, ", len(main), "cles de zone,", len(sub), "cles de sous-zone )")


# ------------------------------------------------------------------------------------------- etiquetage

def _is_pos(x):
    return isinstance(x, list) and len(x) >= 3 and all(isinstance(c, (int, float)) for c in x[:3])


def label_tree(node, res: Resolver, stats, file=None, context=None, path=""):
    """Ajoute `area` a tout dict portant 'position' (ou 'centroid' pour les zones de peche)."""
    if isinstance(node, dict):
        f = node.get("file") if isinstance(node.get("file"), str) else file
        ctx = node.get("context") if isinstance(node.get("context"), dict) else context
        pos = node.get("position") if _is_pos(node.get("position")) else (
            node.get("centroid") if _is_pos(node.get("centroid")) else None)
        if pos is not None and path.split("/")[1:2] != ["files"]:
            a = res.resolve(pos[:3], file=f, context=ctx, names=entity_names(node), conditions=node.get("conditions"))
            stats["positions"] += 1
            if a:
                node["area"] = a
                stats["labeled"] += 1
                stats["by_method"][a["method"]] += 1
                stats["by_conf"][a["confidence"]] += 1
        for k, v in node.items():
            if k in ("area", "conditions", "box", "params"):
                continue
            label_tree(v, res, stats, f, ctx, path + "/" + str(k))
    elif isinstance(node, list):
        for x in node:
            label_tree(x, res, stats, file, context, path)


# ------------------------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESEARCH), help="dossier de areas.json")
    ap.add_argument("--wp", default=str(RESEARCH / "world_positions.json"), help="world_positions.json a etiqueter")
    ap.add_argument("--refresh", action="store_true", help="relire les .pak (sinon cache des volumes)")
    ap.add_argument("--verify-exe", action="store_true", help="recalculer les tables depuis NieRAutomata.exe")
    ap.add_argument("--no-label", action="store_true", help="ne pas modifier world_positions.json")
    args = ap.parse_args()
    out = Path(args.out)
    if args.verify_exe:
        verify_exe()
    actions = collect_volumes(args.refresh)
    tx = texts()
    names = area_names(tx)
    res = Resolver(actions, names)

    wp_path = Path(args.wp)
    data = json.loads(wp_path.read_text(encoding="utf-8"))
    stats = {"positions": 0, "labeled": 0, "by_method": Counter(), "by_conf": Counter()}
    label_tree(data, res, stats)
    sec_stats = {}
    for sec in ("chests", "item_pickups", "quest_npcs", "shops", "access_points", "fishing", "unique_items",
                "gaps_resolved"):
        if sec in data:
            s = {"positions": 0, "labeled": 0, "by_method": Counter(), "by_conf": Counter()}
            _count(data[sec], s)
            sec_stats[sec] = {"positions": s["positions"], "labeled": s["labeled"],
                              "by_confidence": dict(s["by_conf"]), "by_method": dict(s["by_method"])}
    data.setdefault("summary", {})["areas"] = {
        "source": "tools/areas.py (ChangeAreaAction des *.pak + tables exe 0x385f20/0x86d150/0x86f9d0)",
        "positions": stats["positions"], "labeled": stats["labeled"],
        "by_method": dict(stats["by_method"]), "by_confidence": dict(stats["by_conf"]), "by_section": sec_stats}
    if not args.no_label:
        wp_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # areas.json
    counts = defaultdict(Counter)
    rooms_seen = defaultdict(Counter)
    for sec, key in (("chests", "chests"), ("item_pickups", "collection_points")):
        for e in data[sec]:
            a = e.get("area")
            if a:
                counts[a["area_id"]][key] += 1
                rooms_seen[a["area_id"]][a.get("room") or "world"] += 1
    by_id = defaultdict(list)
    for a in actions:
        if a["kind"] == "ChangeArea":
            by_id[AREA_ID.get((a["stage_type"], a["area_type"]))].append(a)
    areas = []
    for i, e in sorted(names.items()):
        acts = by_id.get(i, [])
        ent = dict(e)
        ent["label"] = display(names, i)[2]
        ent["stage_group"] = STAGE_TYPE.get(e["stage_type"])
        ent["counts"] = {"chests": counts[i]["chests"], "collection_points": counts[i]["collection_points"]}
        ent["rooms"] = sorted({room_of(a["file"]) or a["file"] for a in acts})
        ent["rooms_of_labeled_entities"] = dict(rooms_seen[i])
        ent["volumes"] = [{"file": a["file"], "member": a["member"], "hap": a["hap"], "action": a["action"],
                           "conditions": [g["name"] for g in a.get("group_chain", [])],
                           "deprioritized": DEPRIORITIZED.get((a["file"], a["hap"])),
                           "shapes": [{"shape": v["shape"], "position": v["position"], "rotation": v["rotation"],
                                       "scale": v["scale"], "radius": v["radius"] if v["shape"] == "cylinder" else None,
                                       "aabb": aabb(v)} for v in a["volumes"]]} for a in acts]
        bbs = [aabb(v) for a in acts if (a["file"], a["hap"]) not in DEPRIORITIZED for v in a["volumes"]]
        ent["bounds_aabb"] = ([[min(b[0][k] for b in bbs) for k in range(3)], [max(b[1][k] for b in bbs) for k in range(3)]]
                              if bbs else None)
        if i in (185, 195):
            ent["note"] = "aucun volume ChangeArea dans les donnees ; attribue par defaut aux salles DLC (DEDUIT)"
        if i in (170, 180):
            ent["note"] = "aucun volume ChangeArea trouve (StageType 0 / AreaType 6 ou 8) dans les donnees lues"
        if i == 190:
            ent["note"] = ("aucun volume ; 0x86f9d0 ne donne pas de sous-zone (CORE_SUB_MAP_AREA_036 'Arena' de messdlc1 "
                           "n'est pas reference par l'exe)")
        areas.append(ent)
    by_main = defaultdict(Counter)
    for e in areas:
        m = display(names, e["id"])[0] or "?"
        by_main[m]["chests"] += e["counts"]["chests"]
        by_main[m]["collection_points"] += e["counts"]["collection_points"]
    minimap = [{"file": a["file"], "hap": a["hap"], "action": a["action"], "minimap_id": a.get("minimap_id"),
                "stage_type": a.get("minimap_stage_type"), "shapes": [aabb(v) for v in a["volumes"]]}
               for a in actions if a["kind"] == "MinimapArea"]
    doc = {
        "_source": "tools/areas.py (lecture seule) ; voir data_formats.md 'Zones (areas)'",
        "mechanism": ("hap::ChangeAreaAction (code 0x1571c131) : HIT (entree) dans un volume -> id = 0x385f20(StageType, "
                      "AreaType) -> global RVA 0x1494a04 ; noms 0x86d150 (zone) / 0x86f9d0 (sous-zone). Semantique "
                      "'dernier volume entre' : l'etiquetage statique prend le plus petit volume contenant, sinon le plus "
                      "proche (approximation)."),
        "geometry": ("boite : centre position, demi-tailles scale.x/scale.z (points -1..1), y de position.y a "
                     "position.y + scale.y*height, rotation Y (sens de rotation DEDUIT) ; cylindre : rayon radius*scale.x"),
        "areas": areas,
        "totals_by_area": {k: dict(v) for k, v in sorted(by_main.items())},
        "room_defaults": {k: {"area_id": v[0], "label": display(names, v[0])[2], "reason": v[1]}
                          for k, v in ROOM_DEFAULT.items()},
        "conflicts": [{"file": k[0], "hap": k[1], "note": v} for k, v in DEPRIORITIZED.items()],
        "minimap_volumes": minimap,
        "labeling": data["summary"]["areas"],
    }
    (out / "areas.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"positions {stats['positions']}, etiquetees {stats['labeled']} "
          f"({100 * stats['labeled'] / max(1, stats['positions']):.1f} %) ; methodes {dict(stats['by_method'])} ; "
          f"confiance {dict(stats['by_conf'])}")


def _count(node, s):
    if isinstance(node, dict):
        if "area" in node and isinstance(node["area"], dict) and "area_id" in node["area"]:
            s["labeled"] += 1
            s["by_method"][node["area"]["method"]] += 1
            s["by_conf"][node["area"]["confidence"]] += 1
        if _is_pos(node.get("position")) or _is_pos(node.get("centroid")):
            s["positions"] += 1
        for k, v in node.items():
            if k not in ("area", "conditions", "box", "params"):
                _count(v, s)
    elif isinstance(node, list):
        for x in node:
            _count(x, s)


if __name__ == "__main__":
    main()
