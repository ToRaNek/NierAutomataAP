"""Tables noms <-> codes AP, sans dependance a Archipelago."""
from __future__ import annotations

from .abilities import ABILITY_PATCHES
from .areas import AREA_PASSES
from .routes import ROUTE_KEYS
from .items_data import FILLER_ITEMS, FUNDS_ITEMS, MATERIALS, POD_PROGRAMS, TRAP_ITEMS
from .weapons import WEAPONS

BASE_CODE = 0x4E41_0000
from . import worlddb as db

MAX_STORY = len(db.CHAPTERS)
MAX_WEAPON_CHECKS = 30


def story_location(i: int) -> str:
    """Nom du check du chapitre d'indice i (0 = premier chapitre de la route A)."""
    return db.CHAPTERS[i]["name"]


def weapon_location(n: int) -> str:
    return f"Weapon Found #{n}"


def chest_location(i: int) -> str:
    return db.CHESTS[i]["name"]


def pickup_location(i: int) -> str:
    return db.PICKUPS[i]["name"]


def access_point_location(i: int) -> str:
    return db.ACCESS_POINTS[i]["name"]


def quest_location(i: int) -> str:
    return db.QUESTS[i]["name"]


# Magasins (ordre fixe : il determine les codes).
SHOP_PLACES_ORDER = ["Resistance Camp", "Pascal's Village", "Forest Castle"]
MAX_SHOP_SLOTS = 4


def shop_location(place: str, k: int) -> str:
    return f"Shop {place} #{k}"


def ending_location(letter: str) -> str:
    return f"Ending {letter}"


MAX_PROGRAM_CHECKS = 16


def program_location(n: int) -> str:
    return f"Pod Program Found #{n}"


def level_location(n: int) -> str:
    return f"Level {n}"


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
    for i, name in enumerate(POD_PROGRAMS):
        ids[name] = BASE_CODE + 0x500 + i
    for i, name in enumerate(AREA_PASSES):
        ids[name] = BASE_CODE + 0x600 + i
    for i, name in enumerate(ROUTE_KEYS.values()):
        ids[name] = BASE_CODE + 0x680 + i
    ids["B Chapter Key"], ids["C/D Chapter Key"] = BASE_CODE + 0x690, BASE_CODE + 0x691
    return ids


def location_name_to_id() -> dict[str, int]:
    locs: dict[str, int] = {}
    for n in range(1, MAX_WEAPON_CHECKS + 1):
        locs[weapon_location(n)] = BASE_CODE + 0x2000 + n
    for i, name in enumerate(MATERIALS):
        locs[item_location(name)] = BASE_CODE + 0x3000 + i
    for n in range(2, 100):
        locs[level_location(n)] = BASE_CODE + 0x5000 + n
    for i, place in enumerate(SHOP_PLACES_ORDER):
        for k in range(1, MAX_SHOP_SLOTS + 1):
            locs[shop_location(place, k)] = BASE_CODE + 0x7000 + i * 0x10 + k
    for base, table in ((0x8000, db.CHAPTERS), (0x9000, db.CHESTS), (0xA000, db.PICKUPS),
                        (0xB000, db.ACCESS_POINTS), (0xC000, db.QUESTS)):
        for i, entry in enumerate(table):
            locs[entry["name"]] = BASE_CODE + base + i
    for n in range(1, MAX_PROGRAM_CHECKS + 1):
        locs[program_location(n)] = BASE_CODE + 0xE000 + n
    for i, letter in enumerate("ABCD"):
        locs[ending_location(letter)] = BASE_CODE + 0xD000 + i
    return locs


SHOP_REGION = {"Resistance Camp": "A02", "Pascal's Village": "A05", "Forest Castle": "A06"}
# Le marchand de la foret n'existe qu'apres la quete annexe "Camp Development" (q122), qu'on peut rater :
# ses AP Items ne recoivent jamais d'objet important (verifie en jeu).
SHOP_MISSABLE = {"Forest Castle"}


def shop_missable(place: str, regions) -> bool:
    """Magasin qu'on peut perdre : la foret (quete ratable) ; le Village de Pascal quand la route C/D est jouee
    (a la fin du chapitre 14, tuer Pascal ferme son magasin jusqu'a la selection de chapitre)."""
    if place in SHOP_MISSABLE:
        return True
    return place == "Pascal's Village" and any(r.startswith("C") for r in regions)


def pool_weapon_count(story_locations: int, total_locations: int, candidates: int) -> int:
    """Armes (objets "useful") dans le pool : jamais plus que les locations non exclues (histoire),
    et au plus la moitie des locations. Le reste est du filler, seul autorise sur les exclues."""
    return max(0, min(candidates, story_locations, total_locations // 2))


def quest_excluded(quest: dict, regions) -> bool:
    """Une quete ne recoit jamais d'objet important si elle est ratable, ou des que la route C/D est jouee
    (les quetes des routes A/B n'y sont plus faisables)."""
    return bool(quest.get("excluded")) or any(r.startswith("C") for r in regions)
