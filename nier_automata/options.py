from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

from .data.tables import MAX_STORY, MAX_WEAPON_CHECKS


class StoryChecks(Range):
    """Number of story chapters covered when the goal is story_progress. Chapters are counted in order across
    the routes (A: 37 chapters, then B, then C/D); reaching the last one wins. Every chapter in range is a
    "Story <route> <chapter>: <title>" check, and only the areas opened by these chapters have checks.
    Ignored by the ending goals (they cover whole routes)."""
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


class ChestChecks(DefaultOnToggle):
    """Every chest of the areas in range is a check named after its location ("Chest: City Ruins #12").
    Hack-locked chests need 9S, so they only appear from route B on."""
    display_name = "Chest Checks"


class AccessPointChecks(DefaultOnToggle):
    """Activating an access point for the first time sends a check ("Access Point: Desert: Camp")."""
    display_name = "Access Point Checks"


class QuestChecks(Toggle):
    """Completing a side quest sends a check ("Quest: <name>"). Quests that can be missed never hold an
    important item. EXPERIMENTAL (read from the game's quest status, not tested in game yet): off by default."""
    display_name = "Quest Checks"


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
    """"AP Item" objects appear on the ground at collection points of the game, named after their area
    ("AP Item: Desert Zone: Housing Complex #2"). Picking one up sends a check and shows what it contains."""
    display_name = "AP Items"


class ApItemsPerArea(Range):
    """Number of ground AP Items per area (they are spread out; #1 is the closest to the access point)."""
    display_name = "AP Items Per Area"
    range_start = 1
    range_end = 8
    default = 3


class ItemChecks(Toggle):
    """Off by default. If on: the first pickup of each material sends an "Item: <name>" check."""
    display_name = "Item Checks"


class Goal(Choice):
    """Victory condition, which also sets how much of the game has checks.
    story_progress: reach `story_checks` chapters (short game, adjustable).
    ending_a: finish route A. ending_b: finish routes A and B. ending_cd: finish route C/D (ending C or D).
    ending_e: get ending E."""
    display_name = "Goal"
    option_story_progress = 0
    option_ending_a = 1
    option_ending_b = 2
    option_ending_cd = 3
    option_ending_e = 4
    default = 0


@dataclass
class NierAutomataOptions(PerGameCommonOptions):
    story_checks: StoryChecks
    weapon_checks: WeaponChecks
    item_checks: ItemChecks
    ap_items: ApItems
    ap_items_per_area: ApItemsPerArea
    access_point_checks: AccessPointChecks
    quest_checks: QuestChecks
    shop_checks: ShopChecks
    shop_price: ShopPrice
    chest_checks: ChestChecks
    max_level_check: MaxLevelCheck
    trap_percentage: TrapPercentage
    randomized_abilities: RandomizedAbilities
    goal: Goal
    death_link: DeathLink
