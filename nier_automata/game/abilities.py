"""Blocage/deblocage des capacites de 2B selon les objets AP recus."""
from __future__ import annotations

from typing import Optional

from ..data.abilities import ABILITY_PATCHES

# Capacites conditionnelles : (patch utilise, condition) -> bloque seulement si la condition est vraie.
# "Ground Evade" reutilise le patch "Evade" mais seulement quand 2B est au sol, pour garder l'esquive
# aerienne (capacite "Air Dash" separee).
CONDITIONAL = {"Ground Evade": "Evade"}


class AbilityLock:
    def __init__(self, mem, randomized: set[str]):
        self.mem = mem
        self.randomized = {a for a in randomized if a in ABILITY_PATCHES or a in CONDITIONAL}
        self.jammed: set[str] = set()      # pannes en cours (pieges "System Failure")

    def _set(self, patch_name: str, locked: bool) -> None:
        for p in ABILITY_PATCHES[patch_name]:
            addr = self.mem.base + p.rva
            cur = self.mem.read(addr, len(p.original))
            want = p.locked if locked else p.original
            if cur == want or cur not in (p.original, p.locked):
                continue  # deja bon, ou octets inattendus (autre version) : ne jamais ecrire
            writer = getattr(self.mem, "write_code", self.mem.write)
            writer(addr, want)

    def sync(self, received: set[str], grounded: Optional[bool] = None, allowed: bool = True,
             jammed=frozenset()) -> None:
        if not allowed:
            self.unlock_all()
            return
        jammed = {a for a in jammed if a in ABILITY_PATCHES}
        for name in self.randomized:
            if name in CONDITIONAL:
                self._set(CONDITIONAL[name], locked=name not in received and grounded is True)
            else:
                self._set(name, locked=name not in received or name in jammed)
        for name in (jammed | self.jammed) - self.randomized:
            self._set(name, locked=name in jammed)
        self.jammed = jammed

    def unlock_all(self) -> None:
        for name in self.randomized | self.jammed:
            self._set(CONDITIONAL.get(name, name), locked=False)
        self.jammed = set()
