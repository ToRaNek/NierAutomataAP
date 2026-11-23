"""Tables noms <-> codes AP, sans dependance a Archipelago."""
from __future__ import annotations

from .abilities import ABILITY_PATCHES
from .items_data import FILLER_ITEMS, FUNDS_ITEMS, MATERIALS, TRAP_ITEMS
from .weapons import WEAPONS

BASE_CODE = 0x4E41_0000
MAX_STORY = 30
MAX_WEAPON_CHECKS = 30
MAX_CHEST_CHECKS = 60
GOAL_LOCATION = "Story: Ending A"


def story_location(n: int) -> str:
    return f"Story Progress #{n}"


def weapon_location(n: int) -> str:
    return f"Weapon Found #{n}"


def level_location(n: int) -> str:
    return f"Level {n}"


def chest_location(n: int) -> str:
    return f"Chest #{n}"


def item_location(name: str) -> str:
    return f"Item: {name}"


def item_name_to_id() -> dict[str, int]:
    ids: dict[str, int] = {}
    for i, name in enumerate(WEAPONS):
        ids[name] = BASE_CODE + 0x100 + i
    for i, name in enumerate(FILLER_ITEMS):
        ids[name] = BASE_CODE + 0x200 + i
    for i, name in enumerate(FUNDS_ITEMS):
        ids[name] = BASE_CODE + 0x280 + i
    for i, name in enumerate(TRAP_ITEMS):
        ids[name] = BASE_CODE + 0x300 + i
    for name, code in (("Double Jump", 0x400), ("Air Dash", 0x401), ("Evade", 0x402), ("Pod Fire", 0x403),
                       ("Light Attack", 0x404), ("Heavy Attack", 0x405), ("Pod Program", 0x406)):
        ids[name] = BASE_CODE + code
    ids["Ground Evade"] = BASE_CODE + 0x480
    return ids


def location_name_to_id() -> dict[str, int]:
    locs: dict[str, int] = {}
    for n in range(1, MAX_STORY + 1):
        locs[story_location(n)] = BASE_CODE + 0x1000 + n
    for n in range(1, MAX_WEAPON_CHECKS + 1):
        locs[weapon_location(n)] = BASE_CODE + 0x2000 + n
    for i, name in enumerate(MATERIALS):
        locs[item_location(name)] = BASE_CODE + 0x3000 + i
    for n in range(1, MAX_CHEST_CHECKS + 1):
        locs[chest_location(n)] = BASE_CODE + 0x4000 + n
    for n in range(2, 100):
        locs[level_location(n)] = BASE_CODE + 0x5000 + n
    return locs


def pool_weapon_count(story_locations: int, total_locations: int, candidates: int) -> int:
    """Armes (objets "useful") dans le pool : jamais plus que les locations non exclues (histoire),
    et au plus la moitie des locations. Le reste est du filler, seul autorise sur les exclues."""
    return max(0, min(candidates, story_locations, total_locations // 2))
