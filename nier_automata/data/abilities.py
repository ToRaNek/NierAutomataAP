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
    # Bloc d'origine (0x47E47D) : "esquive aerienne deja utilisee ? -> rien ; au sol ([rbx+0x14A4] != 0) ? -> esquive ;
    # sinon marquer l'esquive aerienne utilisee, puis esquive".
    # Blocage : "en l'air ([rbx+0x14A4] == 0) ? -> rien ; sinon esquive". L'esquive au sol reste donc possible.
    # L'ancien blocage (jne -> jmp en 0x47E483) coupait aussi l'esquive au sol : signale par un testeur et mesure
    # en jeu (action 0x12 absente au sol comme en l'air). [rbx+0x14A4] releve en jeu : 1 au sol, 0 pendant un saut.
    "Air Dash": (CodePatch(
        0x47E47D,
        bytes.fromhex("3983980a0100" "0f8562020000" "3983a4140000" "750a" "c783980a010001000000"),
        bytes.fromhex("3983a4140000" "0f8462020000" "eb10" + "90" * 16)),),
    # Debut du bloc setState(0x12 = esquive) -> jmp vers "aucune action" (xor eax,eax).
    # Teste en jeu : bloque l'esquive au sol, en l'air et le sprint.
    "Evade": (CodePatch(0x47E6BB, bytes.fromhex("488b"), bytes.fromhex("eb2e")),),
    # call 0x49EA20 (lecture du bouton de tir) -> xor eax,eax : le Pod ne tire plus (teste en jeu,
    # trouve par dichotomie sur les 27 appels de 0x49EA20).
    "Pod Fire": (CodePatch(0x4306CF, bytes.fromhex("e84ce30600"), bytes.fromhex("31c00f1f00")),),
    # Lecture des boutons d'attaque (call 0x49F060 / 0x49EFE0) -> "non presse" (teste en jeu, dichotomie).
    "Light Attack": (CodePatch(0x47A389, bytes.fromhex("e8d24c0200"), bytes.fromhex("31c00f1f00")),),
    "Heavy Attack": (CodePatch(0x47A355, bytes.fromhex("e8864c0200"), bytes.fromhex("31c00f1f00")),),
    # Bouton du programme de Pod (call 0x49E5D0), 2 lectures : ensemble, le Pod reste en place et
    # ne lance pas le programme (teste en jeu avec le laser A140).
    "Pod Program": (
        CodePatch(0x529240, bytes.fromhex("e88b53f7ff"), bytes.fromhex("31c00f1f00")),
        CodePatch(0x5292AE, bytes.fromhex("e81d53f7ff"), bytes.fromhex("31c00f1f00")),
    ),
}
