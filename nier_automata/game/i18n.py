"""Textes affiches en jeu, dans la langue du jeu (anglais par defaut, francais disponible).

Langue du jeu (verifie dans l'exe v1.04, fonction 0x7A9510) : u32 a RVA 0x1495E84.
1 = anglais, 2 = japonais, 3 = allemand, 4 = francais, 5 = espagnol, 6 = italien,
10 = chinois simplifie, 11 = chinois traditionnel, 12 = coreen.
"""
from __future__ import annotations

import struct

LANG_RVA = 0x1495E84
_BY_VALUE = {1: "en", 2: "ja", 3: "de", 4: "fr", 5: "es", 6: "it", 10: "zh", 11: "zh", 12: "ko"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "from": "From {who}: ",
        "for": "For {who}: ",
        "for_you": "For you: ",
        "check": "Check: ",
        "progression": " (progression)",
        "ap_item_default": "Archipelago item",
        "shop_short": "Shop {place} #{n}",
        "checks_title": "Archipelago checks",
        "hints_title": "Hint from {who}",
        "checks_head": "Remaining checks: {n} / {total}",
        "hints_head": "Hints your friends asked for (items hidden in your world):",
        "hint_line": "{item} for {who}\n  -> {where}",
        "area_locked": "Locked: ",
    },
    "fr": {
        "from": "De {who} : ",
        "for": "Pour {who} : ",
        "for_you": "Pour toi : ",
        "check": "Check : ",
        "progression": " (progression)",
        "ap_item_default": "Objet Archipelago",
        "shop_short": "Magasin {place} #{n}",
        "checks_title": "Checks Archipelago",
        "hints_title": "Indice de {who}",
        "checks_head": "Checks restants : {n} / {total}",
        "hints_head": "Indices demandes par tes potes (objets caches dans ta partie) :",
        "hint_line": "{item} pour {who}\n  -> {where}",
        "area_locked": "Ferme : ",
    },
}

SHORT_PLACES = {
    "en": {"Resistance Camp": "Camp", "Pascal's Village": "Pascal", "Forest Castle": "Castle"},
    "fr": {"Resistance Camp": "Camp", "Pascal's Village": "Pascal", "Forest Castle": "Foret"},
}


def language_from_value(v: int) -> str:
    return _BY_VALUE.get(v, "en")


def game_language(mem) -> str:
    try:
        return language_from_value(struct.unpack("<I", mem.read(mem.base + LANG_RVA, 4))[0])
    except OSError:
        return "en"


def t(lang: str, key: str, **kw) -> str:
    table = STRINGS.get(lang, STRINGS["en"])
    return table.get(key, STRINGS["en"][key]).format(**kw)


def short_place(lang: str, place: str) -> str:
    return SHORT_PLACES.get(lang, SHORT_PLACES["en"]).get(place, place)
