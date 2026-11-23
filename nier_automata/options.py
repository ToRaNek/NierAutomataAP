from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

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
    valid_keys = {"Double Jump", "Air Dash", "Ground Evade", "Pod Fire", "Light Attack", "Heavy Attack", "Pod Program"}
    default = frozenset({"Double Jump", "Air Dash", "Ground Evade"})


class TrapPercentage(Range):
    """Pourcentage des objets de remplissage remplaces par des pieges
    (degats 5 %/10 % des PV max, perte de 10 % des G)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 20


class MaxLevelCheck(Range):
    """Chaque niveau atteint envoie un check "Level N", du niveau 2 jusqu'a cette valeur (0 = desactive).
    Monter de niveau est toujours possible : ces checks peuvent contenir des objets importants."""
    display_name = "Max Level Check"
    range_start = 0
    range_end = 50
    default = 20


class ShopChecks(Range):
    """Nombre d'AP Items vendus en tete de chaque magasin sur la route (Camp de la Resistance, Village de
    Pascal, Chateau de la foret). Acheter un AP Item envoie un check."""
    display_name = "Shop Checks"
    range_start = 0
    range_end = 3   # 9 porteurs (skins de Pod) pour 3 magasins
    default = 2


class ShopPrice(Range):
    """Prix d'un AP Item en magasin (G)."""
    display_name = "Shop Price"
    range_start = 0
    range_end = 20000
    default = 300


class ApItems(DefaultOnToggle):
    """Des objets "AP Item" apparaissent au sol sur le chemin du joueur (a cote des objets poses par le jeu
    dans les zones traversees). Les ramasser envoie un check (rien n'est ajoute a l'inventaire)."""
    display_name = "AP Items"


class ApItemsPerPhase(Range):
    """AP Items au sol par etape de l'histoire. Chaque check s'appelle "AP Item: <lieu> #k" (un indice dit
    donc ou chercher). Avec l'objectif story_progress, seules les etapes jusqu'a l'objectif en ont."""
    display_name = "AP Items Per Phase"
    range_start = 1
    range_end = 3
    default = 2


class ItemChecks(Toggle):
    """Desactive par defaut. Si active : le premier ramassage de chaque materiau envoie un check "Item: <nom>"."""
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
    ap_items: ApItems
    ap_items_per_phase: ApItemsPerPhase
    shop_checks: ShopChecks
    shop_price: ShopPrice
    chest_checks: ChestChecks
    max_level_check: MaxLevelCheck
    trap_percentage: TrapPercentage
    randomized_abilities: RandomizedAbilities
    goal: Goal
    death_link: DeathLink
