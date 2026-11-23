from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .data.items_data import FILLER_ITEMS, FUNDS_ITEMS, MATERIALS, TRAP_ITEMS
from .data.phases import GOAL_PHASE_PREFIX
from .data.tables import (
    GOAL_LOCATION, ap_item_location, chest_location, item_location, level_location, item_name_to_id, pool_weapon_count, location_name_to_id, story_location, weapon_location,
    SHOP_PLACES_ORDER, others_only, shop_location,
)
from .data.phases import ROUTE_A, ap_phase_indices
from .data.weapons import STARTING_WEAPONS, WEAPONS
from .options import NierAutomataOptions

GAME = "NieR:Automata"


def launch_client(*args):
    from .client import launch
    launch_subprocess(launch, name="NieR:Automata Client", args=args)


components.append(Component("NieR:Automata Client", func=launch_client, component_type=Type.CLIENT,
                            game_name=GAME, supports_uri=True))


class NierItem(Item):
    game = GAME


class NierLocation(Location):
    game = GAME


class NierWeb(WebWorld):
    theme = "stone"
    tutorials = [Tutorial("Setup", "Installer l'apworld et lancer le client.", "French",
                          "setup_fr.md", "setup/fr", ["ToRaNek"])]


class NierAutomataWorld(World):
    """NieR:Automata (route A). Checks : progression de l'histoire et armes trouvees."""
    game = GAME
    web = NierWeb()
    options_dataclass = NierAutomataOptions
    options: NierAutomataOptions
    item_name_to_id = item_name_to_id()
    location_name_to_id = location_name_to_id()
    item_name_groups = {"Weapons": set(WEAPONS)}

    def _ap_phase_count(self) -> int:
        """Etapes d'histoire qui ont des AP Items : jusqu'a l'objectif (story_progress) ou toute la route A."""
        return min(self.options.story_checks.value, len(ROUTE_A)) if self.options.goal.value == 0 else len(ROUTE_A)

    def _location_names(self) -> list[str]:
        names = [story_location(n) for n in range(1, self.options.story_checks.value + 1)]
        names += [weapon_location(n) for n in range(1, self.options.weapon_checks.value + 1)]
        names += [chest_location(n) for n in range(1, self.options.chest_checks.value + 1)]
        names += [level_location(n) for n in range(2, self.options.max_level_check.value + 1)]
        if self.options.item_checks:
            names += [item_location(m) for m in MATERIALS]
        if self.options.ap_items:
            names += [ap_item_location(i, k) for i in ap_phase_indices(self._ap_phase_count())
                      for k in range(1, self.options.ap_items_per_phase.value + 1)]
        names += [shop_location(p, k) for p in SHOP_PLACES_ORDER for k in range(1, self.options.shop_checks.value + 1)]
        return names

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        for name in self._location_names():
            loc = NierLocation(self.player, name, self.location_name_to_id[name], menu)
            if name.startswith(("Weapon Found", "Item: ")):
                # Peut etre inatteignable (peu d'armes en route A) : jamais d'objet de progression ici.
                loc.progress_type = LocationProgressType.EXCLUDED
            if self.multiworld.players > 1:
                loc.item_rule = others_only(self.player)  # a plusieurs : chaque check donne aux AUTRES
            menu.locations.append(loc)
        goal_name = "Goal: Story Progress" if self.options.goal.value == 0 else GOAL_LOCATION
        goal = NierLocation(self.player, goal_name, None, menu)
        goal.place_locked_item(NierItem("Victory", ItemClassification.progression, None, self.player))
        menu.locations.append(goal)
        self.multiworld.regions.append(menu)

    def create_item(self, name: str) -> NierItem:
        if name in WEAPONS or name in self.options.randomized_abilities.value:
            cls = ItemClassification.useful
        elif name in TRAP_ITEMS:
            cls = ItemClassification.trap
        else:
            cls = ItemClassification.filler
        return NierItem(name, cls, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(list(FILLER_ITEMS) + list(FUNDS_ITEMS))

    def create_items(self) -> None:
        count = len(self._location_names())
        candidates = sorted(set(WEAPONS) - STARTING_WEAPONS)
        open_locs = (self.options.story_checks.value + self.options.chest_checks.value
                     + max(0, self.options.max_level_check.value - 1))
        abilities = sorted(self.options.randomized_abilities.value)
        n = pool_weapon_count(max(0, open_locs - len(abilities)), count, len(candidates))
        weapons = self.random.sample(candidates, n)
        pool = [self.create_item(a) for a in abilities] + [self.create_item(w) for w in weapons]
        traps = list(TRAP_ITEMS)
        for _ in range(count - len(pool)):
            if self.random.randint(1, 100) <= self.options.trap_percentage.value:
                pool.append(self.create_item(self.random.choice(traps)))
            else:
                pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> dict:
        return {
            "story_checks": self.options.story_checks.value,
            "weapon_checks": self.options.weapon_checks.value,
            "item_checks": bool(self.options.item_checks),
            "chest_checks": self.options.chest_checks.value,
            "ap_items": bool(self.options.ap_items),
            "ap_items_per_phase": self.options.ap_items_per_phase.value,
            "ap_phase_count": self._ap_phase_count(),
            "shop_checks": self.options.shop_checks.value,
            "shop_price": self.options.shop_price.value,
            "max_level_check": self.options.max_level_check.value,
            "randomized_abilities": sorted(self.options.randomized_abilities.value),
            "goal": self.options.goal.value,
            "death_link": bool(self.options.death_link),
            "goal_phase_prefix": GOAL_PHASE_PREFIX,
        }
