"""Guide des chapitres (onglet "Chapters" du client). Sans dependance a Archipelago.

Pour chaque chapitre de la partie : s'il a ete atteint, ce qui manque pour l'ouvrir (objet de route, cles de
chapitre, Pass de zone), si son check est fait, et les fins gag qu'on peut y obtenir avec la marche a suivre.
Un chapitre atteint et non verrouille peut etre rejoue (saut de chapitre, comme le menu Chapter Select du jeu).

Les emplacements des fins gag sont ceux ou elles ont ete obtenues en jeu avec le vrai client.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import chapterlocks as cl
from . import worlddb as db
from .areas import pass_for_region
from .gagendings import GAG_ENDINGS

# lettre -> ((route, code de chapitre) ou None si la fin se fait n'importe ou, marche a suivre)
GAG_GUIDE: dict[str, tuple] = {
    "F": (("B", "01-03"), "After the boss crushes 9S, the repair hacking opens: do nothing for 3 minutes."),
    "G": (("B", "01-01"), "As 9S at the start, walk away from the factory instead of going in."),
    "H": (("A", "05-02"), "When the Goliath attacks the city, walk away from the fight (towards the desert)."),
    "I": (("A", "08-01"), "Beat Adam, then leave the area instead of going to 9S."),
    "J": (("A", "09-01"), "In the factory, attack the machine priests who guide you."),
    "K": (None, "Eat a Mackerel (Items menu > Caught Fish > Use)."),
    "L": (("A", "10-02"), "When the big machine attacks, walk away from the fight (towards the desert)."),
    "M": (("C", "14-03"), "When Pascal's Village is attacked, walk away instead of helping."),
    "N": (("A", "05-01"), "Destroy every machine of Pascal's Village without leaving it."),
    "O": (("C", "11-03"), "During the battle with 2B, walk away from the fight."),
    "P": (("C", "11-06"), "Infected 2B: stay where you are until the virus gauge is full (about 15 minutes)."),
    "Q": (("C", "11-07"), "As 9S, walk away instead of going to 2B."),
    "R": (("C", "14-05"), "As A2 in the factory shelter, attack the villagers."),
    "S": (("C", "17-01"), "After Devola and Popola arrive at the Tower, run away from it."),
    "T": (None, "Remove the OS Chip (Skills menu > Plug-in Chips)."),
    "U": (("A", "06-01"), "Self-destruct inside the Bunker (any visit to the Bunker)."),
    "V": (("C", "17-01"), "After Devola and Popola arrive at the Tower, wait 3 minutes without hacking it."),
    "W": (("A", "01-01"), "Die during the prologue."),
    "X": (("C", "11-06"), "When A2 arrives, walk away from 2B instead of going to her."),
    "Y": (None, "Quest Emil's Determination (all weapons at level 4): let Emil self-destruct at the end."),
    "Z": (("C", "14-01"), "As A2, save Pascal in front of the Resistance Camp, then kill him and walk away."),
}


# Sous-phase exacte ou la fin a ete obtenue en jeu, quand ce n'est pas le debut du chapitre (saut plus precis).
GAG_SUBPHASE: dict[str, str] = {
    "F": "05_30_B_RobotM_ProBoss_phase3", "G": "00_02_B_RobotM_Pro_9S_appearanc", "I": "110_00_A_Copy_City",
    "J": "140_00_A_RobotM_CrazyReligion", "N": "80_10_AB_Pascal_Village", "S": "260_00_CD_Ruined_City_9S",
    "V": "260_00_CD_Ruined_City_9S", "X": "50_10_CD_Ruined_City_A2Come_2B",
}
GAG_CHARACTER: dict[str, str] = {"X": "A2"}          # personnage du saut quand ce n'est pas celui du chapitre


@dataclass
class Ending:
    letter: str
    how: str
    done: bool
    start: Optional[tuple] = None          # (route, personnage, phase, sous-phase) du saut, None = pas de saut


def ending_start(letter: str) -> Optional[tuple]:
    """Ou sauter pour tenter cette fin : sa sous-phase exacte si connue, sinon le debut de son chapitre."""
    where = GAG_GUIDE[letter][0]
    i = chapter_index(*where) if where else None
    if i is None:
        return None
    c, sub = db.CHAPTERS[i], GAG_SUBPHASE.get(letter)
    if sub in c["subphases"]:
        return (c["route"], GAG_CHARACTER.get(letter, c["character"]), c["phase_ids"][c["subphases"].index(sub)], sub)
    return cl.STARTS.get(i)


@dataclass
class Row:
    index: int
    route: str
    code: str
    title: str
    name: str
    region: str
    reached: bool
    can_go: bool
    needs: list = field(default_factory=list)
    check_done: Optional[bool] = None
    endings: list = field(default_factory=list)


def chapter_index(route: str, code: str) -> Optional[int]:
    for i, c in enumerate(db.CHAPTERS):
        if c["route"] == route and c["chapter"] == code:
            return i
    return None


def needs(index: int, received, route_keys: dict, chapter_keys: dict, passes=()) -> list:
    """Objets qui manquent pour ouvrir ce chapitre (noms affichables), [] s'il est ouvert."""
    c = db.CHAPTERS[index]
    got = list(received)
    out = []
    order = "ABC"
    for r in order[1:order.find(c["route"]) + 1]:            # routes a ouvrir avant celle-ci
        name = route_keys.get(r)
        if name and name not in got:
            out.append(name)
    key = chapter_keys.get(c["route"])
    if key:
        want, have = cl.keys_needed(c["region"]), got.count(key)
        if have < want:
            out.append(f"{key} {have}/{want}")
    area = pass_for_region("A" + c["region"][1:]) if c["route"] in "AB" else None
    if area and area in passes and area not in got:
        out.append(area)
    return out


def rows(chapters: int, reached, received, route_keys: dict, chapter_keys: dict, missing, gag_endings,
         endings_seen, passes=()) -> list:
    """Une ligne par chapitre de la partie. `missing` = noms des checks restants (None si inconnu)."""
    by_chapter: dict[int, list] = {}
    for letter in sorted(gag_endings):
        where, how = GAG_GUIDE[letter]
        if where is not None:
            i = chapter_index(*where)
            if i is not None:
                by_chapter.setdefault(i, []).append(Ending(letter, how, letter in endings_seen, ending_start(letter)))
    out = []
    for i in range(min(chapters, len(db.CHAPTERS))):
        c = db.CHAPTERS[i]
        need = needs(i, received, route_keys, chapter_keys, passes)
        was = i in reached
        out.append(Row(index=i, route=c["route"], code=c["chapter"], title=c["title"], name=c["name"],
                       region=c["region"], reached=was, can_go=was and i in cl.STARTS and not need, needs=need,
                       check_done=None if missing is None else c["name"] not in missing,
                       endings=by_chapter.get(i, [])))
    return out


def anywhere(gag_endings, endings_seen) -> list:
    """Fins gag qui ne dependent pas d'un chapitre."""
    return [Ending(e, GAG_GUIDE[e][1], e in endings_seen) for e in sorted(gag_endings) if GAG_GUIDE[e][0] is None]


def line(row: Row) -> str:
    """Resume d'une ligne, pour le journal ou une liste texte."""
    state = "replay" if row.can_go else ("reached" if row.reached else "not reached")
    check = {True: "check sent", False: "check to do", None: ""}[row.check_done]
    ends = " ".join(f"{e.letter}{'*' if e.done else ''}" for e in row.endings)
    parts = [f"{row.route} {row.code} {row.title}", state, check]
    if row.needs:
        parts.append("needs " + ", ".join(row.needs))
    if ends:
        parts.append("joke endings " + ends)
    return " | ".join(p for p in parts if p)
