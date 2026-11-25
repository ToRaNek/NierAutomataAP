from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, Toggle

from .data.tables import MAX_WEAPON_CHECKS


class StoryRoute(Choice):
    """Route of the chapter to reach when the goal is story_progress. Routes A and B go through the same
    chapters 1-10 (B is the second playthrough, as 9S); route C/D has chapters 11-17."""
    display_name = "Story Route"
    option_a = 0
    option_b = 1
    option_cd = 2
    default = 0


class StoryChapter(Range):
    """Chapter to finish when the goal is story_progress (the 17 big chapters of the game: 1-10 in routes A
    and B, 11-17 in route C/D). You win when you reach the last part of that chapter. Every part of every
    chapter up to it is a "Story <route> <chapter>: <title>" check, and only the areas opened by then have
    checks. Example: route a, chapter 4 = a short game that ends at the Amusement Park.
    Ignored by the ending goals (they cover whole routes)."""
    display_name = "Story Chapter"
    range_start = 1
    range_end = 17
    default = 4


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


class QuestChecks(DefaultOnToggle):
    """Completing a side quest sends a check ("Quest: <name>"). Quests that can be missed never hold an
    important item, and no quest holds one when route C/D is played. The game still gives its own reward."""
    display_name = "Quest Checks"


class EndingChecks(DefaultOnToggle):
    """Each main ending reached before the goal is a check ("Ending A", "Ending B", and "Ending C" / "Ending D"
    when the goal is ending E). The ending that is the goal itself is not a check. Joke endings are never
    checks."""
    display_name = "Ending Checks"


class RandomizedAbilities(OptionSet):
    """2B's abilities locked at the start and unlocked by an Archipelago item. Nothing is locked during the
    prologue/tutorial. Add "Pod Fire" and "Pod Program" for a pod-less start."""
    display_name = "Randomized Abilities"
    valid_keys = {"Double Jump", "Air Dash", "Ground Evade", "Pod Fire", "Light Attack", "Heavy Attack", "Pod Program"}
    default = frozenset({"Double Jump", "Air Dash", "Ground Evade"})


class TrapPercentage(Range):
    """Percentage of filler items replaced by traps (damage, 10% money loss, enemy spawn, system failures)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 20


class DamageTrapPercent(Range):
    """Share of max HP removed by a Damage Trap. A Heavy Damage Trap removes twice as much (capped at 90%).
    A trap never kills unless lethal_traps is on."""
    display_name = "Damage Trap Percent"
    range_start = 5
    range_end = 50
    default = 20


class LethalTraps(Toggle):
    """Off: a damage trap always leaves you at 1 HP at worst. On: a damage trap kills you when it removes
    more HP than you have left (a real death, with the game's own death screen)."""
    display_name = "Lethal Traps"


class EnemyTrapEnemies(Choice):
    """Enemies spawned by an Enemy Trap: basic (small machines only) or random (small machines plus the
    medium machine types of the area). Bosses and big machines are never copied. When the area has no
    suitable enemy, or is already crowded, the trap deals damage instead."""
    display_name = "Enemy Trap Enemies"
    option_basic = 0
    option_random = 1
    default = 0


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


class PodPrograms(DefaultOnToggle):
    """The 16 Pod programs other than the starting laser (Mirage, Hammer, Blade, Wire, Scanner...) are
    Archipelago items found in the multiworld. The ones the game hands out normally are still given."""
    display_name = "Pod Programs"


class PodProgramChecks(Range):
    """Pod programs you get in the game itself (shop, quests, pickups) each send a check
    ("Pod Program Found #n") and are taken back, like weapons: you only keep the programs the multiworld
    sends you. These checks never hold an important item. 0 = the game's programs are left alone.
    Ignored when pod_programs is off."""
    display_name = "Pod Program Checks"
    range_start = 0
    range_end = 16
    default = 4


class StarterKit(DefaultOnToggle):
    """Start with a few healing items, one Melee Attack Up (L) and one Melee Defense Up (L). The start of the
    game is the hardest part and the first wall is the Amusement Park boss. You also get a supply drop once
    when you reach the two hard sections you cannot come back from: the boss rush at the end of route A
    (chapter 10) and the first sequence of route C/D (chapter 11)."""
    display_name = "Starter Kit"


class ItemChecks(Toggle):
    """Off by default. If on: the first pickup of each material sends an "Item: <name>" check."""
    display_name = "Item Checks"


class AreaLocks(Choice):
    """Big areas of the game are closed until you receive their Pass: walking in puts you back where you were,
    like an invisible wall. The story cannot go on without the Pass of the next area.
    up_to_forest: Desert Zone, Amusement Park, Pascal's Village, Forest Zone.
    all: also Flooded City and Abandoned Factory. These two come after chapter 7, when side quests are closed, so
    waiting for their Pass leaves little to do.
    Only the areas played before your goal get a Pass."""
    display_name = "Area Locks"
    option_off = 0
    option_up_to_forest = 1
    option_all = 2
    alias_false = 0
    alias_true = 2
    default = 1


class RouteLocks(DefaultOnToggle):
    """Route B needs the "Route B Access" item and route C/D the "Route C/D Access" item. If you finish a route
    without the item of the next one, the client takes you back to the start of chapter 7 of the route you just
    finished, where you are free to keep doing checks; when the item arrives it takes you to the start of the new
    route. Only used when your goal goes past ending A."""
    display_name = "Route Locks"


class ChapterLocks(DefaultOnToggle):
    """In routes B and C/D, each big chapter after the first one of the route needs one more key ("B Chapter Key",
    "C/D Chapter Key"). Without enough keys the client takes you back to the start of the last part of the
    previous chapter; when the key arrives it takes you to the start of the chapter you were waiting for.
    Route A has no chapter keys: its areas are already closed by the Passes."""
    display_name = "Chapter Locks"


class TowerKeys(DefaultOnToggle):
    """Route C/D: the three Access Keys that open the Tower (Forest, Ocean, Park) come from the multiworld. The
    client takes back the ones the game gives you and hands them over when they arrive. Without the three keys
    the Tower door cannot be hacked. Only used when your goal reaches the Tower (ending C/D or E)."""
    display_name = "Tower Keys"


class SelfDestructTrap(Choice):
    """How often the Self-Destruct Trap shows up among the traps. It leaves you at 1 HP, so one hit taken at the
    same moment kills you. rare: four times less often than each other trap."""
    display_name = "Self-Destruct Trap"
    option_off = 0
    option_rare = 1
    option_normal = 2
    default = 1


class FishChecks(Toggle):
    """Off by default. If on: the first catch of each of the 41 fish species sends a "Fish: <name>" check.
    These checks never hold an important item (fishing is slow and some species are far into the game)."""
    display_name = "Fish Checks"


class GagEndingChecks(Toggle):
    """Off by default. If on: each joke ending (F to Z) of the routes you play sends an "Ending <letter>" check
    the first time you get it. These checks never hold an important item."""
    display_name = "Gag Ending Checks"


class Goal(Choice):
    """Victory condition, which also sets how much of the game has checks.
    story_progress: finish chapter `story_chapter` of route `story_route` (short game, adjustable).
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
    story_route: StoryRoute
    story_chapter: StoryChapter
    weapon_checks: WeaponChecks
    item_checks: ItemChecks
    fish_checks: FishChecks
    gag_ending_checks: GagEndingChecks
    ap_items: ApItems
    ap_items_per_area: ApItemsPerArea
    access_point_checks: AccessPointChecks
    quest_checks: QuestChecks
    ending_checks: EndingChecks
    shop_checks: ShopChecks
    shop_price: ShopPrice
    chest_checks: ChestChecks
    max_level_check: MaxLevelCheck
    trap_percentage: TrapPercentage
    damage_trap_percent: DamageTrapPercent
    lethal_traps: LethalTraps
    enemy_trap_enemies: EnemyTrapEnemies
    self_destruct_trap: SelfDestructTrap
    pod_programs: PodPrograms
    pod_program_checks: PodProgramChecks
    starter_kit: StarterKit
    randomized_abilities: RandomizedAbilities
    area_locks: AreaLocks
    route_locks: RouteLocks
    chapter_locks: ChapterLocks
    tower_keys: TowerKeys
    goal: Goal
    death_link: DeathLink
