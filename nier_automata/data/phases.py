"""Phases d'histoire. Noms internes non documentes : on compte les codes de phase distincts."""
from __future__ import annotations

from typing import Optional

MENU_PHASES = {"SIGNIN", "START"}
# Provisoire (AutomataSpeedrunMod) : a confirmer avec tools/phases_seen.log en fin de route A.
GOAL_PHASE_PREFIX = "58_AB_BossArea_Fall"


def phase_code(phase: str) -> Optional[str]:
    if not phase or phase in MENU_PHASES:
        return None
    parts = phase.split("_")
    if len(parts) < 2:
        return None
    return "_".join(parts[:2])


def abilities_allowed(phase: str) -> bool:
    """Les capacites ne sont jamais bloquees pendant le prologue (codes "00_", tutoriels de controles :
    bloquer une action attendue coincerait le joueur) ni pendant les phases de vaisseau ("STG")."""
    if not phase or phase in MENU_PHASES:
        return False
    if phase.startswith("00_") or "STG" in phase:
        return False
    return True
