"""Fins "gag" F a Z (option gag_ending_checks). Sans dependance a Archipelago.

Chaque fin passe par une sous-phase "Ending_<lettre>" (phf/pf30, docs/research/endings_triggers.json) : le client
la reconnait au nom de la phase. Route = route ou la fin peut etre obtenue (les fins "a tout moment" comptent
pour la route A). Ces checks ne recoivent jamais d'objet important : on peut ne jamais les faire.
"""
from __future__ import annotations

# lettre -> route
GAG_ENDINGS: dict[str, str] = {
    "F": "B", "G": "B", "H": "A", "I": "A", "J": "A", "K": "A", "L": "A", "M": "C", "N": "C", "O": "C", "P": "C",
    "Q": "C", "R": "C", "S": "C", "T": "A", "U": "A", "V": "C", "W": "A", "X": "C", "Y": "C", "Z": "C",
}
PHASE_PREFIX = "Ending_"


def letters_in_scope(regions) -> tuple:
    routes = {r[0] for r in regions}
    return tuple(e for e, route in GAG_ENDINGS.items() if route in routes)


def region_of(letter: str, regions) -> str:
    """Premiere region jouee de la route de cette fin."""
    return next(r for r in regions if r[0] == GAG_ENDINGS[letter])


def ending_from_phase(phase: str):
    """Lettre de la fin gag en cours d'apres le nom de la phase, sinon None."""
    if phase and phase.startswith(PHASE_PREFIX):
        letter = phase[len(PHASE_PREFIX):len(PHASE_PREFIX) + 1]
        return letter if letter in GAG_ENDINGS else None
    return None
