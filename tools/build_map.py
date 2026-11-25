"""Carte du monde vue de dessus (wd1) a partir des collisions decodees (cache de tools/reachability.py).
Ecrit nier_automata/data/map.png et map.json (echelle et origine : pixel = (x - x0) / scale, (z - z0) / scale)."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reachability as R  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "nier_automata" / "data"
SCALE = 2.0      # metres par pixel
manifest = json.loads((R.CACHE / "manifest.json").read_text())
tiles = [n for n, e in manifest.items() if n.startswith("wd1/") and e.get("col") and e["col"]["tris"]
         and e["col"]["names"] != ["test"]]
allt = []
for n in tiles:
    with np.load(R.CACHE / f"{n.replace('/', '__')[:-4]}.npz") as z:
        t = z["tris"].astype(np.float32)
    cx, cz = R.tile_offset(n)
    t[:, :, 0] += cx
    t[:, :, 2] += cz
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    keep = (ln > 1e-6) & (np.abs(nrm[:, 1]) / np.maximum(ln, 1e-6) > 0.5)     # sols seulement
    allt.append(t[keep])
t = np.concatenate(allt)
t = t[(t[:, :, 1].max(axis=1) < 95)]          # plafonds techniques a y = 100
x0, z0 = float(t[:, :, 0].min()) - 20, float(t[:, :, 2].min()) - 20
x1, z1 = float(t[:, :, 0].max()) + 20, float(t[:, :, 2].max()) + 20
w, h = int((x1 - x0) / SCALE), int((z1 - z0) / SCALE)
img = Image.new("RGB", (w, h), (10, 14, 22))
d = ImageDraw.Draw(img)
ymax = t[:, :, 1].max(axis=1)
lo, hi = np.percentile(ymax, 2), np.percentile(ymax, 98)
for i in np.argsort(ymax):
    v = float(np.clip((ymax[i] - lo) / (hi - lo), 0, 1))
    c = (int(40 + 120 * v), int(60 + 120 * v), int(70 + 90 * v))
    d.polygon([((p[0] - x0) / SCALE, (p[2] - z0) / SCALE) for p in t[i]], fill=c)
img = img.filter(ImageFilter.SMOOTH)

# Interieurs (wd5, deja en coordonnees monde) : sols en orange translucide par-dessus le monde ouvert, pour que
# les checks de grotte / sous-sol / salle ne paraissent pas poses en plein air. g50010 = un grand plan, ignore.
INTERIOR = (255, 150, 60, 130)
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
n_int = 0
for n, e in sorted(manifest.items()):
    if not (n.startswith("wd5/") and e.get("col") and e["col"]["tris"]) or e["col"]["names"] == ["test"]             or n == "wd5/g50010.dat":
        continue
    with np.load(R.CACHE / f"{n.replace('/', '__')[:-4]}.npz") as z:
        ti = z["tris"].astype(np.float32)
    nrm = np.cross(ti[:, 1] - ti[:, 0], ti[:, 2] - ti[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    ti = ti[(ln > 1e-6) & (np.abs(nrm[:, 1]) / np.maximum(ln, 1e-6) > 0.5)
            & (ti[:, :, 1].max(axis=1) < 300) & (ti[:, :, 1].min(axis=1) > -600)]
    n_int += len(ti)
    for tri in ti:
        od.polygon([((p[0] - x0) / SCALE, (p[2] - z0) / SCALE) for p in tri], fill=INTERIOR)
img.paste(ov, (0, 0), ov)
print(n_int, "triangles d'interieur")
img.save(OUT / "map.png", optimize=True)
(OUT / "map.json").write_text(json.dumps({"x0": x0, "z0": z0, "scale": SCALE, "width": w, "height": h}))
print(len(t), "triangles", w, "x", h, (OUT / "map.png").stat().st_size // 1024, "Ko")
