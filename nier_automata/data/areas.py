"""Zones du jeu verrouillees par un objet "Pass" (option area_locks).

Le jeu garde l'identifiant de la zone courante dans un entier global (docs/research/areas.json). Chaque Pass
ouvre les identifiants d'une grande zone ; `region` est la premiere region logique dont l'histoire y entre.
Sans dependance a Archipelago.
"""
from __future__ import annotations

AREA_ID_RVA = 0x1494A04

# nom de l'objet -> (region logique, nom affiche de la zone, identifiants de zone)
# La Ville copiee (zone 25) n'a pas de Pass : on y arrive par un placement du jeu, pas a pied (releve en jeu au
# debut de 110_00_A_Copy_City), le mur n'aurait donc rien a quoi revenir.
AREA_PASSES: dict[str, tuple[str, str, frozenset]] = {
    "Desert Pass": ("A03", "Desert Zone", frozenset({30, 35, 40, 45, 50, 190})),
    "Park Pass": ("A04", "Amusement Park", frozenset({55, 60, 65, 70, 135})),
    "Village Pass": ("A05", "Pascal's Village", frozenset({165})),
    "Forest Pass": ("A06", "Forest Zone", frozenset({75, 85, 90, 125, 185})),
    "Flooded City Pass": ("A07", "Flooded City", frozenset({95, 130, 195})),
    "Factory Pass": ("A09", "Abandoned Factory", frozenset({105, 115, 120})),
}

_ZONE_OF = {i: name for name, (_, _, ids) in AREA_PASSES.items() for i in ids}


def passes_in_scope(regions) -> list[str]:
    """Pass utiles a une partie : ceux dont la zone est jouee (ordre de l'histoire)."""
    rs = set(regions)
    return [name for name, (region, _, _) in AREA_PASSES.items() if region in rs]


def pass_for_area(area_id: int):
    """Nom du Pass qui ouvre cette zone, ou None si la zone n'est jamais verrouillee."""
    return _ZONE_OF.get(area_id)


def pass_for_region(region: str):
    for name, (r, _, _) in AREA_PASSES.items():
        if r == region:
            return name
    return None


def zone_name(pass_name: str) -> str:
    return AREA_PASSES[pass_name][1]
