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
    route: str = "A"                                          # route en cours : A, B ou C (C/D)
    chapters: set[int] = field(default_factory=set)           # indices des chapitres atteints (worlddb)
    found_weapon_ids: set[int] = field(default_factory=set)
    item_baseline: Optional[set[int]] = None
    items_found: set[int] = field(default_factory=set)
    chests_opened: set[int] = field(default_factory=set)      # indices de coffres (worlddb.CHESTS)
    access_points: set[int] = field(default_factory=set)      # indices de points d'acces actives
    quests_done: set[int] = field(default_factory=set)        # indices de quetes terminees
    max_level: int = 1
    ap_spots_collected: set[int] = field(default_factory=set)  # indices d'AP Items ramasses (worlddb.PICKUPS)
    ap_spawned_pid: int = 0
    ap_spawned_spots: set[int] = field(default_factory=set)
    linked: bool = False  # partie deja acceptee pour cette seed
    hints: list = field(default_factory=list)  # [(objet, pour qui, emplacement)] dans notre partie

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "slot": self.slot, "save_slot": self.save_slot,
            "next_item_index": self.next_item_index,
            "sent_locations": sorted(self.sent_locations),
            "weapons_found": self.weapons_found,
            "ap_weapons": sorted(self.ap_weapons),
            "route": self.route,
            "chapters": sorted(self.chapters),
            "found_weapon_ids": sorted(self.found_weapon_ids),
            "item_baseline": None if self.item_baseline is None else sorted(self.item_baseline),
            "items_found": sorted(self.items_found),
            "chests_opened": sorted(self.chests_opened),
            "access_points": sorted(self.access_points),
            "quests_done": sorted(self.quests_done),
            "max_level": self.max_level,
            "ap_spots_collected": sorted(self.ap_spots_collected),
            "ap_spawned_pid": self.ap_spawned_pid,
            "ap_spawned_spots": sorted(self.ap_spawned_spots),
            "linked": self.linked,
            "hints": [list(h) for h in self.hints],
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
                   route=d.get("route", "A"),
                   chapters=set(d.get("chapters", [])),
                   found_weapon_ids=set(d.get("found_weapon_ids", [])),
                   item_baseline=None if d.get("item_baseline") is None else set(d["item_baseline"]),
                   items_found=set(d.get("items_found", [])),
                   chests_opened=set(d.get("chests_opened", [])),
                   access_points=set(d.get("access_points", [])),
                   quests_done=set(d.get("quests_done", [])),
                   max_level=d.get("max_level", 1),
                   ap_spots_collected=set(d.get("ap_spots_collected", [])),
                   ap_spawned_pid=d.get("ap_spawned_pid", 0),
                   ap_spawned_spots=set(d.get("ap_spawned_spots", [])),
                   linked=bool(d.get("linked", False)),
                   hints=[tuple(h) for h in d.get("hints", [])])
