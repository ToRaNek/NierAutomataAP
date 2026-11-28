"""Detection des checks : armes trouvees (compteur) et phases d'histoire."""
from __future__ import annotations

import math
from typing import Iterable, Optional

from ..data import worlddb as db
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
        if weapon in self.state.found_weapon_ids:
            return [weapon], None          # deja changee en check : reprise (rachat, rechargement)
        if self.state.weapons_found >= self.max_found:
            return [], None                # plus de check d'arme a donner : le joueur garde l'arme
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
    """Un check par chapitre (toutes routes : A, puis B, puis C/D). La route en cours est memorisee : les
    sous-phases "_AB_" sont communes aux routes A et B. Atteindre un chapitre de la route en cours valide
    aussi tous les chapitres precedents (le client peut avoir manque une transition)."""

    def __init__(self, state: ClientState, max_count: int):
        self.state = state
        self.max_count = max_count

    def check(self, phase: str, phase_id: Optional[int] = None) -> Optional[int]:
        """Renvoie l'indice (0..) du chapitre nouvellement atteint s'il est dans le perimetre, sinon None."""
        self.state.route = db.next_route(self.state.route, phase)
        i = db.match_chapter(phase, self.state.route, phase_id)
        if i is None or i in self.state.chapters:
            return None
        if db.CHAPTERS[i]["route"] == self.state.route:
            self.state.chapters.update(range(i + 1))
        else:
            self.state.chapters.add(i)       # selection de chapitre vers une autre route
        return i if i < self.max_count else None


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


class ChestTracker:
    """Coffres ouverts. Le compteur du jeu augmente a chaque ouverture (et a chaque ramassage au sol, ecarte
    par `ground_pickup`) ; le coffre est celui de la base, non encore ouvert, le plus proche du joueur."""

    def __init__(self, state: ClientState, scope_chests):
        self.state = state
        self.scope = frozenset(scope_chests)
        self.enabled = bool(self.scope)
        self._last: Optional[int] = None
        self._prev: Optional[int] = None

    def update(self, counter: int, pos, ground_pickup: bool = False, opened=None) -> Optional[int]:
        """Renvoie l'indice du coffre ouvert (worlddb.CHESTS) s'il est dans le perimetre, sinon None.
        opened : fonction donnant les positions des objets coffre ouverts en memoire (plus sur que la
        position du joueur quand deux coffres sont proches)."""
        prev, self._prev = self._prev, counter
        if prev != counter:
            return None  # attendre une 2e lecture identique
        if self._last is None or counter < self._last:
            self._last = counter  # reference ou rechargement
            return None
        if counter == self._last:
            return None
        self._last = counter
        if ground_pickup or pos is None:
            return None
        i = None
        for q in sorted(opened() if opened else [], key=lambda q: math.dist(q, pos)):
            i = db.nearest(db.CHESTS, q, self.state.chests_opened, radius=2.0, dy=3.0)
            if i is not None:
                break
        if i is None:
            i = db.nearest(db.CHESTS, pos, self.state.chests_opened)
        if i is None:
            return None
        self.state.chests_opened.add(i)
        return i if i in self.scope else None


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
