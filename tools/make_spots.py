"""Genere nier_automata/data/ap_spots.py a partir des releves de tools/spot_collector.py :
- spots_items.tsv : objets poses par le jeu (sur le chemin normal) ;
- spots_chests.tsv : position de 2B a l'ouverture d'un coffre ;
(+ path_log.tsv, ancien enregistreur de trajet, si present).
Les AP Items sont decales de 2 m pour ne pas recouvrir l'objet d'origine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.ap_items import pick_spots  # noqa: E402

HERE = Path(__file__).parent
OFFSET = 2.0


def read(name, cols):
    p = HERE / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) >= cols:
            out.append((f[1], float(f[2]) + OFFSET, float(f[3]), float(f[4])))
    return out


path = read("spots_chests.tsv", 5) + read("spots_items.tsv", 5) + read("path_log.tsv", 5)
spots = pick_spots(path, min_dist=25.0, per_area=6)
out = HERE.parent / "nier_automata" / "data" / "ap_spots.py"
body = "\n".join(f'    ("{c}", {x:.1f}, {y:.1f}, {z:.1f}),' for c, x, y, z in spots)
out.write_text('"""Emplacements des AP Items (genere par tools/make_spots.py depuis des releves en jeu)."""\n\n'
               f"AP_SPOTS: list[tuple[str, float, float, float]] = [\n{body}\n]\n", encoding="utf-8")
print(len(spots), "emplacements :", sorted({c for c, *_ in spots}))
