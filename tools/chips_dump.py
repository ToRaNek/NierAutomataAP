"""Liste les puces du joueur et les ajoute au catalogue nier_automata/data/chip_catalog.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nier_automata.data.offsets import OFFSETS, detect_version  # noqa: E402
from nier_automata.game.chips import ChipTable  # noqa: E402
from nier_automata.game.memory import ProcessMemory  # noqa: E402

CATALOG = Path(__file__).resolve().parent.parent / "nier_automata" / "data" / "chip_catalog.json"


def main():
    mem = ProcessMemory.attach()
    if mem is None or detect_version(mem.exe_path) != "v1.04":
        sys.exit("Jeu v1.04 non lance.")
    chips = ChipTable(mem, OFFSETS["v1.04"]["chipTableStart"]).read_all()
    cat = json.loads(CATALOG.read_text()) if CATALOG.exists() else {}
    for c in chips:
        print(f"slot {c.index:3}  id={c.chip_id}  type={c.type_index}  niv=+{c.level}  cout={c.cost}"
              + ("  [OS]" if c.is_os else ""))
        cat[str(c.chip_id)] = {"type": c.type_index, "level": c.level, "cost": c.cost,
                               "os": c.is_os, "raw": c.raw.hex()}
    CATALOG.write_text(json.dumps(cat, indent=1, sort_keys=True))
    print(f"{len(chips)} puces, catalogue : {len(cat)} entrees")


if __name__ == "__main__":
    main()
