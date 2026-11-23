from dataclasses import dataclass

from Options import DefaultOnToggle, PerGameCommonOptions, Range

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


class ItemChecks(DefaultOnToggle):
    """Le premier ramassage de chaque materiau (coffre, ennemi, sol) envoie un check "Item: <nom>"."""
    display_name = "Item Checks"


@dataclass
class NierAutomataOptions(PerGameCommonOptions):
    story_checks: StoryChecks
    weapon_checks: WeaponChecks
    item_checks: ItemChecks
