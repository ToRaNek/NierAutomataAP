"""Mur invisible des zones verrouillees : tant que le Pass d'une zone n'est pas recu, le joueur qui y entre
est remis a sa derniere position autorisee. Logique pure (pas d'acces memoire)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..data.areas import pass_for_area
from ..data.phases import MENU_PHASES, is_prologue

BACK_DISTANCE = 8.0      # on revient a la derniere position situee a 8 m au moins de l'endroit du refus
KEEP_SECONDS = 15.0
WALL_RADIUS = 0.5        # mur garde : refus si le joueur revient a moins de la moitie du chemin ancre -> refus
WALL_FORGET = 60.0       # mur oublie quand le joueur s'eloigne (le jeu resignalera la zone a son retour)
MAX_DISTANCE = 120.0     # jamais de retour plus loin (position d'une autre carte : chargement, voyage rapide)
MESSAGE_EVERY = 12.0


# actions du joueur pendant lesquelles on ne le deplace jamais : vol, piratage, mort
_NO_PUSHBACK_ACTIONS = {0x84, 0x42, 0xAF, 0x2C, 0x35, 0x36}


def area_lock_active(phase: str, cutscene: bool, action, hp) -> bool:
    """Le mur de zone n'agit que quand le joueur a la main : jamais pendant le prologue (il se passe dans l'usine),
    une phase de vaisseau, une cinematique, un vol, un piratage ou la mort."""
    if not phase or phase in MENU_PHASES or is_prologue(phase) or "STG" in phase or cutscene:
        return False
    return action is not None and action not in _NO_PUSHBACK_ACTIONS and bool(hp)


@dataclass
class Pushback:
    pos: tuple            # ou remettre le joueur
    area_id: int          # zone a reecrire (celle d'avant)
    pass_name: str        # objet manquant
    notify: bool          # afficher le message (pas a chaque fois)


class AreaLock:
    """Le jeu ne signale une zone qu'a l'ENTREE dans un de ses volumes. Apres un retour en arriere on garde donc
    notre propre mur : le point de retour (ancre) et l'endroit du refus restent en memoire, et s'en approcher de
    nouveau renvoie a la meme ancre meme si le jeu ne signale rien (vu en jeu : au 2e essai le joueur passait)."""

    def __init__(self, locked_passes):
        self.passes = set(locked_passes)      # Pass qui existent dans cette partie
        self._trail: list[tuple[float, tuple, int]] = []
        self._last_message = -1e9
        self._wall = None                     # (ancre, endroit du refus, Pass manquant, zone d'avant)
        self.blocked_without_trail = False

    def locked(self, area_id: int, owned) -> Optional[str]:
        name = pass_for_area(area_id)
        return name if name in self.passes and name not in owned else None

    def reset(self) -> None:
        """Chargement, saut de phase, voyage rapide : les anciennes positions ne valent plus rien."""
        self._trail.clear()
        self._wall = None

    def _push(self, now: float) -> Pushback:
        anchor, _, missing, area = self._wall
        notify = now - self._last_message >= MESSAGE_EVERY
        if notify:
            self._last_message = now
        self._trail = [(now, anchor, area)]
        return Pushback(anchor, area, missing, notify)

    def update(self, area_id: int, pos, now: float, owned, active: bool = True) -> Optional[Pushback]:
        """active = le joueur a la main (pas de cinematique, de vol, de prologue...)."""
        if pos is None or not active:
            return None
        pos = tuple(pos)
        if self._wall is not None:
            anchor, refused, name, _ = self._wall
            if name in owned or math.dist(pos, refused) > WALL_FORGET:
                self._wall = None
        missing = self.locked(area_id, owned)
        if missing is None:
            if self._wall is not None:
                anchor, refused, _, _ = self._wall
                if math.dist(pos, refused) <= WALL_RADIUS * math.dist(anchor, refused):
                    return self._push(now)       # revenu pres de l'endroit du refus : meme mur
            if self._trail and math.dist(self._trail[-1][1], pos) > 30.0:
                self._trail.clear()          # saut de position : teleportation du jeu
            self._trail.append((now, pos, area_id))
            self._trail = [t for t in self._trail if now - t[0] <= KEEP_SECONDS]
            self.blocked_without_trail = False
            return None
        if self._wall is not None and self._wall[2] == missing:
            return self._push(now)               # meme mur : toujours la meme ancre
        far = [t for t in self._trail if math.dist(t[1], pos) >= BACK_DISTANCE]
        target = far[-1] if far else (self._trail[0] if self._trail else None)
        if target is None or math.dist(target[1], pos) > MAX_DISTANCE:
            self.blocked_without_trail = True
            return None
        self._wall = (target[1], pos, missing, target[2])
        return self._push(now)
