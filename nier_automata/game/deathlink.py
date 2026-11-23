"""DeathLink (detection de mort par les PV) et ajout d'argent."""
from __future__ import annotations

from typing import Optional

from .memory import Memory, read_u32, write_u32

# Vrais PV (verifie en jeu : +0x858 est une copie recalculee a chaque image).
HP_OFFSET = 0x10668
MAX_FUNDS = 9_999_999


class DeathTracker:
    """Mort = 2B vivante puis deux lectures a 0 de suite sur la meme entite (evite les valeurs
    passageres pendant un chargement)."""

    def __init__(self):
        self._expected = False
        self.reset()

    def reset(self) -> None:
        self._alive = False
        self._pending = False
        self._ptr = None

    def expect_death(self) -> None:
        """Appele quand le client tue 2B suite a un DeathLink recu : ne pas le renvoyer."""
        self._expected = True

    def update(self, hp: Optional[int], ptr=None) -> bool:
        if hp is None or ptr != self._ptr:
            self.reset()
            self._ptr = ptr
            self._alive = hp is not None and hp > 0
            return False
        if hp > 0:
            self._alive, self._pending, self._expected = True, False, False
            return False
        if not self._pending:
            self._pending = self._alive
            return False
        self._pending, died, self._alive = False, self._alive, False
        if died and self._expected:
            self._expected = False
            return False
        return died


def add_funds(mem: Memory, offset: int, amount: int) -> None:
    write_u32(mem, offset, min(MAX_FUNDS, read_u32(mem, offset) + amount))
