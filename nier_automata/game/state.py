"""Etat persistant du client, un fichier JSON par seed + slot AP."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def state_path(seed: str, slot: int) -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NierAutomataAP"
    # Le seed vient du serveur AP : ne garder que des caracteres surs.
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(seed))[:64] or "seed"
    return root / f"{safe}_{int(slot)}.json"


@dataclass
class ClientState:
    seed: str
    slot: int
    save_slot: Optional[int]
    next_item_index: int = 0
    sent_locations: set[int] = field(default_factory=set)
    weapons_found: int = 0
    ap_weapons: set[int] = field(default_factory=set)
    story_codes: set[str] = field(default_factory=set)
    found_weapon_ids: set[int] = field(default_factory=set)
    item_baseline: Optional[set[int]] = None
    items_found: set[int] = field(default_factory=set)
    chests_found: int = 0
    max_level: int = 1
    ap_spots_collected: set[int] = field(default_factory=set)
    ap_spawned_pid: int = 0
    ap_spawned_spots: set[int] = field(default_factory=set)
    ap_dynamic_spots: list = field(default_factory=list)  # [(code, x, y, z)] trouves en jouant
    chest_spots: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "slot": self.slot, "save_slot": self.save_slot,
            "next_item_index": self.next_item_index,
            "sent_locations": sorted(self.sent_locations),
            "weapons_found": self.weapons_found,
            "ap_weapons": sorted(self.ap_weapons),
            "story_codes": sorted(self.story_codes),
            "found_weapon_ids": sorted(self.found_weapon_ids),
            "item_baseline": None if self.item_baseline is None else sorted(self.item_baseline),
            "items_found": sorted(self.items_found),
            "chests_found": self.chests_found,
            "max_level": self.max_level,
            "ap_spots_collected": sorted(self.ap_spots_collected),
            "ap_spawned_pid": self.ap_spawned_pid,
            "ap_spawned_spots": sorted(self.ap_spawned_spots),
            "ap_dynamic_spots": [list(x) for x in self.ap_dynamic_spots],
            "chest_spots": [list(x) for x in self.chest_spots],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise

    @classmethod
    def load(cls, path: Path) -> Optional["ClientState"]:
        path = Path(path)
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(seed=d["seed"], slot=d["slot"], save_slot=d["save_slot"],
                   next_item_index=d["next_item_index"],
                   sent_locations=set(d["sent_locations"]),
                   weapons_found=d["weapons_found"], ap_weapons=set(d["ap_weapons"]),
                   story_codes=set(d.get("story_codes", [])),
                   found_weapon_ids=set(d.get("found_weapon_ids", [])),
                   item_baseline=None if d.get("item_baseline") is None else set(d["item_baseline"]),
                   items_found=set(d.get("items_found", [])),
                   chests_found=d.get("chests_found", 0),
                   max_level=d.get("max_level", 1),
                   ap_spots_collected=set(d.get("ap_spots_collected", [])),
                   ap_spawned_pid=d.get("ap_spawned_pid", 0),
                   ap_spawned_spots=set(d.get("ap_spawned_spots", [])),
                   ap_dynamic_spots=[(c, float(x), float(y), float(z)) for c, x, y, z in d.get("ap_dynamic_spots", [])],
                   chest_spots=[tuple(x) for x in d.get("chest_spots", [])])
