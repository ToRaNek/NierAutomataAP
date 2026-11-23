"""Comparaison de photos memoire (recherche des flags : coffres, points d'acces, pods...)."""
from __future__ import annotations

import struct


def diff_u32(a: bytes, b: bytes, base: int) -> list[tuple[int, int, int]]:
    if len(a) != len(b):
        raise ValueError(f"tailles differentes : {len(a)} != {len(b)}")
    n = len(a) // 4
    wa = struct.unpack(f"<{n}I", a[:n * 4])
    wb = struct.unpack(f"<{n}I", b[:n * 4])
    return [(base + i * 4, x, y) for i, (x, y) in enumerate(zip(wa, wb)) if x != y]


def filter_small(changes, max_delta: int):
    out = []
    for off, old, new in changes:
        x = old ^ new
        if abs(new - old) <= max_delta or (x & (x - 1)) == 0:
            out.append((off, old, new))
    return out


def exclude_offsets(changes, noise: set[int]):
    return [c for c in changes if c[0] not in noise]
