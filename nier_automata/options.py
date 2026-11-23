from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range

from .data.tables import MAX_CHEST_CHECKS, MAX_STORY, MAX_WEAPON_CHECKS


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


class ChestChecks(Range):
    """Nombre de checks "Chest" : chaque coffre ouvert dans le jeu envoie un check.
    La route A contient beaucoup de coffres : ces checks peuvent contenir des objets importants."""
    display_name = "Chest Checks"
    range_start = 0
    range_end = MAX_CHEST_CHECKS
    default = 15


class RandomizedAbilities(OptionSet):
    """Capacites de 2B bloquees au depart et debloquees par un objet AP (trouve par un autre joueur)."""
    display_name = "Randomized Abilities"
    valid_keys = {"Double Jump", "Air Dash", "Ground Evade"}
    default = frozenset({"Double Jump", "Air Dash", "Ground Evade"})


class TrapPercentage(Range):
    """Pourcentage des objets de remplissage remplaces par des pieges
    (degats 5 %/10 % des PV max, perte de 10 % des G)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 20


class ItemChecks(DefaultOnToggle):
    """Le premier ramassage de chaque materiau (coffre, ennemi, sol) envoie un check "Item: <nom>"."""
    display_name = "Item Checks"


class Goal(Choice):
    """Condition de victoire.
    story_progress : atteindre `story_checks` sequences d'histoire (partie courte, reglable).
    ending_a : terminer la route A (premiere fin, partie longue)."""
    display_name = "Goal"
    option_story_progress = 0
    option_ending_a = 1
    default = 0


@dataclass
class NierAutomataOptions(PerGameCommonOptions):
    story_checks: StoryChecks
    weapon_checks: WeaponChecks
    item_checks: ItemChecks
    chest_checks: ChestChecks
    trap_percentage: TrapPercentage
    randomized_abilities: RandomizedAbilities
    goal: Goal
    death_link: DeathLink
