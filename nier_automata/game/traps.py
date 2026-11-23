"""Pieges recus via Archipelago."""
from __future__ import annotations

import math


def damage_after_trap(hp: int, max_hp: int, percent: int) -> int:
    """PV apres un piege de degats (% des PV max). Un piege ne tue jamais : minimum 1 PV."""
    return max(1, hp - math.ceil(max_hp * percent / 100))


def funds_after_trap(funds: int, percent: int) -> int:
    return funds - funds * percent // 100
