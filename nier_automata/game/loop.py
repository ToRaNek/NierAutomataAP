"""Un tour de boucle du client, sans dependance a Archipelago."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data.items_data import MATERIALS
from ..data.tables import item_location, location_name_to_id, story_location, weapon_location
from ..data.weapons import STARTING_WEAPONS, WEAPONS
from .state import ClientState
from .trackers import ItemTracker, StoryTracker, WeaponTracker

_LOCS = location_name_to_id()
_WEAPON_NAME_BY_ID = {v: k for k, v in WEAPONS.items()}
_MATERIAL_LOC_BY_ID = {v: _LOCS[item_location(k)] for k, v in MATERIALS.items()}


@dataclass
class Trackers:
    story: StoryTracker
    weapons: WeaponTracker
    items: ItemTracker


@dataclass
class TickResult:
    locations: list[int] = field(default_factory=list)
    goal: bool = False
    refused: bool = False


def new_state(seed: str, slot: int) -> ClientState:
    """Etat neuf : les armes de depart de 2B ne doivent jamais compter comme trouvees."""
    return ClientState(seed=seed, slot=slot, save_slot=None,
                       ap_weapons={WEAPONS[n] for n in STARTING_WEAPONS})


def due_locations(state: ClientState, story_checks: int, weapon_checks: int) -> set[int]:
    """Locations meritees d'apres l'etat (renvoyees tant que le serveur ne les a pas confirmees)."""
    due = {_LOCS[story_location(i)] for i in range(1, min(len(state.story_codes), story_checks) + 1)}
    due |= {_LOCS[weapon_location(i)] for i in range(1, min(state.weapons_found, weapon_checks) + 1)}
    due |= {_MATERIAL_LOC_BY_ID[i] for i in state.items_found if i in _MATERIAL_LOC_BY_ID}
    return due


def is_fresh(state: ClientState) -> bool:
    return state.next_item_index == 0 and state.weapons_found == 0 and not state.story_codes


def looks_like_new_game(game) -> bool:
    starting = {WEAPONS[n] for n in STARTING_WEAPONS}
    return game.owned_weapons() <= starting and game.phase().startswith("00_")


def make_trackers(state: ClientState, story_checks: int, weapon_checks: int,
                  item_checks: bool = True) -> Trackers:
    enabled = set(MATERIALS.values()) if item_checks else set()
    return Trackers(StoryTracker(state, story_checks), WeaponTracker(state, weapon_checks),
                    ItemTracker(state, enabled))


def tick(game, state: ClientState, received: list[str], trackers: Trackers, goal_prefix: str) -> TickResult:
    """game : in_game(), phase(), owned_weapons(), give(name) -> bool, remove_weapon(id) -> bool."""
    result = TickResult()
    if not game.in_game():
        return result
    if is_fresh(state) and not looks_like_new_game(game):
        result.refused = True  # sauvegarde deja avancee : on ne touche a rien
        return result

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
    to_remove, n = trackers.weapons.scan(owned)
    for wid in to_remove:
        game.remove_weapon(wid)

    # 4. premier ramassage d'objets
    trackers.items.scan(game.owned_items())

    # 5. progression de l'histoire
    phase = game.phase()
    trackers.story.check(phase)

    due = due_locations(state, trackers.story.max_count, trackers.weapons.max_found)
    result.locations = sorted(due - state.sent_locations)
    state.sent_locations.update(result.locations)
    result.goal = bool(phase) and phase.startswith(goal_prefix)
    return result
