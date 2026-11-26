"""Envoie au mod les panneaux des zones encore verrouillees. Ne fait rien sans le mod (acces par processus)."""
from __future__ import annotations

import struct

from ..data import gatewalls as gw

OP_WALLS, OP_WALLSTATE = 8, 9
CAMERA_EYE_RVA, CAMERA_TARGET_RVA, CAMERA_FOV_RVA = 0x1020BC0, 0x1020BD0, 0x1020CE8      # releves en jeu, v1.04
PLAYER_PTR_RVA = 0x1020C88       # le mod s'en sert pour arreter le joueur au panneau
MIN_MOD_VERSION = 4


class GateWalls:
    def __init__(self):
        self._sent = None          # (pid du jeu, Pass affiches) du dernier envoi reussi

    def update(self, mem, passes, owned) -> bool:
        """Met les panneaux a jour si la liste a change (ou si le jeu a ete relance). True si un envoi a eu lieu."""
        if getattr(mem, "mod_version", 0) < MIN_MOD_VERSION:
            return False
        names = gw.locked_passes(passes, owned)
        key = (mem.pid, tuple(names))
        if key == self._sent:
            return False
        req = struct.pack("<BQQQQI", OP_WALLS, mem.base + CAMERA_EYE_RVA, mem.base + CAMERA_TARGET_RVA,
                          mem.base + CAMERA_FOV_RVA, mem.base + PLAYER_PTR_RVA, len(names)) + gw.pack(names)
        if mem._ask(req, 1) != b"\x01":
            return False
        self._sent = key
        return True

    @staticmethod
    def status(mem) -> int:
        """1 : dessines, 0 : pas encore, -1 : l'affichage du mod a echoue."""
        return struct.unpack("<i", mem._ask(bytes([OP_WALLSTATE]), 4))[0]
