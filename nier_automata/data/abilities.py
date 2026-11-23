"""Capacites de 2B bloquees par modification du code (v1.04, verifie en jeu le 2026-11-23).

Source : nierhook (InfiniteDoubleJump / InfiniteAirDash v1.02), retrouves dans la v1.04 par motif.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodePatch:
    rva: int          # adresse relative a la base du module (en memoire)
    original: bytes   # octets d'origine (capacite disponible)
    locked: bytes     # octets du blocage


ABILITY_PATCHES: dict[str, tuple[CodePatch, ...]] = {
    "Double Jump": (
        # cmp dword [rbx+0x14A8], 2 ; jge -> limite de sauts 2 -> 1 (teste en jeu)
        CodePatch(0x47E357, b"\x02", b"\x01"),
        # 2e chemin : mov eax,[rbx+0x14A8] ; cmp eax, 2 ; jge
        CodePatch(0x47E74F, b"\x02", b"\x01"),
    ),
    # jne (esquive aerienne deja utilisee) -> jmp : l'esquive aerienne est toujours ignoree (teste en jeu)
    "Air Dash": (CodePatch(0x47E483, bytes.fromhex("0f8562020000"), bytes.fromhex("e96302000090")),),
}
