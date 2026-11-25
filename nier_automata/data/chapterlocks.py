"""Grands chapitres verrouilles des routes B et C/D (option chapter_locks). Sans dependance a Archipelago.

Chaque grand chapitre apres le premier de sa route demande une cle de plus ("B Chapter Key", "C/D Chapter Key",
objets progressifs). Sans assez de cles, le client ramene le joueur au debut du dernier sous-chapitre du grand
chapitre precedent ; quand la cle arrive, il l'emmene au debut du grand chapitre attendu. La route A n'en a pas :
ses zones sont deja fermees par les Pass.
"""
from __future__ import annotations

import json
import pkgutil
from typing import Optional

from . import worlddb as db

CHAPTER_KEYS: dict[str, str] = {"B": "B Chapter Key", "C": "C/D Chapter Key"}

# indice de chapitre -> (etat de route, personnage, numero de phase, sous-phase) : debuts de chapitre atteints par
# saut pendant la campagne de test (tools/campaign_report.json)
STARTS: dict[int, tuple] = {int(k): tuple(v) for k, v in json.loads(
    pkgutil.get_data(__name__.rsplit(".", 1)[0], "chapter_starts.json").decode()).items()}


def route_regions(regions, route: str) -> list[str]:
    return [r for r in regions if r.startswith(route)]


def key_counts(regions) -> dict[str, int]:
    """{route: nombre de cles} pour cette partie : une par grand chapitre apres le premier de la route."""
    out = {}
    for route in CHAPTER_KEYS:
        n = len(route_regions(regions, route)) - 1
        if n > 0:
            out[route] = n
    return out


def keys_needed(region: str) -> int:
    """Cles demandees pour entrer dans `region` : son rang dans sa route (0 pour le premier grand chapitre)."""
    return route_regions(db.REGIONS, region[0]).index(region)


def locked(chapter: int, keys: dict, received) -> bool:
    """Le chapitre d'indice `chapter` est-il ferme avec les objets `received` (liste de noms) ?"""
    c = db.CHAPTERS[chapter]
    name = keys.get(c["route"])
    return bool(name) and list(received).count(name) < keys_needed(c["region"])


def park_chapter(chapter: int) -> Optional[int]:
    """Ou attendre : dernier sous-chapitre sautable du grand chapitre precedent."""
    region = db.CHAPTERS[chapter]["region"]
    for j in range(chapter - 1, -1, -1):
        if db.CHAPTERS[j]["region"] != region and j in STARTS:
            return j
    return None


def start_chapter(chapter: int) -> Optional[int]:
    """Debut du grand chapitre de `chapter` : son premier sous-chapitre sautable."""
    region = db.CHAPTERS[chapter]["region"]
    for j, c in enumerate(db.CHAPTERS):
        if c["region"] == region and j in STARTS:
            return j
    return None
