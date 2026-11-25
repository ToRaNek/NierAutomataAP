"""Pieges recus via Archipelago."""
from __future__ import annotations

import math


def damage_after_trap(hp: int, max_hp: int, percent: int, lethal: bool = False) -> int:
    """PV apres un piege de degats (% des PV max). Sans l'option lethal_traps un piege ne tue jamais (1 PV)."""
    return max(0 if lethal else 1, hp - math.ceil(max_hp * percent / 100))


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


# actions du joueur pendant lesquelles on ne declenche rien (autodestruction en cours, etats speciaux)
_BUSY_ACTIONS = {0x37, 0x38, 0x39, 0x41, 0x46, 0xC7, 0xAC, 0xAD}


FLYING_ACTION = 0x84     # unite de vol : le jeu annule l'autodestruction aussitot (verifie en jeu)
HACKING_ACTION = 0x42    # mini-jeu de piratage de 9S : meme annulation (verifie en jeu)


def effect_allowed(world_loaded: bool, menu_closed: bool, action: int, hp: int, kind: str = "") -> bool:
    """Peut-on lancer un effet du jeu sur le joueur maintenant ? Sinon le client reessaie au tour suivant."""
    if kind == "selfdestruct" and action in (FLYING_ACTION, HACKING_ACTION):
        return False
    return bool(world_loaded and menu_closed and action not in _BUSY_ACTIONS and hp > 1)
