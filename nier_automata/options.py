from dataclasses import dataclass

from Options import PerGameCommonOptions, Range

from .data.tables import MAX_STORY, MAX_WEAPON_CHECKS


class StoryChecks(Range):
    """Nombre de checks "Story Progress" : chaque nouvelle zone/sequence de l'histoire en donne un."""
    display_name = "Story Checks"
    range_start = 1
    range_end = MAX_STORY
    default = 12


class WeaponChecks(Range):
    """Nombre de checks "Weapon Found" : chaque arme trouvee dans le jeu (coffre, quete, boutique)
    est retiree et donne un check. La route A donne peu d'armes : rester bas."""
    display_name = "Weapon Checks"
    range_start = 0
    range_end = MAX_WEAPON_CHECKS
    default = 8


@dataclass
class NierAutomataOptions(PerGameCommonOptions):
    story_checks: StoryChecks
    weapon_checks: WeaponChecks
