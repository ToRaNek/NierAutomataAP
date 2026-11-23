"""Detection des checks : armes trouvees (compteur) et phases d'histoire."""
from __future__ import annotations

from typing import Iterable, Optional

from ..data.phases import MENU_PHASES, phase_code
from ..data.weapons import WEAPONS
from .state import ClientState

KNOWN_WEAPON_IDS = frozenset(WEAPONS.values())


class WeaponTracker:
    def __init__(self, state: ClientState, max_found: int):
        self.state = state
        self.max_found = max_found
        self._pending: set[int] = set()

    def scan(self, owned_weapon_ids: set[int]) -> tuple[list[int], Optional[int]]:
        """Renvoie (armes a retirer, numero de "Weapon Found #n" nouvellement obtenu ou None).

        Seuls les IDs d'armes connus comptent, et une arme doit etre vue deux scans de suite
        (evite les valeurs passageres pendant un chargement). Une arme traitee par appel.
        """
        natural = (owned_weapon_ids & KNOWN_WEAPON_IDS) - self.state.ap_weapons
        confirmed = sorted(natural & self._pending)
        self._pending = natural
        if not confirmed:
            return [], None
        weapon = confirmed[0]
        self._pending.discard(weapon)
        if weapon in self.state.found_weapon_ids or self.state.weapons_found >= self.max_found:
            return [weapon], None
        self.state.found_weapon_ids.add(weapon)
        self.state.weapons_found += 1
        return [weapon], self.state.weapons_found


class PhaseTracker:
    def __init__(self, phases: list[tuple[str, str]], already_sent: Iterable[str] = ()):
        self.phases = phases
        self.sent = set(already_sent)

    def check(self, phase: str) -> list[str]:
        if not phase or phase in MENU_PHASES:
            return []
        hits = [name for name, prefix in self.phases
                if phase.startswith(prefix) and name not in self.sent]
        self.sent.update(hits)
        return hits

    def is_goal(self, phase: str) -> bool:
        return bool(phase) and phase.startswith(self.phases[-1][1])


class StoryTracker:
    """Chaque nouveau code de phase ("NN_XX") donne "Story Progress #n", jusqu'a max_count."""

    def __init__(self, state: ClientState, max_count: int):
        self.state = state
        self.max_count = max_count

    def check(self, phase: str) -> Optional[int]:
        code = phase_code(phase)
        if code is None or code in self.state.story_codes:
            return None
        self.state.story_codes.add(code)
        n = len(self.state.story_codes)
        return n if n <= self.max_count else None


class ItemTracker:
    """Premier ramassage de chaque objet active. Reference = deux lectures identiques (pas de check) ;
    un objet doit ensuite etre vu deux scans de suite pour compter (valeurs passageres)."""

    def __init__(self, state: ClientState, enabled_ids: set[int]):
        self.state = state
        self.enabled_ids = enabled_ids
        self._prev: Optional[set[int]] = None

    def scan(self, owned_item_ids: set[int]) -> list[int]:
        owned = owned_item_ids & self.enabled_ids
        prev, self._prev = self._prev, owned
        if self.state.item_baseline is None:
            if prev is not None and prev == owned:
                self.state.item_baseline = set(owned)
            return []
        if prev is None:
            return []
        new = sorted((owned & prev) - self.state.item_baseline - self.state.items_found)
        self.state.items_found.update(new)
        return new


CHEST_SPOT_RADIUS = 4.0


class ChestTracker:
    """Compteur de coffres du jeu : chaque hausse confirmee (2 lectures) = un coffre.
    Un coffre est identifie par (code de phase, x, z) pour ne pas recompter apres un rechargement."""

    def __init__(self, state: ClientState, max_count: int):
        self.state = state
        self.max_count = max_count
        self._last: Optional[int] = None
        self._prev: Optional[int] = None

    def _known(self, code: str, pos) -> bool:
        x, _, z = pos
        return any(c == code and abs(x - sx) <= CHEST_SPOT_RADIUS and abs(z - sz) <= CHEST_SPOT_RADIUS
                   for c, sx, sz in self.state.chest_spots)

    def update(self, counter: int, code: Optional[str], pos) -> Optional[int]:
        prev, self._prev = self._prev, counter
        if prev != counter:
            return None  # attendre une 2e lecture identique
        if self._last is None or counter < self._last:
            self._last = counter  # baseline ou rechargement
            return None
        if counter == self._last:
            return None
        self._last = counter
        if code is None or self._known(code, pos):
            return None
        self.state.chest_spots.append((code, pos[0], pos[2]))
        if self.state.chests_found >= self.max_count:
            return None
        self.state.chests_found += 1
        return self.state.chests_found


MAX_LEVEL = 99


class LevelTracker:
    """Niveau max atteint (2 lectures identiques, valeurs 1..99 seulement, ne baisse jamais)."""

    def __init__(self, state: ClientState):
        self.state = state
        self._prev: Optional[int] = None

    def update(self, level: Optional[int]) -> None:
        prev, self._prev = self._prev, level
        if level is None or level != prev or not 1 <= level <= MAX_LEVEL:
            return
        self.state.max_level = max(self.state.max_level, level)
