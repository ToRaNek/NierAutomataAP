"""Pieges recus via Archipelago."""
from __future__ import annotations

import math


def damage_after_trap(hp: int, max_hp: int, percent: int) -> int:
    """PV apres un piege de degats (% des PV max). Un piege ne tue jamais : minimum 1 PV (ecrire 0 PV ne tue
    pas, le jeu remet 1 PV : verifie en jeu ; un piege mortel passe par NierGame.kill, voir trap_kills)."""
    return max(1, hp - math.ceil(max_hp * percent / 100))


def trap_kills(hp: int, max_hp: int, percent: int, lethal: bool) -> bool:
    """Avec l'option lethal_traps : le piege tue si ses degats atteignent les PV restants."""
    return bool(lethal and hp - math.ceil(max_hp * percent / 100) <= 0)


def damage_percent(factor: int, base_percent: int) -> int:
    """% des PV max retire par un piege de degats (factor 1 ou 2 x le reglage), plafonne a 90."""
    return max(1, min(90, factor * base_percent))


def funds_after_trap(funds: int, percent: int) -> int:
    return funds - funds * percent // 100


class Jams:
    """Pannes de systeme en cours : capacite -> instant de fin (horloge monotone)."""

    def __init__(self):
        self.until: dict[str, float] = {}

    def start(self, ability: str, seconds: float, now: float) -> None:
        self.until[ability] = max(self.until.get(ability, 0.0), now + seconds)

    def active(self, now: float) -> set:
        return {a for a, t in self.until.items() if t > now}


class CutsceneHold:
    """Retient les pieges pendant une cinematique, au plus `max_wait` secondes d'affilee."""

    def __init__(self, max_wait: float = 300.0):
        self.max_wait = max_wait
        self.since = None

    def hold(self, cutscene: bool, now: float) -> bool:
        if not cutscene:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        return now - self.since < self.max_wait


# actions du joueur pendant lesquelles on ne declenche rien (autodestruction en cours, etats speciaux)
_BUSY_ACTIONS = {0x37, 0x38, 0x39, 0x41, 0x46, 0xC7, 0xAC, 0xAD}


FLYING_ACTION = 0x84     # unite de vol : le jeu annule l'autodestruction aussitot (verifie en jeu)
HACKING_ACTION = 0x42    # mini-jeu de piratage de 9S : meme annulation (verifie en jeu)
HACK_START_ACTION = 0xAF  # animation de lancement / de sortie du piratage
_NO_SELF_DESTRUCT = (FLYING_ACTION, HACKING_ACTION, HACK_START_ACTION)


def self_destruct_clear(actions) -> bool:
    """Plusieurs lectures de l'action a la suite : aucune ne doit etre un etat de vol ou de piratage
    (pendant le piratage l'action retombe a 0 pendant ~0,1 s)."""
    return not any(a in _NO_SELF_DESTRUCT or a in _BUSY_ACTIONS for a in actions)


def effect_allowed(world_loaded: bool, menu_closed: bool, action: int, hp: int, kind: str = "",
                   cutscene: bool = False) -> bool:
    """Peut-on lancer un effet du jeu sur le joueur maintenant ? Sinon le client reessaie au tour suivant."""
    if cutscene:
        return False
    if kind == "selfdestruct" and action in _NO_SELF_DESTRUCT:
        return False
    return bool(world_loaded and menu_closed and action not in _BUSY_ACTIONS and hp > 1)


TRAIL_KEEP = 90.0            # secondes de positions gardees pour le piege "Teleport"
TELEPORT_MAX = 150.0         # jamais de retour plus loin (autre carte, chargement)


class Trail:
    """Positions recentes du joueur. Le piege "Teleport" le ramene la ou il etait il y a `seconds` secondes."""

    def __init__(self):
        self._points: list = []

    def add(self, pos, now: float) -> None:
        if pos is None:
            return
        if self._points and _dist(self._points[-1][1], pos) > TELEPORT_MAX:
            self._points.clear()                 # saut de position : chargement, voyage rapide
        self._points.append((now, tuple(pos)))
        self._points = [p for p in self._points if now - p[0] <= TRAIL_KEEP]

    def back(self, pos, now: float, seconds: float):
        """Position d'il y a au moins `seconds` secondes (la plus recente), sinon la plus ancienne connue.
        None s'il n'y a rien d'utilisable ou si c'est trop loin."""
        if not self._points or pos is None:
            return None
        older = [p for p in self._points if now - p[0] >= seconds]
        target = (older[-1] if older else self._points[0])[1]
        return target if _dist(target, pos) <= TELEPORT_MAX else None


def _dist(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
