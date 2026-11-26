"""Panneaux "zone verrouillee" dessines par le mod a l'entree de chaque zone fermee par un Pass (option area_locks).
Sans dependance a Archipelago.

Pour chaque Pass : le point ou le jeu signale l'entree dans la zone en venant de la ville (releve en jeu en avancant
en ligne droite depuis le cote ville) et la direction d'arrivee. Le panneau est pose un peu avant ce point, en
travers du passage. C'est un affichage : ce qui arrete vraiment le joueur reste le retour en arriere du client."""
from __future__ import annotations

import struct

from .areas import zone_name

# Pass -> (x, y du SOL, z du point d'entree, direction d'arrivee (dx, dz)).
# Hauteur du sol mesuree en jeu en laissant tomber le joueur sur place. La ou deux niveaux se superposent, c'est
# celui du chemin qui est retenu : route surelevee de l'usine (20,7 m, pas le sol 19 m plus bas), rue du desert
# (15,1 m, pas le toit a 46,8 m), galerie de la Ville inondee (-58,5 m, pas la surface a -17,6 m).
GATES: dict[str, tuple] = {
    "Desert Pass": ((-169.0, 15.1, 33.1), (-0.5, -0.866)),
    "Park Pass": ((313.1, 0.1, 344.5), (1.0, 0.0)),
    "Village Pass": ((397.1, 3.6, -35.0), (1.0, 0.0)),
    "Forest Pass": ((75.4, 11.4, -227.0), (0.0, -1.0)),
    "Flooded City Pass": ((471.9, -58.5, 595.0), (0.0, 1.0)),
    "Factory Pass": ((-207.0, 20.7, 514.1), (-1.0, 0.0)),
}
BEFORE = 4.0        # metres avant le point d'entree, cote ville
WIDTH = 36.0
HEIGHT = 6.0        # une rangee du motif : le panneau ne depasse plus sous le sol
SINK = 0.5          # le pied s'enfonce a peine (terrain en pente)
MAX_WALLS = 8
WALL_SIZE = 88      # 6 floats + 64 octets de texte


def text_for(pass_name: str) -> str:
    return f"{zone_name(pass_name).upper()} LOCKED  -  {pass_name} needed"[:63]


def locked_passes(passes, owned) -> list:
    """Pass de la partie pas encore recus, dans l'ordre de l'histoire, qui ont une entree connue."""
    wanted, got = set(passes), set(owned)
    return [p for p in GATES if p in wanted and p not in got][:MAX_WALLS]


def wall(pass_name: str) -> tuple:
    """(x1, y, z1, x2, z2, hauteur) du panneau de ce Pass."""
    (x, y, z), (dx, dz) = GATES[pass_name]
    cx, cz = x - dx * BEFORE, z - dz * BEFORE
    sx, sz = -dz * WIDTH / 2, dx * WIDTH / 2          # en travers du passage
    return (cx - sx, y - SINK, cz - sz, cx + sx, cz + sz, HEIGHT + SINK)


def pack(names) -> bytes:
    """Murs au format du mod (mod/overlay.h)."""
    out = b""
    for n in names:
        out += struct.pack("<6f", *wall(n)) + text_for(n).encode("ascii", "replace").ljust(64, b"\0")
    return out
