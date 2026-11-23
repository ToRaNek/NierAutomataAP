from nier_automata.data.tables import location_name_to_id, story_location, weapon_location
from nier_automata.data.weapons import WEAPONS
from nier_automata.game.loop import tick, make_trackers
from nier_automata.game.state import ClientState

LOCS = location_name_to_id()
GOAL = "EndRoll_A"


class FakeGame:
    def __init__(self, phase="00_60_A_RobotM_Pro_Tutorial", weapons=None, capacity=99):
        self._phase = phase
        self.weapons = set(weapons or {0x42E, 0x4EC})
        self.items: dict[str, int] = {}
        self.capacity = capacity
        self.ingame = True
        self.owned = set()

    def owned_items(self):
        return set(self.owned)

    def chest_counter(self):
        return getattr(self, "chests", 0)

    def position(self):
        return (0.0, 0.0, 0.0)

    def in_game(self):
        return self.ingame

    def phase(self):
        return self._phase

    def owned_weapons(self):
        return set(self.weapons)

    def give(self, name):
        if name in WEAPONS:
            self.weapons.add(WEAPONS[name])
            return True
        if len(self.items) >= self.capacity and name not in self.items:
            return False
        self.items[name] = self.items.get(name, 0) + 1
        return True

    def remove_weapon(self, wid):
        self.weapons.discard(wid)
        return True


def setup(**kw):
    s = ClientState(seed="S", slot=1, save_slot=None,
                    ap_weapons={0x42E, 0x4EC}, **kw)  # armes de depart = deja connues
    return s, make_trackers(s, story_checks=5, weapon_checks=3)


def test_items_applied_once():
    s, tr = setup()
    g = FakeGame()
    tick(g, s, ["Small Recovery", "Type-40 Sword"], tr, GOAL)
    tick(g, s, ["Small Recovery", "Type-40 Sword"], tr, GOAL)
    assert g.items == {"Small Recovery": 1}
    assert 0x41A in g.weapons and 0x41A in s.ap_weapons
    assert s.next_item_index == 2


def test_full_inventory_retries():
    s, tr = setup()
    g = FakeGame(capacity=0)
    tick(g, s, ["Small Recovery"], tr, GOAL)
    assert s.next_item_index == 0
    g.capacity = 99
    tick(g, s, ["Small Recovery"], tr, GOAL)
    assert s.next_item_index == 1 and g.items == {"Small Recovery": 1}


def test_no_action_in_menu():
    s, tr = setup()
    g = FakeGame(phase="SIGNIN")
    g.ingame = False
    r = tick(g, s, ["Small Recovery"], tr, GOAL)
    assert r.locations == [] and not r.goal and g.items == {}


def test_first_phase_sends_story_check():
    s, tr = setup()
    boss = FakeGame(phase="05_00_A_RobotM_Pro_ArmBoss_2nd")
    r = tick(boss, s, [], tr, GOAL)
    assert r.locations == [LOCS[story_location(1)]]
    assert tick(boss, s, [], tr, GOAL).locations == []


def test_natural_weapon_removed_and_checked():
    s, tr = setup()
    g = FakeGame()
    tick(g, s, [], tr, GOAL)
    g.weapons.add(0x41A)
    tick(g, s, [], tr, GOAL)
    r = tick(g, s, [], tr, GOAL)
    assert r.locations == [LOCS[weapon_location(1)]]
    assert 0x41A not in g.weapons


def test_ap_weapon_reinjected_after_reload():
    s, tr = setup()
    g = FakeGame()
    tick(g, s, ["Type-40 Sword"], tr, GOAL)
    g.weapons.discard(0x41A)  # rechargement d'une ancienne save
    r = tick(g, s, ["Type-40 Sword"], tr, GOAL)
    assert 0x41A in g.weapons
    assert r.locations == []
    assert s.weapons_found == 0


def test_goal_sent_on_ending_phase():
    s, tr = setup(story_codes={"00_60"})  # partie deja liee
    r = tick(FakeGame(phase="EndRoll_A"), s, [], tr, GOAL)
    assert r.goal is True


def test_new_state_keeps_starting_weapons():
    from nier_automata.game.loop import new_state
    s = new_state("S", 1)
    tr = make_trackers(s, story_checks=5, weapon_checks=3)
    g = FakeGame()
    r = tick(g, s, [], tr, GOAL)
    assert g.weapons == {0x42E, 0x4EC}
    assert LOCS[weapon_location(1)] not in r.locations


from nier_automata.game.loop import due_locations


def test_due_locations_from_state():
    s, _ = setup()
    s.weapons_found = 2
    s.story_codes = {"05_00_A_RobotM_Pro_ArmBoss", "10_A_bunker_Robot_Battle", "11_A_bunker_monitorHD", "00_60"}
    due = due_locations(s, story_checks=2, weapon_checks=1)
    assert due == {LOCS[story_location(1)], LOCS[story_location(2)], LOCS[weapon_location(1)]}


class CrashingGame(FakeGame):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.crash = False

    def phase(self):
        if self.crash:
            raise OSError("jeu ferme")
        return super().phase()


def test_weapon_check_not_lost_on_oserror():
    s, tr = setup()
    g = CrashingGame()
    tick(g, s, [], tr, GOAL)
    g.weapons.add(0x41A)
    tick(g, s, [], tr, GOAL)
    g.crash = True
    try:
        tick(g, s, [], tr, GOAL)  # scan valide l'arme puis phase() plante
    except OSError:
        pass
    assert LOCS[weapon_location(1)] in due_locations(s, story_checks=5, weapon_checks=3)


def test_refuses_existing_save_on_first_link():
    from nier_automata.game.loop import new_state
    s = new_state("S", 1)
    tr = make_trackers(s, story_checks=5, weapon_checks=3)
    g = FakeGame(phase="10_AB_City", weapons={0x42E, 0x4EC, 0x3F5})
    r = tick(g, s, ["Small Recovery"], tr, GOAL)
    assert r.refused
    assert g.weapons == {0x42E, 0x4EC, 0x3F5} and g.items == {}
    assert r.locations == []


def test_accepts_new_game_on_first_link():
    from nier_automata.game.loop import new_state
    s = new_state("S", 1)
    tr = make_trackers(s, story_checks=5, weapon_checks=3)
    r = tick(FakeGame(), s, [], tr, GOAL)
    assert not r.refused


def test_tick_sends_item_location():
    s, tr = setup(story_codes={"00_60"})
    g = FakeGame()
    g.owned = {540}
    tick(g, s, [], tr, GOAL); tick(g, s, [], tr, GOAL)
    g.owned = {540, 601}
    tick(g, s, [], tr, GOAL)
    r = tick(g, s, [], tr, GOAL)
    assert LOCS["Item: Iron Ore"] in r.locations


from nier_automata.game.loop import goal_reached, GOAL_STORY, GOAL_ENDING_A


def test_goal_story_progress_reached_at_nth_route_phase():
    s, _ = setup(story_codes={"10_A_bunker_Robot_Battle", "16_AB_bunker_Order"})
    assert goal_reached(s, "x", GOAL_STORY, 5, GOAL) is True      # 16_AB = 5e phase
    s.story_codes.discard("16_AB_bunker_Order")
    assert goal_reached(s, "x", GOAL_STORY, 5, GOAL) is False


def test_goal_ending_a_needs_phase():
    s, _ = setup(story_codes={"00_60"})
    assert goal_reached(s, "EndRoll_A", GOAL_ENDING_A, 5, GOAL) is True
    assert goal_reached(s, "10_AB_City", GOAL_ENDING_A, 5, GOAL) is False


def test_tick_story_goal():
    s, tr = setup(story_codes={"00_60"})
    tr = make_trackers(s, story_checks=1, weapon_checks=3)
    r = tick(FakeGame(phase="05_00_A_RobotM_Pro_ArmBoss_2nd"), s, [], tr, GOAL, goal=GOAL_STORY)
    assert r.goal is True


def test_due_includes_chests():
    s, _ = setup()
    s.chests_found = 2
    due = due_locations(s, story_checks=5, weapon_checks=3, chest_checks=10)
    assert LOCS["Chest #1"] in due and LOCS["Chest #2"] in due and LOCS["Chest #3"] not in due


def test_due_includes_levels():
    s, _ = setup()
    s.max_level = 4
    due = due_locations(s, story_checks=5, weapon_checks=3, chest_checks=0, max_level_check=20)
    assert {LOCS["Level 2"], LOCS["Level 3"], LOCS["Level 4"]} <= due
    assert LOCS["Level 5"] not in due
    assert LOCS["Level 4"] not in due_locations(s, 5, 3, 0, max_level_check=3)


def test_first_link_accepted_anywhere_in_prologue():
    from nier_automata.game.loop import new_state
    s = new_state("S", 1)
    tr = make_trackers(s, story_checks=5, weapon_checks=3)
    r = tick(FakeGame(phase="05_00_A_RobotM_Pro_ArmBoss_2nd"), s, [], tr, GOAL)
    assert not r.refused


def test_linked_after_first_accepted_tick_even_without_story():
    s, tr = setup()
    tick(FakeGame(), s, [], tr, GOAL)              # prologue : accepte, pas de check d'histoire
    assert s.linked
    g = FakeGame(phase="30_AB_Ruined_City_ForcedLanding", weapons={0x42E, 0x4EC, 0x41A})
    assert not tick(g, s, [], tr, GOAL).refused    # arme hors depart apres le prologue : toujours accepte
