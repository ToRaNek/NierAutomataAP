"""Cles d'acces de la Tour (option tower_keys). Sans dependance a Archipelago.

Le jeu donne trois objets-cles pendant la route C/D (Forest, Ocean, Park Access Key) et la porte de la Tour ne se
pirate pas sans eux (verifie en jeu : sans cle la barriere repousse 9S et le piratage s'arrete, avec les trois il
aboutit). Avec l'option, le client reprend les cles que le jeu donne et les rend quand elles arrivent du multimonde.
"""
from __future__ import annotations

# nom de l'objet -> identifiant de l'objet-cle du jeu
TOWER_KEYS: dict[str, int] = {"Forest Access Key": 820, "Ocean Access Key": 821, "Park Access Key": 822}
TOWER_REGION = "C17"                  # grand chapitre de la Tour
TOWER_OPEN_PHASE = "270_CD_Tower"     # sous-phases jouees une fois la porte ouverte : les cles ne servent plus


def keys_in_scope(regions) -> list[str]:
    return list(TOWER_KEYS) if TOWER_REGION in regions else []


def to_remove(owned_items, received) -> list[int]:
    """Cles presentes dans l'inventaire sans avoir ete recues du multimonde : donnees par le jeu, a reprendre."""
    got = {TOWER_KEYS[n] for n in received if n in TOWER_KEYS}
    return sorted((set(TOWER_KEYS.values()) & set(owned_items)) - got)


def to_give_back(owned_items, received) -> list[str]:
    """Cles recues du multimonde absentes de l'inventaire (sauvegarde rechargee) : a redonner."""
    return [n for n in TOWER_KEYS if n in received and TOWER_KEYS[n] not in owned_items]
