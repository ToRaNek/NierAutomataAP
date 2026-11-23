"""Blocage/deblocage des capacites de 2B selon les objets AP recus."""
from __future__ import annotations

from ..data.abilities import ABILITY_PATCHES


class AbilityLock:
    def __init__(self, mem, randomized: set[str]):
        self.mem = mem
        self.randomized = {a for a in randomized if a in ABILITY_PATCHES}

    def _set(self, name: str, locked: bool) -> None:
        for p in ABILITY_PATCHES[name]:
            addr = self.mem.base + p.rva
            cur = self.mem.read(addr, len(p.original))
            want = p.locked if locked else p.original
            if cur == want or cur not in (p.original, p.locked):
                continue  # deja bon, ou octets inattendus (autre version) : ne jamais ecrire
            writer = getattr(self.mem, "write_code", self.mem.write)
            writer(addr, want)

    def sync(self, received: set[str]) -> None:
        for name in self.randomized:
            self._set(name, locked=name not in received)

    def unlock_all(self) -> None:
        for name in self.randomized:
            self._set(name, locked=False)
