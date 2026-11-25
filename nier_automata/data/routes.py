"""Routes verrouillees par un objet (option route_locks). Sans dependance a Archipelago.

La route B ne s'ouvre qu'avec "Route B Access", la route C/D qu'avec "Route C/D Access". Sans l'objet, le client
ramene le joueur dans la route precedente (saut de chapitre, comme le menu Chapter Select du jeu) a un endroit ou
il est libre de continuer ses checks ; quand l'objet arrive, le client l'emmene au debut de la route.
"""
from __future__ import annotations

ROUTE_KEYS: dict[str, str] = {"B": "Route B Access", "C": "Route C/D Access"}
_ORDER = "ABC"

# route verrouillee -> (etat de route, personnage, numero de phase, sous-phase) ou attendre :
# debut du chapitre 7 de la route precedente (Village de Pascal, monde ouvert, quetes encore disponibles)
PARK = {
    "B": ("A", "2B", 0x200, "80_00_AB_Pascal_Village"),
    "C": ("B", "9S", 0x200, "80_00_AB_Pascal_Village"),
}
# route -> debut de cette route
START = {
    "B": ("B", "9S", 0x100, "00_00_B_RobotM_Pro_RobotBrother"),
    "C": ("C", "2B", 0x300, "00_10_CD_Bunker_Hangar_2B"),
}


def keys_in_scope(regions) -> dict[str, str]:
    """{route: objet} pour les routes jouees dans cette partie."""
    return {r: name for r, name in ROUTE_KEYS.items() if any(x.startswith(r) for x in regions)}


def locked_route(current: str, new: str, keys: dict, owned) -> str:
    """Premiere route, entre `current` (exclue) et `new` (incluse), dont l'objet manque ; "" si aucune."""
    a, b = _ORDER.find(current), _ORDER.find(new)
    for r in _ORDER[a + 1:b + 1]:
        if r in keys and keys[r] not in owned:
            return r
    return ""
