from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

from .data.tables import MAX_CHEST_CHECKS, MAX_STORY, MAX_WEAPON_CHECKS


class StoryChecks(Range):
    """Number of "Story: <place>" checks: each named story step of route A gives one (in order).
    With the story_progress goal, reaching the last one wins."""
    display_name = "Story Checks"
    range_start = 1
    range_end = MAX_STORY
    default = 12


class WeaponChecks(Range):
    """Number of "Weapon Found" checks: each weapon found in the game (chest, quest, shop) is removed
    and sends a check. Route A gives few weapons: keep this low."""
    display_name = "Weapon Checks"
    range_start = 0
    range_end = MAX_WEAPON_CHECKS
    default = 8


class ChestChecks(Range):
    """Number of "Chest" checks: each chest opened in the game sends a check."""
    display_name = "Chest Checks"
    range_start = 0
    range_end = MAX_CHEST_CHECKS
    default = 15


class RandomizedAbilities(OptionSet):
    """2B's abilities locked at the start and unlocked by an Archipelago item. Nothing is locked during the
    prologue/tutorial. Add "Pod Fire" and "Pod Program" for a pod-less start."""
    display_name = "Randomized Abilities"
    valid_keys = {"Double Jump", "Air Dash", "Ground Evade", "Pod Fire", "Light Attack", "Heavy Attack", "Pod Program"}
    default = frozenset({"Double Jump", "Air Dash", "Ground Evade"})


class TrapPercentage(Range):
    """Percentage of filler items replaced by traps (5%/10% max HP damage, 10% money loss, enemy spawn)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 20


class MaxLevelCheck(Range):
    """Each level reached sends a "Level N" check, from level 2 up to this value (0 = off)."""
    display_name = "Max Level Check"
    range_start = 0
    range_end = 50
    default = 20


class ShopChecks(Range):
    """Number of AP Items sold at the top of each shop on the route (Resistance Camp, Pascal's Village,
    Forest Castle). Buying one sends a check; its description shows what's inside and for whom."""
    display_name = "Shop Checks"
    range_start = 0
    range_end = 3   # 9 porteurs (skins de Pod) pour 3 magasins
    default = 2


class ShopPrice(Range):
    """Price of a shop AP Item (G)."""
    display_name = "Shop Price"
    range_start = 0
    range_end = 20000
    default = 300


class ApItems(DefaultOnToggle):
    """"AP Item" objects appear on the ground along the player's path. Picking one up sends a check
    (nothing is added to the inventory)."""
    display_name = "AP Items"


class ApItemsPerPhase(Range):
    """Ground AP Items per story step. Each check is named "AP Item: <place> #k" so hints say where to look.
    With the story_progress goal, only the steps up to the goal have them."""
    display_name = "AP Items Per Phase"
    range_start = 1
    range_end = 3
    default = 2


class ItemChecks(Toggle):
    """Off by default. If on: the first pickup of each material sends an "Item: <name>" check."""
    display_name = "Item Checks"


class Goal(Choice):
    """Victory condition.
    story_progress: reach `story_checks` story steps (short game, adjustable).
    ending_a: finish route A (first ending, long game)."""
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
