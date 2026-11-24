"""Base de donnees du monde (world_data.json, produite par tools/build_world_data.py).

Chapitres de toutes les routes (A, B, C/D), coffres nommes par lieu, emplacements des AP Items (points de
collecte du jeu), points d'acces, quetes. Chaque entree a une region logique ("A02", "B05", "C13"...).
Sans dependance a Archipelago : utilise par la generation ET par le client.
"""
from __future__ import annotations

import json
import math
import pkgutil
from typing import Optional

_DB = json.loads(pkgutil.get_data(__name__.rsplit(".", 1)[0], "world_data.json").decode("utf-8"))

REGIONS: list[str] = _DB["regions"]
REGION_LEVEL: dict[str, int] = _DB["region_level"]
CHAPTERS: list[dict] = _DB["chapters"]
CHESTS: list[dict] = _DB["chests"]
PICKUPS: list[dict] = _DB["pickups"]
ACCESS_POINTS: list[dict] = _DB["access_points"]
QUESTS: list[dict] = _DB["quests"]

GOAL_STORY, GOAL_ENDING_A, GOAL_ENDING_B, GOAL_ENDING_CD, GOAL_ENDING_E = 0, 1, 2, 3, 4
_ROUTE_ORDER = {"A": 0, "B": 1, "C": 2}
# phases qui prouvent une fin (generiques / retour au titre), par objectif
GOAL_PHASES = {
    GOAL_ENDING_A: ("EndRoll_A", "BackTitle_A"),
    GOAL_ENDING_B: ("BackTitle_B",),
    GOAL_ENDING_CD: ("EndRoll_CD", "BackTitle_CD", "BackTitle_True", "360_CD_TrueEnd"),
    GOAL_ENDING_E: ("360_CD_TrueEnd", "BackTitle_True", "BackTitle_FIN"),
}

_SUB: dict[str, list[int]] = {}
for _i, _c in enumerate(CHAPTERS):
    for _s in _c["subphases"]:
        _SUB.setdefault(_s, []).append(_i)


def chapter_count(goal: int, story_checks: int) -> int:
    """Nombre de chapitres (dans l'ordre A, B, C/D) couverts par l'objectif."""
    if goal == GOAL_STORY:
        return max(1, min(story_checks, len(CHAPTERS)))
    last = {GOAL_ENDING_A: "A", GOAL_ENDING_B: "B"}.get(goal, "C")
    return sum(1 for c in CHAPTERS if _ROUTE_ORDER[c["route"]] <= _ROUTE_ORDER[last])


def regions_in_scope(chapters: int) -> list[str]:
    """Regions entamees par les `chapters` premiers chapitres (ordre de REGIONS)."""
    started = {c["region"] for c in CHAPTERS[:chapters]}
    return [r for r in REGIONS if r in started]


def _candidates(subphase: str) -> list[int]:
    if subphase in _SUB:
        return _SUB[subphase]
    best: list[int] = []
    best_len = 0
    for name, idx in _SUB.items():       # variante de sous-phase : plus long prefixe commun
        n = len(name) if subphase.startswith(name) else (len(subphase) if name.startswith(subphase) else 0)
        if n > best_len and n >= 8:
            best, best_len = idx, n
    return best


def _phase_of(i: int, subphase: str):
    c = CHAPTERS[i]
    return c["phase_ids"][c["subphases"].index(subphase)] if subphase in c["subphases"] else None


def match_chapter(subphase: str, route: str, phase_id: Optional[int] = None) -> Optional[int]:
    """Indice du chapitre de `subphase` pour la route en cours (les sous-phases "_AB_" sont partagees).
    phase_id (0x100 = p100...) departage un meme nom de sous-phase present dans deux chapitres."""
    cands = _candidates(subphase) if subphase else []
    if not cands:
        return None
    if phase_id is not None:
        exact = [i for i in cands if _phase_of(i, subphase) == phase_id]
        cands = exact or cands
    same = [i for i in cands if CHAPTERS[i]["route"] == route]
    if same:
        return same[0]
    below = [i for i in cands if _ROUTE_ORDER[CHAPTERS[i]["route"]] <= _ROUTE_ORDER.get(route, 0)]
    return (below or cands)[-1]


def next_route(route: str, subphase: str) -> str:
    """Route apres avoir vu `subphase` : on n'avance que si elle n'existe que dans une route plus tardive."""
    routes = {CHAPTERS[i]["route"] for i in (_candidates(subphase) if subphase else [])}
    if len(routes) == 1:
        r = next(iter(routes))
        if _ROUTE_ORDER[r] > _ROUTE_ORDER.get(route, 0):
            return r
    return route


def nearest(points: list[dict], pos, opened: set, radius: float = 8.0, dy: float = 6.0) -> Optional[int]:
    """Indice du point (coffre...) non encore valide le plus proche de `pos`, ou None."""
    best, best_d = None, radius
    for i, p in enumerate(points):
        if i in opened:
            continue
        x, y, z = p["pos"]
        if abs(pos[1] - y) > dy:
            continue
        d = math.hypot(pos[0] - x, pos[2] - z)
        if d <= best_d:
            best, best_d = i, d
    return best


def level_region(level: int) -> str:
    """Premiere region dont le niveau conseille atteint `level`."""
    for r in REGIONS:
        if REGION_LEVEL[r] >= level:
            return r
    return REGIONS[-1]


def required_weapons(region_index: int, region_count: int, pool_weapons: int) -> int:
    """Armes attendues pour entrer dans la region n (logique de combat) : croissance reguliere jusqu'a
    75 % des armes du pool a la derniere region, et jamais plus de 2 armes de plus par region (les premieres
    regions ont peu d'emplacements : une marche trop haute rend la generation impossible)."""
    if region_count <= 1 or pool_weapons <= 0:
        return 0
    return min(int(0.75 * pool_weapons * region_index / (region_count - 1)), 2 * region_index)


def selected_pickups(per_area: int, regions: list[str]) -> list[int]:
    """Indices des emplacements d'AP Items retenus : `per_area` premiers de chaque zone, dans le perimetre."""
    return [i for i, p in enumerate(PICKUPS) if p["k"] <= per_area and p["region"] in regions]


class Scope:
    """Ce que couvre une partie (selon l'objectif et les options). Calcule de la meme facon par la generation
    et par le client."""

    def __init__(self, goal, chapters, regions, chests, pickups, access_points, quests, weapon_checks,
                 max_level, item_checks):
        self.goal: int = goal
        self.chapters: int = chapters
        self.regions: tuple = regions
        self.chests: frozenset = chests
        self.pickups: frozenset = pickups
        self.access_points: frozenset = access_points
        self.quests: frozenset = quests
        self.weapon_checks: int = weapon_checks
        self.max_level: int = max_level
        self.item_checks: bool = item_checks


def make_scope(goal: int, story_checks: int, chest_checks: bool, ap_items_per_area: int,
               access_point_checks: bool, quest_checks: bool, weapon_checks: int, max_level_check: int,
               item_checks: bool) -> Scope:
    n = chapter_count(goal, story_checks)
    regions = regions_in_scope(n)
    rs = set(regions)
    top = max(REGION_LEVEL[r] for r in regions)
    return Scope(
        goal=goal, chapters=n, regions=tuple(regions),
        chests=frozenset(i for i, c in enumerate(CHESTS) if c["region"] in rs) if chest_checks else frozenset(),
        pickups=frozenset(selected_pickups(ap_items_per_area, regions)) if ap_items_per_area else frozenset(),
        access_points=frozenset(i for i, a in enumerate(ACCESS_POINTS) if a["region"] in rs)
        if access_point_checks else frozenset(),
        quests=frozenset(i for i, q in enumerate(QUESTS) if q["region"] in rs) if quest_checks else frozenset(),
        weapon_checks=weapon_checks,
        max_level=min(max_level_check, top) if max_level_check else 0,   # pas de niveau au-dela du conseille
        item_checks=item_checks,
    )


def scope_from_slot_data(sd: dict) -> Scope:
    return make_scope(int(sd.get("goal", GOAL_STORY)), int(sd.get("story_checks", 12)),
                      bool(sd.get("chest_checks", False)), int(sd.get("ap_items_per_area", 0)),
                      bool(sd.get("access_point_checks", False)), bool(sd.get("quest_checks", False)),
                      int(sd.get("weapon_checks", 0)), int(sd.get("max_level_check", 0)),
                      bool(sd.get("item_checks", False)))


QUEST_STATUS_RVA = 0x14946D0     # i32 par quete (docs/research/runtime_state.md)
QUEST_STATUS_COUNT = max((q["status_index"] for q in QUESTS), default=-1) + 1
_QUEST_DONE = (2, 3, 4)          # DONE, END, FIN ; 1 = CLR (objectif atteint, pas encore rendue)


def quests_done(status: list[int]) -> set[int]:
    """Indices (QUESTS) des quetes terminees d'apres le tableau de statuts du jeu."""
    return {i for i, q in enumerate(QUESTS)
            if q["status_index"] < len(status) and status[q["status_index"]] in _QUEST_DONE}


_POSITIONS = {e["name"]: tuple(e["pos"]) for table in (CHESTS, PICKUPS, ACCESS_POINTS) for e in table}


def location_position(name: str):
    """Position monde (x, y, z) d'un check qui a un lieu precis, sinon None."""
    return _POSITIONS.get(name)


# etats de scene poses par le jeu quand une fin est obtenue (docs/research/endings_triggers.json)
GOAL_STATES = {
    GOAL_ENDING_A: {"ending_A"},
    GOAL_ENDING_B: {"ending_B"},
    GOAL_ENDING_CD: {"ending_C", "ending_D", "ending_CD"},
}
ENDING_STATES = ("ending_A", "ending_B", "ending_C", "ending_D", "ending_CD")
