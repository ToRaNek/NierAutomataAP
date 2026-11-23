"""DeathLink (detection de mort par les PV) et ajout d'argent."""
from __future__ import annotations

from typing import Optional

from .memory import Memory, read_u32, write_u32

HP_OFFSET = 0x858
MAX_HP_OFFSET = 0x85C
MAX_FUNDS = 9_999_999


class DeathTracker:
    def __init__(self):
        self._last: Optional[int] = None
        self._expected = False

    def expect_death(self) -> None:
        """Appele quand le client tue 2B suite a un DeathLink recu : ne pas le renvoyer."""
        self._expected = True

    def update(self, hp: Optional[int]) -> bool:
        died = hp == 0 and self._last is not None and self._last > 0
        if hp is not None and hp > 0:
            self._expected = False
        self._last = hp
        if died and self._expected:
            self._expected = False
            return False
        return died


def add_funds(mem: Memory, offset: int, amount: int) -> None:
    write_u32(mem, offset, min(MAX_FUNDS, read_u32(mem, offset) + amount))
