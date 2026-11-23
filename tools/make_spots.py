"""Genere nier_automata/data/ap_spots.py a partir de tools/path_log.tsv (trajet enregistre en jouant)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.ap_items import pick_spots
log = Path(__file__).with_name("path_log.tsv")
path = []
for line in log.read_text(encoding="utf-8").splitlines():
    t, ph, x, y, z = line.split("\t")
    path.append((ph, float(x), float(y), float(z)))
spots = pick_spots(path, min_dist=40.0, per_area=5)
out = Path(__file__).resolve().parent.parent / "nier_automata" / "data" / "ap_spots.py"
body = "\n".join(f'    ("{c}", {x:.1f}, {y:.1f}, {z:.1f}),' for c, x, y, z in spots)
out.write_text(f'"""Emplacements des AP Items (genere par tools/make_spots.py depuis un trajet reel)."""\n\n'
               f"AP_SPOTS: list[tuple[str, float, float, float]] = [\n{body}\n]\n", encoding="utf-8")
print(len(spots), "emplacements")
