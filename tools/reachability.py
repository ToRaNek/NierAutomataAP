"""Estimation statique des capacites de mouvement necessaires pour atteindre coffres et points de collecte.

Lecture seule du jeu. Deux etapes (relancables, un .dat a la fois, peu de RAM) :
  python tools/reachability.py extract   # cellules wd*/g*.dat -> triangles COL2 + Layout.lay en cache
  python tools/reachability.py run       # -> docs/research/reachability.json + resume
Options de seuils : voir --help (valeurs par defaut = HYPOTHESES, voir docs/research/reachability.md).

Format COL2 (verifie par lecture, version 0x20151201) :
  en-tete <4s I(version) I namesOff I namesCnt I meshOff I meshCnt I boneMapOff I boneMapCnt
           I boneMap2Off I boneMap2Cnt I meshMapOff I meshMapCnt I treeOff I treeCnt>
  noms   : namesCnt x u32 offset -> chaine C
  mesh   : 20 o <I flags, i nameIndex, i batchType, I batchOff, I batchCnt>   (meshOff peut etre non aligne)
  batch type 2 : 20 o <i boneIndex, I vertOff, I vertCnt, I idxOff, I idxCnt> ; type 3 : 16 o (sans boneIndex)
  sommet : 4 x f32 (x, y, z, 1) ; indices : u16, triangles (3 par face). boneIndex -1 = coordonnees monde.
  arbre : treeCnt noeuds (BVH, non utilise ici).
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpk  # noqa: E402
import extract_research as er  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "docs" / "research"
CACHE = er.CACHE / "reachability"
WD_RE = re.compile(r"wd[1-5a]/g[0-9a-f]+\.dat$")


# ------------------------------------------------------------------------------------------------ COL2

def parse_col2(b: bytes):
    """-> (tris float32 (N,3,3), flags uint32 (N,), mesh_idx int32 (N,), names, stats)."""
    magic, ver, no, nc, mo, mc = struct.unpack_from("<4s5I", b, 0)
    assert magic == b"COL2", magic
    names = []
    for i in range(nc):
        o = struct.unpack_from("<I", b, no + 4 * i)[0]
        names.append(b[o:b.index(b"\0", o)].decode("ascii", "replace"))
    tris, flags, midx = [], [], []
    stats = Counter()
    for m in range(mc):
        fl, ni, bt, bo, bc = struct.unpack_from("<IiiII", b, mo + 20 * m)
        stats[f"batchType{bt}"] += 1
        for k in range(bc):
            if bt == 2:
                bone, vo, vc, io, ic = struct.unpack_from("<iIIII", b, bo + 20 * k)
            elif bt == 3:
                bone = -1
                vo, vc, io, ic = struct.unpack_from("<IIII", b, bo + 16 * k)
            else:
                stats["unknownBatchType"] += 1
                continue
            if bone != -1:
                stats["boned_batches_skipped"] += 1
                continue
            v = np.frombuffer(b, "<f4", vc * 4, vo).reshape(vc, 4)[:, :3]
            ix = np.frombuffer(b, "<u2", ic, io).astype(np.int64)
            ix = ix[: len(ix) // 3 * 3].reshape(-1, 3)
            if len(ix) == 0 or ix.max() >= vc:
                stats["bad_index_batches"] += 1
                continue
            tris.append(v[ix])
            flags.append(np.full(len(ix), fl, np.uint32))
            midx.append(np.full(len(ix), m, np.int32))
    if not tris:
        return np.zeros((0, 3, 3), np.float32), np.zeros(0, np.uint32), np.zeros(0, np.int32), names, stats
    return (np.concatenate(tris).astype(np.float32), np.concatenate(flags), np.concatenate(midx), names, stats)


def parse_lay(b: bytes):
    """Layout.lay (LAY\\0, f32 version 2.01) -> [(nom, pos, rot, scale)]. Instance = 112 o :
    nom[32], pos 4f, rot 4f, scale 4f, u32 ?, remplissage."""
    _m, _v, ao, ac, io, ic = struct.unpack_from("<4sf4I", b, 0)
    out = []
    for i in range(ic):
        o = io + 112 * i
        name = b[o:o + 32].split(b"\0")[0].decode("ascii", "replace")
        pos = struct.unpack_from("<3f", b, o + 32)
        rot = struct.unpack_from("<3f", b, o + 48)
        sc = struct.unpack_from("<3f", b, o + 64)
        out.append((name, pos, rot, sc))
    return out


# ------------------------------------------------------------------------------------------------ extract

def cmd_extract(args):
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = er._toc_index()
    names = sorted(n for n in idx if WD_RE.match(n))
    manifest_p = CACHE / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
    for i, n in enumerate(names):
        if n in manifest:
            continue
        p, row = idx[n]
        entry = {"cpk": p.name, "col": None, "lay": None}
        if row["FileSize"] > 200:
            dat = cpk.dat_files(cpk.extract(p, row))
            key = n.replace("/", "__")[:-4]
            for m, data in dat.items():
                if m.endswith(".col") and data[:4] == b"COL2":
                    tris, fl, mi, mnames, st = parse_col2(data)
                    np.savez_compressed(CACHE / f"{key}.npz", tris=tris, flags=fl, mesh=mi)
                    lo = tris.reshape(-1, 3).min(0).tolist() if len(tris) else None
                    hi = tris.reshape(-1, 3).max(0).tolist() if len(tris) else None
                    entry["col"] = {"member": m, "tris": int(len(tris)), "meshes": int(mi.max() + 1) if len(mi) else 0,
                                    "names": mnames, "bbox": [lo, hi], "stats": dict(st),
                                    "flags": {hex(k): int(v) for k, v in Counter(fl.tolist()).items()}}
                elif m == "Layout.lay":
                    entry["lay"] = [[a, list(b_), list(c), list(d)] for a, b_, c, d in parse_lay(data)]
            del dat
        manifest[n] = entry
        manifest_p.write_text(json.dumps(manifest))
        print(f"[{i + 1}/{len(names)}] {n} col={entry['col'] and entry['col']['tris']}", flush=True)
    print("ok", len(manifest))




# ------------------------------------------------------------------------------------------------ cartes

def map_key(tile: str) -> str:
    """wd1..wd4 = grilles de cellules g<monde><XX><YY> (une carte par dossier) ; wd5/wda = une carte par fichier."""
    d, f = tile.split("/")
    return d if d in ("wd1", "wd2", "wd3", "wd4") else f"{d}/{f[:-4]}"


HEX_R = 100.0  # rayon des cellules hexagonales des grilles wd1/wd3


def tile_offset(tile: str) -> tuple[float, float]:
    """Decalage monde (Cx, Cz) d'une cellule de grille g<monde><AA><BB> (AA, BB lus en DECIMAL) :
    grille hexagonale de rayon 100 m (noms de maillage "HexGround") :
      Cx = 150 * (AA - 12) ; Cz = 173.205 * (BB - 16) + 86.603 * (AA - 14).
    Deduit par recalage independant de 13 cellules sur les ancres (ecart <= 4 m sauf 1, voir data_formats.md) ;
    valide par les 233 positions relevees en jeu (sol a 0-0,5 m sous chacune).
    Cartes wd5/wda : deja en coordonnees monde (0, 0)."""
    d, f = tile.split("/")
    if d in ("wd1", "wd2", "wd3", "wd4"):
        aa, bb = int(f[2:4]), int(f[4:6])
        return 1.5 * HEX_R * (aa - 12), math.sqrt(3) * HEX_R * (bb - 16) + math.sqrt(3) / 2 * HEX_R * (aa - 14)
    return 0.0, 0.0


class World:
    """Triangles COL2 par cellule, rasterises a la demande en couches de sol (pas `cell` m), LRU en memoire."""

    def __init__(self, cell=1.0, walk_ny=0.6, max_tiles=16):
        self.manifest = json.loads((CACHE / "manifest.json").read_text())
        self.cell, self.walk_ny, self.max_tiles = cell, walk_ny, max_tiles
        self.tiles = {}
        for n, e in self.manifest.items():
            if e.get("col") and e["col"]["tris"]:
                lo, hi = e["col"]["bbox"]
                cx, cz = tile_offset(n)
                lo, hi = [lo[0] + cx, lo[1], lo[2] + cz], [hi[0] + cx, hi[1], hi[2] + cz]
                self.tiles[n] = (map_key(n), lo, hi)
        self._lru: dict[str, np.ndarray] = {}
        self._test = {map_key(n) for n, e in self.manifest.items() if e.get("col") and e["col"]["names"] == ["test"]}

    def is_test_map(self, mk):
        return mk in self._test

    def maps_at(self, x, z, margin=0.0):
        out = defaultdict(list)
        for n, (mk, lo, hi) in self.tiles.items():
            if lo[0] - margin <= x <= hi[0] + margin and lo[2] - margin <= z <= hi[2] + margin:
                out[mk].append(n)
        return out

    def tile_points(self, n):
        """Points de sol (ix, iz, h) de la cellule n : centres de case couverts par un triangle praticable."""
        if n in self._lru:
            self._lru[n] = self._lru.pop(n)
            return self._lru[n]
        key = n.replace("/", "__")[:-4]
        pf = CACHE / f"{key}.wfloor{self.cell:g}_{self.walk_ny:g}.npy"
        if pf.exists():
            pts = np.load(pf)
        else:
            with np.load(CACHE / f"{key}.npz") as z:
                t = z["tris"].astype(np.float64)
            cx, cz = tile_offset(n)  # local -> monde
            t[:, :, 0] += cx
            t[:, :, 2] += cz
            nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            ln = np.linalg.norm(nrm, axis=1)
            ok = ln > 1e-9
            ny = np.zeros(len(t))
            ny[ok] = np.abs(nrm[ok, 1]) / ln[ok]  # orientation ignoree : |ny|
            t = t[ny >= self.walk_ny]
            pts = rasterize(t, self.cell)
            np.save(pf, pts)
        self._lru[n] = pts
        while len(self._lru) > self.max_tiles:
            self._lru.pop(next(iter(self._lru)))
        return pts

    def window(self, tiles, x, z, r):
        c = self.cell
        x0, x1 = math.floor((x - r) / c), math.floor((x + r) / c)
        z0, z1 = math.floor((z - r) / c), math.floor((z + r) / c)
        parts = []
        for n in tiles:
            p = self.tile_points(n)
            m = (p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= z0) & (p[:, 1] <= z1)
            if m.any():
                parts.append(p[m])
        if not parts:
            return np.zeros((0, 3), np.float32)
        return np.concatenate(parts)


def rasterize(t: np.ndarray, cell: float) -> np.ndarray:
    """Triangles (N,3,3) -> points (ix, iz, h) float32 : hauteur du plan du triangle au centre de chaque case
    ((ix+0.5)*cell, (iz+0.5)*cell) contenue dans sa projection XZ ; un triangle plus petit qu'une case donne le
    point de son barycentre."""
    out = []
    for tri in t:
        xs, zs = tri[:, 0], tri[:, 2]
        ix0, ix1 = math.floor(xs.min() / cell - 0.5), math.ceil(xs.max() / cell - 0.5)
        iz0, iz1 = math.floor(zs.min() / cell - 0.5), math.ceil(zs.max() / cell - 0.5)
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
        den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(den) < 1e-9:
            continue
        gx, gz = np.meshgrid(np.arange(ix0, ix1 + 1), np.arange(iz0, iz1 + 1), indexing="ij")
        px, pz = (gx + 0.5) * cell, (gz + 0.5) * cell
        l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / den
        l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if m.any():
            h = l1[m] * ay + l2[m] * by + l3[m] * cy
            out.append(np.stack([gx[m], gz[m], h], 1))
        else:
            out.append(np.array([[math.floor(xs.mean() / cell), math.floor(zs.mean() / cell), tri[:, 1].mean()]]))
    if not out:
        return np.zeros((0, 3), np.float32)
    return np.concatenate(out).astype(np.float32)


# ------------------------------------------------------------------------------------------------ graphe local

class Local:
    """Couches de sol d'une fenetre : noeuds (case, hauteur), hauteurs a moins de `merge` m fusionnees."""

    def __init__(self, pts, merge=0.4):
        cells = defaultdict(list)
        for ix, iz, h in pts.tolist():
            cells[(int(ix), int(iz))].append(h)
        self.node_cell, self.node_h, self.by_cell = [], [], {}
        for c, hs in cells.items():
            hs.sort()
            layers = [hs[0]]
            for h in hs[1:]:
                if h - layers[-1] > merge:
                    layers.append(h)
                else:
                    layers[-1] = max(layers[-1], h)
            ids = []
            for h in layers:
                ids.append(len(self.node_h))
                self.node_cell.append(c)
                self.node_h.append(h)
            self.by_cell[c] = ids
        self.cx = np.array([c[0] for c in self.node_cell], np.int32)
        self.cz = np.array([c[1] for c in self.node_cell], np.int32)
        self.h = np.array(self.node_h, np.float64)

    def floor_below(self, ix, iz, y, up=0.6, down=6.0, rad=1):
        """Couche la plus proche sous y (dans [y-down, y+up]) des cases a <= rad -> (noeud, h) ou None.
        Priorite : case la plus proche, puis couche la plus haute."""
        best = None
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                for n in self.by_cell.get((ix + dx, iz + dz), ()):
                    h = self.node_h[n]
                    if y - down <= h <= y + up:
                        k = (max(abs(dx), abs(dz)), -h)
                        if best is None or k < best[0]:
                            best = (k, n, h)
        return (best[1], best[2]) if best else None

    def adjacent(self, n):
        cx, cz = self.node_cell[n]
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx or dz:
                    yield from self.by_cell.get((cx + dx, cz + dz), ())

    def min_climb(self, start, targets, cap=80.0):
        """Minimax entre cases voisines : plus petite "plus grande montee" sur un chemin cible -> start.
        Recherche a rebours depuis start : aller de v (exterieur) a u (vers l'objet) demande h[u]-h[v]."""
        best = {start: 0.0}
        pq = [(0.0, start)]
        while pq:
            c, u = heapq.heappop(pq)
            if c > best.get(u, 1e9):
                continue
            if u in targets:
                return c, u
            for v in self.adjacent(u):
                nc = max(c, self.node_h[u] - self.node_h[v])
                if nc < best.get(v, 1e9) and nc <= cap:
                    best[v] = nc
                    heapq.heappush(pq, (nc, v))
        return None, None

    def reach(self, start, targets, jump, gap, glide, step, cell, max_drop=40.0):
        """Une cible permet-elle d'atteindre start ? Aretes a rebours (le joueur va de v a u) :
        - cases voisines : h[u]-h[v] <= max(step, jump) ;
        - saut au-dessus du vide depuis un noeud de bord : distance <= gap + glide * (h[v]-h[u]) et
          h[u]-h[v] <= jump (on ne monte pas plus haut que le saut)."""
        seen = {start}
        todo = [start]
        rg = int(math.ceil((gap + glide * max_drop) / cell))
        while todo:
            u = todo.pop()
            if u in targets:
                return True, u
            hu = self.node_h[u]
            for v in self.adjacent(u):
                if v not in seen and hu - self.node_h[v] <= max(step, jump):
                    seen.add(v)
                    todo.append(v)
            if gap <= 0:
                continue
            cxu, czu = self.node_cell[u]
            edge = any(not any(abs(self.node_h[w] - hu) <= step for w in self.by_cell.get((cxu + dx, czu + dz), ()))
                       for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz)
            if not edge:
                continue
            m = (np.abs(self.cx - cxu) <= rg) & (np.abs(self.cz - czu) <= rg)
            idx = np.nonzero(m)[0]
            d = np.hypot(self.cx[idx] - cxu, self.cz[idx] - czu) * cell
            dh = hu - self.h[idx]  # > 0 : il faut monter de v vers u
            ok = (dh <= jump) & (d <= gap + glide * np.clip(-dh, 0.0, max_drop)) & (d > 1.5 * cell)
            for v in idx[ok].tolist():
                if v not in seen:
                    seen.add(v)
                    todo.append(v)
        return False, None


# ------------------------------------------------------------------------------------------------ donnees

def load_locations():
    wp = json.loads((RESEARCH / "world_positions.json").read_text(encoding="utf-8"))
    out, seen = [], Counter()
    for kind, key in (("chest", "chests"), ("pickup", "item_pickups")):
        for e in wp[key]:
            lid = f"{kind}:{e['file']}:{e['member']}:{e['entity_id']}"
            seen[lid] += 1
            if seen[lid] > 1:
                lid += f"#{seen[lid]}"
            out.append({"id": lid, "kind": kind, "objId": e["objId"], "pos": e["position"], "file": e["file"],
                        "hap": e.get("hap"), "box": (e.get("box") or {}).get("boxdata_index")})
    return out, wp


def load_anchors(wp):
    """Positions ou le joueur se tient a coup sur : releves en jeu (tools/path_log.tsv), departs de sous-phase
    (routes_full.json start_pos), terminaux/points d'acces, PNJ (objId pl*/um*) des quetes et magasins."""
    pts = []
    pl = ROOT / "tools" / "path_log.tsv"
    if pl.exists():
        for line in pl.read_text(encoding="utf-8").splitlines():
            f = line.split("\t")
            if len(f) >= 5:
                try:
                    pts.append((float(f[2]), float(f[3]), float(f[4]), "path_log"))
                except ValueError:
                    pass
    rf = json.loads((RESEARCH / "routes_full.json").read_text(encoding="utf-8"))
    for steps in list(rf["routes"].values()) + list(rf.get("other_phases", {}).values()):
        for s in steps:
            sp = isinstance(s, dict) and s.get("start_pos")
            if sp:
                pts.append((sp["x"], sp["y"], sp["z"], "start_pos"))

    def walk(o):
        if isinstance(o, dict):
            oid = o.get("objId") or ""
            if isinstance(o.get("position"), list) and (oid.startswith(("pl", "um")) or oid in ("ba1000", "ba1100")):
                x, y, z = o["position"]
                pts.append((x, y, z, "npc" if oid[:2] in ("pl", "um") else "terminal"))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for k in ("quest_npcs", "shops", "access_points"):
        walk(wp.get(k))
    uniq = {(round(x, 1), round(y, 1), round(z, 1)): s for x, y, z, s in pts}
    return np.array([k for k in uniq], np.float64), list(uniq.values())


# ------------------------------------------------------------------------------------------------ analyse

def tiers(a):
    """Niveaux de capacites (cumulatifs). Le saut simple et le vol plane du Pod (maintenir saut) sont
    toujours disponibles ; l'esquive au sol n'apporte rien de plus pour franchir (hypothese)."""
    return [
        ([], a.jump1, a.gap1),
        (["Double Jump"], a.jump2, a.gap2),
        (["Double Jump", "Air Dash"], a.jump2, a.gap3),
    ]


def analyse(world, loc, anchors, a):
    x, y, z = loc["pos"]
    cell = a.cell
    ix, iz = math.floor(x / cell), math.floor(z / cell)
    cands = world.maps_at(x, z, margin=2.0)
    if not cands:
        return {"needs": "unknown", "confidence": "low", "map": None,
                "evidence": "aucune cellule COL2 ne couvre cette position (interieur sans collision chargee ?)"}
    # choix de la carte : sol le plus proche sous l'objet
    fits = []
    own = map_key(loc["file"]) if WD_RE.match(loc["file"]) else None
    for mk, tiles in cands.items():
        pts = world.window(tiles, x, z, 2.5)
        fb = Local(pts).floor_below(ix, iz, y, up=a.up_tol, down=a.down_max, rad=1)
        score = abs(y - fb[1]) if fb else 1e9
        if fb and world.is_test_map(mk):
            score += 3.0  # cartes "test" (g5a001/g5a002 : copies d'essai) en dernier
        if fb and own == mk:
            score -= 3.0  # carte du fichier de l'entite
        fits.append((score, mk, tiles, fb))
    fits.sort(key=lambda f: f[0])
    _score, mk, tiles, fb0 = fits[0]
    alts = {f[1]: (round(y - f[3][1], 2) if f[3] else None) for f in fits}
    res = {"map": mk, "map_candidates": alts}
    if fb0 is None:
        res.update(needs="unknown", confidence="low", nearest_floor_delta=None,
                   evidence=f"aucun sol praticable dans [{-a.down_max}, +{a.up_tol}] m sous l'objet (cartes {sorted(alts)})")
        return res
    pts = world.window(tiles, x, z, a.radius)
    L = Local(pts)
    fb = L.floor_below(ix, iz, y, up=a.up_tol, down=a.down_max, rad=1)
    start, hf = fb
    res["nearest_floor_delta"] = round(y - hf, 2)
    res["floor_height"] = round(hf, 2)
    # cibles : noeuds sous une ancre (le joueur s'y tient) + noeuds du bord de la fenetre
    targets = set()
    near = anchors[(np.abs(anchors[:, 0] - x) <= a.radius) & (np.abs(anchors[:, 2] - z) <= a.radius)]
    n_anchor = 0
    anchor_nodes = set()
    for ax, ay, az in near.tolist():
        f = L.floor_below(math.floor(ax / cell), math.floor(az / cell), ay, up=1.0, down=2.5, rad=1)
        if f:
            anchor_nodes.add(f[0]); n_anchor += 1
    targets |= anchor_nodes
    r_cells = a.radius / cell
    dcx, dcz = L.cx - ix, L.cz - iz
    border = np.nonzero(np.maximum(np.abs(dcx), np.abs(dcz)) >= r_cells - 1.5)[0]
    # bord de fenetre : on suppose que l'exterieur est relie au reste de la carte (toute hauteur).
    targets |= set(border.tolist())
    # sol environnant : couche la plus basse a 3-8 m de l'objet, au plus 40 m sous son sol (rue sous un toit...)
    dist = np.hypot(dcx, dcz) * cell
    ring = (dist >= 3) & (dist <= 8) & (L.h >= hf - 40) & (L.h <= hf + a.up_tol)
    ground = float(L.h[ring].min()) if ring.any() else hf
    res["ground_height"] = round(ground, 2)
    res["height_above_ground"] = round(y - ground, 2)
    res["anchors_in_window"] = n_anchor
    if start in targets:
        res.update(needs=[], min_climb=0.0, confidence="high" if n_anchor else "medium",
                   evidence="le sol sous l objet porte une ancre (PNJ, terminal, depart, releve en jeu) ou touche le bord de fenetre")
        return res
    mc, _ = L.min_climb(start, targets)
    res["min_climb"] = None if mc is None else round(mc, 2)
    for k, (needs, j, g) in enumerate(tiers(a)):
        ok, hit = L.reach(start, targets, j, g, a.glide, a.step, cell)
        if not ok:
            continue
        via = ("ancre" if hit in anchor_nodes else "bord de fenetre") + f" (sol {L.node_h[hit]:.1f})"
        if not needs:
            conf = "high" if (mc is not None and mc <= a.step + 0.01) else "medium"
        else:
            # a la limite : le niveau precedent passe avec une marge de +margin m (saut et vide)
            pn, pj, pg = tiers(a)[k - 1]
            border_ok, _ = L.reach(start, targets, pj + a.margin, pg + a.margin, a.glide, a.step, cell)
            conf = "low" if border_ok else ("medium" if needs == ["Double Jump"] else "low")
            res["borderline"] = bool(border_ok)
        res.update(needs=needs, confidence=conf,
                   evidence=f"atteint depuis {via} avec montee <= {j} m / vide <= {g} m (+vol plane x{a.glide}) ; "
                            f"montee minimale entre cases voisines {res['min_climb']} m")
        return res
    res.update(needs="unknown", confidence="low",
               evidence=f"non atteint meme avec Double Jump + Air Dash dans un rayon de {a.radius} m "
                        f"(ascenseur/echelle/objet mobile/collision d'un decor bg, ou acces lointain) ; "
                        f"montee minimale {res['min_climb']} m")
    return res


def cmd_run(a):
    world = World(cell=a.cell, walk_ny=a.walk_ny)
    locs, wp = load_locations()
    anchors, _src = load_anchors(wp)
    anchors = anchors.reshape(-1, 3)
    # ordre spatial : reutilise les cellules en cache LRU
    locs.sort(key=lambda l: (round(l["pos"][0] / 250), round(l["pos"][2] / 250)))
    out = {}
    for i, loc in enumerate(locs):
        if a.limit and i >= a.limit:
            break
        try:
            r = analyse(world, loc, anchors, a)
        except Exception as e:  # pragma: no cover
            r = {"needs": "unknown", "confidence": "low", "evidence": f"erreur {e!r}"}
        r = {"kind": loc["kind"], "objId": loc["objId"], "position": loc["pos"], "file": loc["file"],
             "hap": loc["hap"], **r}
        out[loc["id"]] = r
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(locs)}", flush=True)
    summ = Counter()
    for r in out.values():
        k = "unknown" if r["needs"] == "unknown" else ("+".join(r["needs"]) or "none")
        summ[(r["kind"], k, r["confidence"])] += 1
    by_class = Counter("unknown" if r["needs"] == "unknown" else ("+".join(r["needs"]) or "none") for r in out.values())
    doc = {
        "_source": "tools/reachability.py (COL2 des cellules wd*/g*.dat, voir reachability.md)",
        "thresholds_assumed": {k: getattr(a, k) for k in ("cell", "walk_ny", "step", "jump1", "jump2", "gap1", "gap2",
                                                           "gap3", "glide", "margin", "radius",
                                                           "up_tol", "down_max")},
        "summary": {"total": len(out), "by_class": dict(by_class),
                    "by_kind_class_confidence": {f"{k}|{c}|{f}": n for (k, c, f), n in sorted(summ.items())}},
        "locations": dict(sorted(out.items())),
    }
    (a.out / "reachability.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc["summary"], indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["extract", "run"])
    ap.add_argument("--out", type=Path, default=RESEARCH)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cell", type=float, default=1.0, help="pas de la grille (m)")
    ap.add_argument("--walk-ny", type=float, default=0.6, help="|normale y| minimale d'un sol (0.6 ~ 53 deg)")
    ap.add_argument("--step", type=float, default=1.0, help="denivele marchable entre cases voisines (m)")
    ap.add_argument("--jump1", type=float, default=2.0, help="HYPOTHESE : montee max saut simple (m)")
    ap.add_argument("--jump2", type=float, default=4.0, help="HYPOTHESE : montee max double saut (m)")
    ap.add_argument("--gap1", type=float, default=4.0, help="HYPOTHESE : vide franchissable saut simple (m)")
    ap.add_argument("--gap2", type=float, default=6.0, help="HYPOTHESE : vide franchissable double saut (m)")
    ap.add_argument("--gap3", type=float, default=10.0, help="HYPOTHESE : vide double saut + esquive aerienne (m)")
    ap.add_argument("--glide", type=float, default=2.0, help="HYPOTHESE : m horizontaux par m de chute (vol plane Pod)")
    ap.add_argument("--radius", type=float, default=40.0, help="demi-cote de la fenetre locale (m)")
    ap.add_argument("--up-tol", type=float, default=0.6, help="sol accepte jusqu'a +x m au-dessus de l'objet")
    ap.add_argument("--margin", type=float, default=0.5, help="marge pour signaler un cas limite (m)")
    ap.add_argument("--down-max", type=float, default=6.0, help="sol cherche jusqu'a x m sous l'objet")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "extract":
        cmd_extract(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
