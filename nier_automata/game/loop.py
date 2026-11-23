"""Un tour de boucle du client, sans dependance a Archipelago."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data.tables import location_name_to_id, story_location, weapon_location
from ..data.weapons import STARTING_WEAPONS, WEAPONS
from .state import ClientState
from .trackers import StoryTracker, WeaponTracker

_LOCS = location_name_to_id()
_WEAPON_NAME_BY_ID = {v: k for k, v in WEAPONS.items()}


@dataclass
class Trackers:
    story: StoryTracker
    weapons: WeaponTracker


@dataclass
class TickResult:
    locations: list[int] = field(default_factory=list)
    goal: bool = False


def new_state(seed: str, slot: int) -> ClientState:
    """Etat neuf : les armes de depart de 2B ne doivent jamais compter comme trouvees."""
    return ClientState(seed=seed, slot=slot, save_slot=None,
                       ap_weapons={WEAPONS[n] for n in STARTING_WEAPONS})


def make_trackers(state: ClientState, story_checks: int, weapon_checks: int) -> Trackers:
    return Trackers(StoryTracker(state, story_checks), WeaponTracker(state, weapon_checks))


def tick(game, state: ClientState, received: list[str], trackers: Trackers, goal_prefix: str) -> TickResult:
    """game : in_game(), phase(), owned_weapons(), give(name) -> bool, remove_weapon(id) -> bool."""
    result = TickResult()
    if not game.in_game():
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
    if n is not None:
        result.locations.append(_LOCS[weapon_location(n)])

    # 4. progression de l'histoire
    phase = game.phase()
    n = trackers.story.check(phase)
    if n is not None:
        result.locations.append(_LOCS[story_location(n)])

    result.locations = [loc for loc in result.locations if loc not in state.sent_locations]
    state.sent_locations.update(result.locations)
    result.goal = bool(phase) and phase.startswith(goal_prefix)
    return result
