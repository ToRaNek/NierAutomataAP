"""Zippe nier_automata/ en dist/nier_automata.apworld."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "nier_automata"
OUT = ROOT / "dist" / "nier_automata.apworld"

OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(SRC.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            z.write(f, Path("nier_automata") / f.relative_to(SRC))
print(OUT)
