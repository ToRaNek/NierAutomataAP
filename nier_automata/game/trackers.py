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
        if self.state.weapons_found >= self.max_found:
            return [weapon], None
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
