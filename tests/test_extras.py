from nier_automata.data import worlddb as db
from nier_automata.data.gagendings import GAG_ENDINGS, ending_from_phase, letters_in_scope, region_of
from nier_automata.data.items_data import FISH, MATERIALS, TRAP_ITEMS, trap_weights
from nier_automata.data.tables import BASE_CODE, ending_location, fish_location, item_name_to_id, location_name_to_id
from nier_automata.game.abilities import AbilityLock
from nier_automata.game.loop import due_locations, make_trackers, tick
from nier_automata.game.spawner import raised_level
from nier_automata.game.state import ClientState
from nier_automata.game.traps import Trail

from test_loop import FakeGame, scope

LOCS = location_name_to_id()


def test_new_traps_are_appended_so_old_item_ids_do_not_move():
    names = list(TRAP_ITEMS)
    assert names[:9] == ["Damage Trap", "Heavy Damage Trap", "Money Trap", "Enemy Trap",
                         "System Failure: Light Attack", "System Failure: Heavy Attack", "System Failure: Pod Fire",
                         "Self-Destruct Trap", "E-Drug Trap"]
    assert names[9:] == ["Level Up Trap", "Teleport Trap", "System Failure: Evade", "System Failure: Double Jump"]
    ids = item_name_to_id()
    assert ids["E-Drug Trap"] == BASE_CODE + 0x308 and ids["Level Up Trap"] == BASE_CODE + 0x309
    assert set(trap_weights(2)) == set(TRAP_ITEMS)


def test_level_up_adds_levels_up_to_99():
    assert raised_level(5, 10) == 15 and raised_level(95, 10) == 99
    assert raised_level(99, 10) == 0 and raised_level(0, 10) == 0 and raised_level(4000, 10) == 0


def test_trail_gives_the_position_of_some_seconds_ago():
    t = Trail()
    for k in range(60):
        t.add((float(k), 0.0, 0.0), k * 0.5)
    assert t.back((29.5, 0.0, 0.0), 30.0, 20) == (20.0, 0.0, 0.0)
    assert Trail().back((0.0, 0.0, 0.0), 1.0, 20) is None                 # rien de connu
    young = Trail()
    young.add((1.0, 0.0, 0.0), 0.0)
    assert young.back((3.0, 0.0, 0.0), 2.0, 20) == (1.0, 0.0, 0.0)        # trop recent : la plus ancienne
    far = Trail()
    far.add((0.0, 0.0, 0.0), 0.0)
    far.add((900.0, 0.0, 0.0), 1.0)                                       # chargement : l'ancienne trace est oubliee
    assert far.back((905.0, 0.0, 0.0), 30.0, 20) == (900.0, 0.0, 0.0)
    assert far.back((2000.0, 0.0, 0.0), 30.0, 20) is None                 # trop loin : pas de teleportation


class FakeMem:
    base = 0

    def __init__(self):
        from nier_automata.data.abilities import ABILITY_PATCHES
        self.data = {}
        for patches in ABILITY_PATCHES.values():
            for p in patches:
                self.data[p.rva] = p.original

    def read(self, addr, n):
        return self.data[addr][:n]

    def write(self, addr, raw):
        self.data[addr] = raw


def test_evade_failure_locks_evade_even_with_ground_evade_randomized():
    from nier_automata.data.abilities import ABILITY_PATCHES
    evade = ABILITY_PATCHES["Evade"][0]
    for randomized in (set(), {"Ground Evade"}):
        mem = FakeMem()
        lock = AbilityLock(mem, randomized)
        lock.sync({"Ground Evade"}, grounded=False, jammed={"Evade"})
        assert mem.data[evade.rva] == evade.locked
        lock.sync({"Ground Evade"}, grounded=False, jammed=set())
        assert mem.data[evade.rva] == evade.original


def test_fish_checks_are_optional_and_use_their_own_codes():
    assert len(FISH) == 41 and not set(FISH.values()) & set(MATERIALS.values())
    assert LOCS[fish_location("Arowana")] == BASE_CODE + 0x3100
    assert len(set(LOCS.values())) == len(LOCS)
    sc = scope()
    s = ClientState(seed="S", slot=1, save_slot=None, ap_weapons={0x42E, 0x4EC}, linked=True, item_baseline=set())
    g = FakeGame()
    g.owned = {FISH["Mackerel"]}
    tr = make_trackers(s, sc)
    tick(g, s, [], tr); tick(g, s, [], tr)
    assert LOCS[fish_location("Mackerel")] not in due_locations(s, sc)        # option absente : rien
    sc.fish_checks = True
    s2 = ClientState(seed="S", slot=1, save_slot=None, ap_weapons={0x42E, 0x4EC}, linked=True, item_baseline=set())
    tr2 = make_trackers(s2, sc)
    tick(g, s2, [], tr2); tick(g, s2, [], tr2)
    assert LOCS[fish_location("Mackerel")] in due_locations(s2, sc)


def test_gag_endings_follow_the_routes_played():
    assert len(GAG_ENDINGS) == 21 and "".join(GAG_ENDINGS) == "FGHIJKLMNOPQRSTUVWXYZ"
    a = [r for r in db.REGIONS if r[0] == "A"]
    assert set(letters_in_scope(a)) == {"H", "I", "J", "K", "L", "T", "U", "W"}
    assert len(letters_in_scope(db.REGIONS)) == 21
    assert region_of("W", db.REGIONS) == "A01" and region_of("G", db.REGIONS) == "B01"
    assert ending_from_phase("Ending_K") == "K" and ending_from_phase("Ending_A") is None
    assert ending_from_phase("EndRoll_A") is None and ending_from_phase("") is None
    assert LOCS[ending_location("F")] == BASE_CODE + 0xD010 and LOCS[ending_location("D")] == BASE_CODE + 0xD003


def test_gag_ending_seen_becomes_a_check_only_with_the_option():
    sc = scope(goal=db.GOAL_ENDING_E)
    s = ClientState(seed="S", slot=1, save_slot=None, linked=True, endings_seen={"K"})
    assert LOCS[ending_location("K")] not in due_locations(s, sc)
    sc.gag_endings = letters_in_scope(sc.regions)
    assert LOCS[ending_location("K")] in due_locations(s, sc)
