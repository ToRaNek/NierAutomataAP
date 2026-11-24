from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .data import worlddb as db
from .data.items_data import FILLER_ITEMS, FUNDS_ITEMS, MATERIALS, TRAP_ITEMS
from .data.tables import (
    SHOP_PLACES_ORDER, SHOP_REGION, item_location, item_name_to_id, level_location, location_name_to_id,
    pool_weapon_count, quest_excluded, shop_location, shop_missable, weapon_location,
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
    tutorials = [Tutorial("Setup", "Install the apworld and start the client.", "English",
                          "setup_en.md", "setup/en", ["ToRaNek"])]


class NierAutomataWorld(World):
    """NieR:Automata (all routes). Story chapters, named chests, AP Items on the game's collection points,
    access points, shops and levels are checks; weapons and abilities are items."""
    game = GAME
    web = NierWeb()
    options_dataclass = NierAutomataOptions
    options: NierAutomataOptions
    item_name_to_id = item_name_to_id()
    location_name_to_id = location_name_to_id()
    item_name_groups = {"Weapons": set(WEAPONS)}

    scope: db.Scope
    pool_weapons: list

    def generate_early(self) -> None:
        o = self.options
        self.scope = db.make_scope(
            goal=o.goal.value, story_checks=o.story_checks.value, chest_checks=bool(o.chest_checks),
            ap_items_per_area=o.ap_items_per_area.value if o.ap_items else 0,
            access_point_checks=bool(o.access_point_checks), quest_checks=bool(o.quest_checks),
            weapon_checks=o.weapon_checks.value, max_level_check=o.max_level_check.value,
            item_checks=bool(o.item_checks))
        self.spots = self._spots()
        abilities = len(o.randomized_abilities.value)
        open_locs = sum(1 for _, _, excluded, _ in self.spots if not excluded)
        candidates = sorted(set(WEAPONS) - STARTING_WEAPONS)
        n = pool_weapon_count(max(0, open_locs - abilities), len(self.spots), len(candidates))
        self.pool_weapons = self.random.sample(candidates, n)

    def _spots(self) -> list[tuple[str, str, bool, list]]:
        """(nom, region, exclu, capacites requises) de chaque check de cette partie."""
        s, regions = self.scope, set(self.scope.regions)
        out = [(db.CHAPTERS[i]["name"], db.CHAPTERS[i]["region"], False, []) for i in range(s.chapters)]
        for table, idx in ((db.CHESTS, s.chests), (db.PICKUPS, s.pickups), (db.ACCESS_POINTS, s.access_points),
                           (db.QUESTS, s.quests)):
            out += [(table[i]["name"], table[i]["region"],
                     quest_excluded(table[i], s.regions) if table is db.QUESTS else bool(table[i].get("excluded")),
                     table[i].get("needs", [])) for i in sorted(idx)]
        out += [(level_location(n), db.level_region(n), False, []) for n in range(2, s.max_level + 1)]
        for place in SHOP_PLACES_ORDER:
            if SHOP_REGION[place] in regions:
                out += [(shop_location(place, k), SHOP_REGION[place], shop_missable(place, s.regions), [])
                        for k in range(1, self.options.shop_checks.value + 1)]
        # peuvent etre inatteignables (peu d'armes par route) : jamais d'objet important
        out += [(weapon_location(n), s.regions[0], True, []) for n in range(1, s.weapon_checks + 1)]
        if s.item_checks:
            out += [(item_location(m), s.regions[0], True, []) for m in MATERIALS]
        return out

    def create_regions(self) -> None:
        player, regions = self.player, self.scope.regions
        menu = Region("Menu", player, self.multiworld)
        by_name = {r: Region(r, player, self.multiworld) for r in regions}
        self.multiworld.regions += [menu, *by_name.values()]
        menu.connect(by_name[regions[0]])
        weapons = len(self.pool_weapons)
        for i in range(1, len(regions)):
            need = db.required_weapons(i, len(regions), weapons)
            by_name[regions[i - 1]].connect(
                by_name[regions[i]],
                rule=(lambda state, n=need: state.has_group("Weapons", player, n)) if need else None)
        locked = set(self.options.randomized_abilities.value)
        for name, region, excluded, needs in self.spots:
            loc = NierLocation(player, name, self.location_name_to_id[name], by_name[region])
            if excluded:
                loc.progress_type = LocationProgressType.EXCLUDED
            required = [a for a in needs if a in locked]
            if required:
                loc.access_rule = lambda state, req=tuple(required): state.has_all(req, player)
            by_name[region].locations.append(loc)
        goal = NierLocation(player, "Goal", None, by_name[regions[-1]])
        goal.place_locked_item(NierItem("Victory", ItemClassification.progression, None, player))
        by_name[regions[-1]].locations.append(goal)

    def create_item(self, name: str) -> NierItem:
        if name in WEAPONS or name in self.options.randomized_abilities.value:
            cls = ItemClassification.progression     # armes : logique de combat ; capacites : acces
        elif name in TRAP_ITEMS:
            cls = ItemClassification.trap
        else:
            cls = ItemClassification.filler
        return NierItem(name, cls, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(list(FILLER_ITEMS) + list(FUNDS_ITEMS))

    def create_items(self) -> None:
        pool = [self.create_item(a) for a in sorted(self.options.randomized_abilities.value)]
        pool += [self.create_item(w) for w in self.pool_weapons]
        traps = list(TRAP_ITEMS)
        for _ in range(len(self.spots) - len(pool)):
            if self.random.randint(1, 100) <= self.options.trap_percentage.value:
                pool.append(self.create_item(self.random.choice(traps)))
            else:
                pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> dict:
        o = self.options
        return {
            "goal": o.goal.value,
            "story_checks": o.story_checks.value,
            "chest_checks": bool(o.chest_checks),
            "ap_items_per_area": o.ap_items_per_area.value if o.ap_items else 0,
            "access_point_checks": bool(o.access_point_checks),
            "quest_checks": bool(o.quest_checks),
            "weapon_checks": o.weapon_checks.value,
            "max_level_check": o.max_level_check.value,
            "item_checks": bool(o.item_checks),
            "shop_checks": o.shop_checks.value,
            "shop_price": o.shop_price.value,
            "randomized_abilities": sorted(o.randomized_abilities.value),
            "death_link": bool(o.death_link),
        }
