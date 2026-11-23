from nier_automata.data.tables import location_name_to_id, story_location, weapon_location
from nier_automata.data.weapons import WEAPONS
from nier_automata.game.loop import tick, make_trackers
from nier_automata.game.state import ClientState

LOCS = location_name_to_id()
GOAL = "58_AB_BossArea_Fall"


class FakeGame:
    def __init__(self, phase="00_60_A_RobotM_Pro_Tutorial", weapons=None, capacity=99):
        self._phase = phase
        self.weapons = set(weapons or {0x42E, 0x4EC})
        self.items: dict[str, int] = {}
        self.capacity = capacity
        self.ingame = True

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
    r = tick(FakeGame(), s, [], tr, GOAL)
    assert r.locations == [LOCS[story_location(1)]]
    assert tick(FakeGame(), s, [], tr, GOAL).locations == []


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
    s, tr = setup()
    r = tick(FakeGame(phase="58_AB_BossArea_Fall"), s, [], tr, GOAL)
    assert r.goal is True


def test_new_state_keeps_starting_weapons():
    from nier_automata.game.loop import new_state
    s = new_state("S", 1)
    tr = make_trackers(s, story_checks=5, weapon_checks=3)
    g = FakeGame()
    r = tick(g, s, [], tr, GOAL)
    assert g.weapons == {0x42E, 0x4EC}
    assert LOCS[weapon_location(1)] not in r.locations
