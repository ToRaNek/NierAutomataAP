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

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "slot": self.slot, "save_slot": self.save_slot,
            "next_item_index": self.next_item_index,
            "sent_locations": sorted(self.sent_locations),
            "weapons_found": self.weapons_found,
            "ap_weapons": sorted(self.ap_weapons),
            "story_codes": sorted(self.story_codes),
            "found_weapon_ids": sorted(self.found_weapon_ids),
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
                   found_weapon_ids=set(d.get("found_weapon_ids", [])))
