"""Phases d'histoire. Noms internes non documentes : on compte les codes de phase distincts."""
from __future__ import annotations

from typing import Optional

MENU_PHASES = {"SIGNIN", "START"}
# Provisoire (AutomataSpeedrunMod) : a confirmer avec tools/phases_seen.log en fin de route A.


def phase_code(phase: str) -> Optional[str]:
    if not phase or phase in MENU_PHASES:
        return None
    parts = phase.split("_")
    if len(parts) < 2:
        return None
    return "_".join(parts[:2])


def is_prologue(phase: str) -> bool:
    """Prologue (usine) : codes "00_" mais aussi "05_..." (vu en jeu : 05_00_A_RobotM_Pro_ArmBoss_2nd).
    Toutes ses phases contiennent "RobotM_Pro" / "RobotM_Prologue"."""
    return bool(phase) and (phase.startswith("00_") or "RobotM_Pro" in phase)


def abilities_allowed(phase: str) -> bool:
    """Les capacites ne sont jamais bloquees pendant le prologue (codes "00_", tutoriels de controles :
    bloquer une action attendue coincerait le joueur) ni pendant les phases de vaisseau ("STG")."""
    if not phase or phase in MENU_PHASES:
        return False
    if is_prologue(phase) or "STG" in phase:
        return False
    return True
