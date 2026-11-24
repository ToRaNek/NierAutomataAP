"""Un tour de boucle du client, sans dependance a Archipelago."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data import worlddb as db
from ..data.items_data import MATERIALS, SUPPLY_DROPS
from ..data.phases import is_prologue
from ..data.tables import (access_point_location, chest_location, item_location, level_location,
                           location_name_to_id, pickup_location, quest_location, story_location, weapon_location)
from ..data.weapons import STARTING_WEAPONS, WEAPONS
from .state import ClientState
from .trackers import ChestTracker, ItemTracker, LevelTracker, StoryTracker, WeaponTracker

_LOCS = location_name_to_id()
_WEAPON_NAME_BY_ID = {v: k for k, v in WEAPONS.items()}
_MATERIAL_LOC_BY_ID = {v: _LOCS[item_location(k)] for k, v in MATERIALS.items()}

GOAL_STORY, GOAL_ENDING_A = db.GOAL_STORY, db.GOAL_ENDING_A


@dataclass
class Trackers:
    story: StoryTracker
    weapons: WeaponTracker
    items: ItemTracker
    chests: ChestTracker
    levels: LevelTracker
    scope: db.Scope


@dataclass
class TickResult:
    locations: list[int] = field(default_factory=list)
    goal: bool = False
    refused: bool = False


def new_state(seed: str, slot: int) -> ClientState:
    """Etat neuf : les armes de depart de 2B ne doivent jamais compter comme trouvees."""
    return ClientState(seed=seed, slot=slot, save_slot=None,
                       ap_weapons={WEAPONS[n] for n in STARTING_WEAPONS})


def due_locations(state: ClientState, scope: db.Scope) -> set[int]:
    """Locations meritees d'apres l'etat (renvoyees tant que le serveur ne les a pas confirmees)."""
    due = {_LOCS[story_location(i)] for i in state.chapters if i < scope.chapters}
    due |= {_LOCS[weapon_location(i)] for i in range(1, min(state.weapons_found, scope.weapon_checks) + 1)}
    if scope.item_checks:
        due |= {_MATERIAL_LOC_BY_ID[i] for i in state.items_found if i in _MATERIAL_LOC_BY_ID}
    due |= {_LOCS[chest_location(i)] for i in state.chests_opened & scope.chests}
    due |= {_LOCS[pickup_location(i)] for i in state.ap_spots_collected & scope.pickups}
    due |= {_LOCS[access_point_location(i)] for i in state.access_points & scope.access_points}
    due |= {_LOCS[quest_location(i)] for i in state.quests_done & scope.quests}
    due |= {_LOCS[level_location(n)] for n in range(2, min(state.max_level, scope.max_level) + 1)}
    return due


def is_fresh(state: ClientState) -> bool:
    return (not state.linked and state.next_item_index == 0 and state.weapons_found == 0
            and not state.chapters)


def looks_like_new_game(game) -> bool:
    starting = {WEAPONS[n] for n in STARTING_WEAPONS}
    return game.owned_weapons() <= starting or is_prologue(game.phase())


def goal_reached(state: ClientState, phase: str, scope: db.Scope, endings=frozenset()) -> bool:
    if scope.goal == db.GOAL_STORY:
        return (scope.chapters - 1) in state.chapters
    if db.GOAL_STATES.get(scope.goal, set()) & set(endings):
        return True
    if phase and phase.startswith(db.GOAL_PHASES[scope.goal]):
        return True
    # la route suivante a commence : la fin precedente a forcement ete vue
    return (scope.goal == db.GOAL_ENDING_A and state.route in ("B", "C")) or \
           (scope.goal == db.GOAL_ENDING_B and state.route == "C")


def make_trackers(state: ClientState, scope: db.Scope) -> Trackers:
    enabled = set(MATERIALS.values()) if scope.item_checks else set()
    return Trackers(StoryTracker(state, scope.chapters), WeaponTracker(state, scope.weapon_checks),
                    ItemTracker(state, enabled), ChestTracker(state, scope.chests), LevelTracker(state), scope)


def tick(game, state: ClientState, received: list[str], trackers: Trackers) -> TickResult:
    """game : in_game(), phase(), owned_weapons(), give(name) -> bool, remove_weapon(id) -> bool, ..."""
    result = TickResult()
    scope = trackers.scope
    if not game.in_game():
        return result
    if is_fresh(state) and not looks_like_new_game(game):
        result.refused = True  # sauvegarde deja avancee : on ne touche a rien
        return result
    state.linked = True  # partie acceptee : liee a cette seed

    # 1. objets recus pas encore appliques
    while state.next_item_index < len(received):
        name = received[state.next_item_index]
        if not game.give(name):
            break  # inventaire plein : on reessaie au prochain tour
        if name in WEAPONS:
            state.ap_weapons.add(WEAPONS[name])
        state.next_item_index += 1

    # 2. reinjection des armes AP perdues (rechargement de save)
    owned = game.owned_weapons()
    for wid in sorted(state.ap_weapons - owned):
        name = _WEAPON_NAME_BY_ID.get(wid)
        if name:
            game.give(name)
    owned = game.owned_weapons()

    # 3. armes trouvees naturellement
    to_remove, _ = trackers.weapons.scan(owned)
    for wid in to_remove:
        game.remove_weapon(wid)

    # 4. premier ramassage d'objets
    trackers.items.scan(game.owned_items())

    # 5. progression de l'histoire
    phase = game.phase()
    trackers.story.check(phase, game.phase_id() if hasattr(game, "phase_id") else None)

    # 5 bis. ravitaillement a l'entree des passages durs (une fois)
    if getattr(scope, "supplies", False):
        reached = {db.CHAPTERS[i]["region"] for i in state.chapters}
        for region, names in SUPPLY_DROPS.items():
            if region in reached and region not in state.supplies_given:
                if all([game.give(n) for n in names]):
                    state.supplies_given.add(region)

    # 6. coffres
    if trackers.chests.enabled:
        pos = game.position()
        picked = getattr(game, "ground_pickup", lambda p: False)(pos)
        trackers.chests.update(game.chest_counter(), pos, ground_pickup=picked,
                               opened=getattr(game, "opened_chests", None))

    # 7. niveaux
    if scope.max_level and hasattr(game, "level"):
        trackers.levels.update(game.level())

    # 8. points d'acces actives, quetes terminees (lectures memoire fournies par le jeu)
    if scope.access_points and hasattr(game, "access_point_bits"):
        bits = game.access_point_bits()
        state.access_points.update(i for i in scope.access_points if db.ACCESS_POINTS[i]["bit"] in bits)
    if scope.quests and hasattr(game, "quests_done"):
        state.quests_done.update(i for i in game.quests_done() if i in scope.quests)

    due = due_locations(state, scope)
    result.locations = sorted(due - state.sent_locations)
    state.sent_locations.update(result.locations)
    endings = game.endings() if scope.goal != db.GOAL_STORY and hasattr(game, "endings") else frozenset()
    result.goal = goal_reached(state, phase, scope, endings)
    return result
