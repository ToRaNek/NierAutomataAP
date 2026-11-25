from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .data import worlddb as db
from .data.areas import AREA_PASSES, pass_for_region, passes_in_scope
from .data.items_data import FILLER_ITEMS, FUNDS_ITEMS, MATERIALS, POD_PROGRAMS, STARTER_KIT, TRAP_ITEMS
from .data.tables import (
    SHOP_PLACES_ORDER, SHOP_REGION, item_location, item_name_to_id, level_location, location_name_to_id,
    ending_location, pool_weapon_count, program_location, quest_excluded, shop_location, shop_missable, weapon_location,
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
    item_name_groups = {"Weapons": set(WEAPONS), "Area Passes": set(AREA_PASSES)}

    scope: db.Scope
    pool_weapons: list

    def generate_early(self) -> None:
        o = self.options
        self.scope = db.make_scope(
            goal=o.goal.value, story_checks=self._story_checks(), chest_checks=bool(o.chest_checks),
            ap_items_per_area=o.ap_items_per_area.value if o.ap_items else 0,
            access_point_checks=bool(o.access_point_checks), quest_checks=bool(o.quest_checks),
            weapon_checks=o.weapon_checks.value, max_level_check=o.max_level_check.value,
            item_checks=bool(o.item_checks))
        self.scope.program_checks = o.pod_program_checks.value if o.pod_programs else 0
        if o.ending_checks:
            self.scope.endings = db.ending_checks(self.scope.goal, self.scope.regions)
        self.passes = passes_in_scope(self.scope.regions) if o.area_locks else []
        self.spots = self._spots()
        abilities = len(o.randomized_abilities.value)
        open_locs = sum(1 for _, _, excluded, _ in self.spots if not excluded)
        candidates = sorted(set(WEAPONS) - STARTING_WEAPONS)
        n = pool_weapon_count(max(0, open_locs - abilities - len(self.passes)), len(self.spots), len(candidates))
        self.pool_weapons = self.random.sample(candidates, n)

    def _story_checks(self) -> int:
        o = self.options
        return db.chapters_until("ABC"[o.story_route.value], o.story_chapter.value)

    def _spots(self) -> list[tuple[str, str, bool, list]]:
        """(nom, region, exclu, capacites requises) de chaque check de cette partie."""
        s, regions = self.scope, set(self.scope.regions)
        out = [(db.CHAPTERS[i]["name"], db.CHAPTERS[i]["region"], False, []) for i in range(s.chapters)]
        for table, idx in ((db.CHESTS, s.chests), (db.PICKUPS, s.pickups), (db.ACCESS_POINTS, s.access_points),
                           (db.QUESTS, s.quests)):
            out += [(table[i]["name"], table[i]["region"],
                     self._quest_excluded(table[i]) if table is db.QUESTS else bool(table[i].get("excluded")),
                     table[i].get("needs", [])) for i in sorted(idx)]
        out += [(ending_location(e), db.ENDING_REGION[e], False, []) for e in s.endings]
        out += [(level_location(n), db.level_region(n), False, []) for n in range(2, s.max_level + 1)]
        for place in SHOP_PLACES_ORDER:
            if SHOP_REGION[place] in regions:
                out += [(shop_location(place, k), SHOP_REGION[place], shop_missable(place, s.regions), [])
                        for k in range(1, self.options.shop_checks.value + 1)]
        # peuvent etre inatteignables (peu d'armes par route) : jamais d'objet important
        out += [(weapon_location(n), s.regions[0], True, []) for n in range(1, s.weapon_checks + 1)]
        out += [(program_location(n), s.regions[0], True, []) for n in range(1, s.program_checks + 1)]
        if s.item_checks:
            out += [(item_location(m), s.regions[0], True, []) for m in MATERIALS]
        return out

    def _quest_excluded(self, quest: dict) -> bool:
        """Avec les zones verrouillees, une quete de la route A peut envoyer dans une zone encore fermee
        (11B's Memento, donnee au camp, se finit dans l'usine) : elle ne recoit jamais d'objet important."""
        return quest_excluded(quest, self.scope.regions) or (bool(self.passes) and quest["region"].startswith("A"))

    def create_regions(self) -> None:
        player, regions = self.player, self.scope.regions
        menu = Region("Menu", player, self.multiworld)
        by_name = {r: Region(r, player, self.multiworld) for r in regions}
        self.multiworld.regions += [menu, *by_name.values()]
        menu.connect(by_name[regions[0]])
        weapons = len(self.pool_weapons)
        for i in range(1, len(regions)):
            need = db.required_weapons(i, len(regions), weapons)
            area_pass = pass_for_region(regions[i]) if self.passes else None   # zone fermee sans son Pass
            rule = None
            if need or area_pass:
                rule = (lambda state, n=need, k=area_pass: state.has_group("Weapons", player, n)
                        and (k is None or state.has(k, player)))
            by_name[regions[i - 1]].connect(by_name[regions[i]], rule=rule)
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
        if name in WEAPONS or name in AREA_PASSES or name in self.options.randomized_abilities.value:
            cls = ItemClassification.progression     # armes : logique de combat ; capacites : acces
        elif name in POD_PROGRAMS:
            cls = ItemClassification.useful
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
        pool += [self.create_item(k) for k in self.passes]
        if self.options.pod_programs:
            # jamais plus que la place restante hors checks exclus (les "useful" n'y vont pas)
            room = sum(1 for _, _, excluded, _ in self.spots if not excluded) - len(pool)
            programs = self.random.sample(sorted(POD_PROGRAMS), max(0, min(len(POD_PROGRAMS), room // 2)))
            pool += [self.create_item(p) for p in programs]
        traps = list(TRAP_ITEMS)
        for _ in range(len(self.spots) - len(pool)):
            if self.random.randint(1, 100) <= self.options.trap_percentage.value:
                pool.append(self.create_item(self.random.choice(traps)))
            else:
                pool.append(self.create_item(self.get_filler_item_name()))
        self.multiworld.itempool += pool
        if self.options.starter_kit:
            for name in STARTER_KIT:
                self.multiworld.push_precollected(self.create_item(name))

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self) -> dict:
        o = self.options
        return {
            "goal": o.goal.value,
            "story_checks": self._story_checks(),
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
            "starter_kit": bool(o.starter_kit),
            "damage_trap_percent": o.damage_trap_percent.value,
            "lethal_traps": bool(o.lethal_traps),
            "enemy_trap_enemies": o.enemy_trap_enemies.current_key,
            "ending_checks": bool(o.ending_checks),
            "pod_program_checks": self.scope.program_checks,
            "area_passes": list(self.passes),
            "death_link": bool(o.death_link),
        }
