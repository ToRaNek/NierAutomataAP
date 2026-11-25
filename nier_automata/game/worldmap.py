"""Carte du monde vue de dessus : conversion monde -> image et liste des points a dessiner (sans interface)."""
from __future__ import annotations

import json
import pkgutil
from dataclasses import dataclass
from typing import Optional

from ..data import worlddb as db


@dataclass
class MapInfo:
    x0: float
    z0: float
    scale: float      # metres par pixel
    width: int
    height: int

    def to_pixel(self, x: float, z: float) -> tuple[float, float]:
        """Pixel de l'image (origine en haut a gauche, z vers le bas)."""
        return (x - self.x0) / self.scale, (z - self.z0) / self.scale

    def inside(self, x: float, z: float) -> bool:
        px, py = self.to_pixel(x, z)
        return 0 <= px < self.width and 0 <= py < self.height


def load_info() -> MapInfo:
    return MapInfo(**json.loads(pkgutil.get_data(__name__.rsplit(".", 2)[0] + ".data", "map.json").decode()))


MAP_FILES = {"all": "map.png", "surface": "map_surface.png", "indoor": "map_indoor.png"}


def map_png(layer: str = "all") -> bytes:
    return pkgutil.get_data(__name__.rsplit(".", 2)[0] + ".data", MAP_FILES[layer])


@dataclass
class Marker:
    kind: str        # "hint", "check" ou "player"
    x: float
    z: float
    label: str


def markers(hints, remaining, player: Optional[tuple], layer: str = "all") -> list[Marker]:
    """hints : [(objet, pour qui, nom du check)] ; remaining : noms des checks pas encore valides.
    layer : "all", ou "surface" / "indoor" pour ne garder que les checks de ce niveau (le joueur reste affiche)."""
    def shown(name):
        return layer == "all" or db.location_layer(name) == layer

    out, hinted = [], set()
    for item, who, where in hints:
        pos = db.location_position(where)
        if pos is None or where in hinted or not shown(where):
            continue
        hinted.add(where)
        out.append(Marker("hint", pos[0], pos[2], f"{item} ({who}) - {where}"))
    checks = []
    for name in sorted(remaining):
        pos = db.location_position(name)
        if pos is not None and name not in hinted and shown(name):
            checks.append(Marker("check", pos[0], pos[2], name))
    out = checks + out                       # les indices sont dessines par-dessus
    if player is not None:
        out.append(Marker("player", player[0], player[2], ""))
    return out
