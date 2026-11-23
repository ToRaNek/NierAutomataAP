"""Phases d'histoire. Noms internes non documentes : on compte les codes de phase distincts."""
from __future__ import annotations

from typing import Optional

MENU_PHASES = {"SIGNIN", "START"}
# Provisoire (AutomataSpeedrunMod) : a confirmer avec tools/phases_seen.log en fin de route A.
GOAL_PHASE_PREFIX = "EndRoll_A"  # generique de fin A (phf/pf10.dat)


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


# Route A : phases nommees (fichiers du jeu ph1/p100.dat et ph2/p200.dat, "*_sub.bxm"), dans l'ordre.
# Un check par phase. Les codes "NN_XX" se repetent d'un fichier a l'autre (30_AB = atterrissage ET village
# de Pascal) : on compare le NOM complet (prefixe). Libelles <= 17 caracteres (notification en jeu).
ROUTE_A: list[tuple[str, str]] = [
    ("05_00_A_RobotM_Pro_ArmBoss", "Boss du prologue"),
    ("10_A_bunker_Robot_Battle", "Bunker: arrivee"),
    ("11_A_bunker_monitorHD", "Bunker: briefing"),
    ("13_A_bunker_Setup", "Bunker: prepa"),
    ("16_AB_bunker_Order", "Bunker: mission"),
    ("20_AB_buker_Aerial_battle", "Vol vers la Terre"),
    ("30_AB_Ruined_City_ForcedLanding", "Atterrissage"),
    ("40_AB_Resistance_Camp_Leader", "Camp Resistance"),
    ("50_AB_Desert_temple", "Entree du desert"),
    ("51_AB_MainDesert", "Desert"),
    ("52_AB_Danchi_Haikyo", "Desert: immeubles"),
    ("55_AB_Danchi_Boss_1", "Boss du desert"),
    ("56_AB_Danchi_Boss_EV1", "Boss desert (2)"),
    ("58_AB_BossArea_Fall", "Chute (desert)"),
    ("70_AB_Amusement_Park", "Parc d'attraction"),
    ("76_AB_Amusement_Park_Boss", "Boss Simone 1"),
    ("77_AB_Amusement_Park_Boss", "Boss Simone 2"),
    ("78_AB_Amusement_Park_Boss", "Boss Simone 3"),
    ("00_AB_Ruined_City", "Retour en ville"),
    ("10_AB_Alien_Ship", "Vaisseau alien"),
    ("15_AB_Transfer_device", "Teleporteur"),
    ("20_AB_Bunker", "Retour au Bunker"),
    ("30_AB_Pascal_Village", "Village de Pascal"),
    ("70_AB_Resistance_Camp", "Camp (retour)"),
    ("90_AB_Battle_Submerge_City", "Ville engloutie 1"),
    ("91_AB_Battle_Submerge_City_2", "Ville engloutie 2"),
    ("92_AB_Battle_Submerge_City_3", "Ville engloutie 3"),
]


def route_index(phase: str) -> Optional[int]:
    """Indice (0..) de la phase nommee de la route A, ou None. Le plus long prefixe gagne."""
    if not phase:
        return None
    best, best_len = None, -1
    for i, (prefix, _) in enumerate(ROUTE_A):
        if phase.startswith(prefix) and len(prefix) > best_len:
            best, best_len = i, len(prefix)
    return best
