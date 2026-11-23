from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .data.items_data import FILLER_ITEMS
from .data.phases import GOAL_PHASE_PREFIX
from .data.tables import (
    GOAL_LOCATION, item_name_to_id, location_name_to_id, story_location, weapon_location,
)
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

    def _location_names(self) -> list[str]:
        names = [story_location(n) for n in range(1, self.options.story_checks.value + 1)]
        names += [weapon_location(n) for n in range(1, self.options.weapon_checks.value + 1)]
        return names

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        for name in self._location_names():
            menu.locations.append(NierLocation(self.player, name, self.location_name_to_id[name], menu))
        goal = NierLocation(self.player, GOAL_LOCATION, None, menu)
        goal.place_locked_item(NierItem("Victory", ItemClassification.progression, None, self.player))
        menu.locations.append(goal)
        self.multiworld.regions.append(menu)

    def create_item(self, name: str) -> NierItem:
        cls = ItemClassification.useful if name in WEAPONS else ItemClassification.filler
        return NierItem(name, cls, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(list(FILLER_ITEMS))

    def create_items(self) -> None:
        count = len(self._location_names())
        candidates = sorted(set(WEAPONS) - STARTING_WEAPONS)
        weapons = self.random.sample(candidates, min(len(candidates), count // 2))
        pool = [self.create_item(w) for w in weapons]
        pool += [self.create_item(self.get_filler_item_name()) for _ in range(count - len(pool))]
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> dict:
        return {
            "story_checks": self.options.story_checks.value,
            "weapon_checks": self.options.weapon_checks.value,
            "goal_phase_prefix": GOAL_PHASE_PREFIX,
        }
