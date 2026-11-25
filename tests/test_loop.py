from nier_automata.data import worlddb as db
from nier_automata.data.tables import chest_location, location_name_to_id, story_location, weapon_location
from nier_automata.data.weapons import WEAPONS
from nier_automata.game.loop import due_locations, goal_reached, make_trackers, new_state, tick
from nier_automata.game.state import ClientState

LOCS = location_name_to_id()
BOSS = "05_00_A_RobotM_Pro_ArmBoss_2nd"
CITY = "30_AB_Ruined_City_ForcedLanding"


def scope(goal=db.GOAL_STORY, story=5, chests=True, ap=2, access=True, quests=False, weapons=3, level=20,
          items=True):
    return db.make_scope(goal, story, chests, ap, access, quests, weapons, level, items)


SCOPE = scope()
FULL_A = scope(goal=db.GOAL_ENDING_A)


class FakeGame:
    def __init__(self, phase="00_60_A_RobotM_Pro_Tutorial", weapons=None, capacity=99):
        self._phase = phase
        self.weapons = set(weapons or {0x42E, 0x4EC})
        self.items: dict[str, int] = {}
        self.capacity = capacity
        self.ingame = True
        self.owned = set()
        self.pos = (0.0, 0.0, 0.0)

    def owned_items(self):
        return set(self.owned)

    def chest_counter(self):
        return getattr(self, "chests", 0)

    def position(self):
        return self.pos

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


def setup(sc=None, **kw):
    s = ClientState(seed="S", slot=1, save_slot=None,
                    ap_weapons={0x42E, 0x4EC}, **kw)  # armes de depart = deja connues
    return s, make_trackers(s, sc or SCOPE)


def test_items_applied_once():
    s, tr = setup()
    g = FakeGame()
    tick(g, s, ["Small Recovery", "Type-40 Sword"], tr)
    tick(g, s, ["Small Recovery", "Type-40 Sword"], tr)
    assert g.items == {"Small Recovery": 1}
    assert 0x41A in g.weapons and 0x41A in s.ap_weapons
    assert s.next_item_index == 2


def test_full_inventory_retries():
    s, tr = setup()
    g = FakeGame(capacity=0)
    tick(g, s, ["Small Recovery"], tr)
    assert s.next_item_index == 0
    g.capacity = 99
    tick(g, s, ["Small Recovery"], tr)
    assert s.next_item_index == 1 and g.items == {"Small Recovery": 1}


def test_no_action_in_menu():
    s, tr = setup()
    g = FakeGame(phase="SIGNIN")
    g.ingame = False
    r = tick(g, s, ["Small Recovery"], tr)
    assert r.locations == [] and not r.goal and g.items == {}


def test_chapter_reached_sends_story_checks_up_to_it():
    s, tr = setup()
    i = db.match_chapter(BOSS, "A")
    r = tick(FakeGame(phase=BOSS), s, [], tr)
    assert all(LOCS[story_location(k)] in r.locations for k in range(i + 1))   # chapitres precedents aussi
    assert tick(FakeGame(phase=BOSS), s, [], tr).locations == []


def test_story_checks_limited_to_scope():
    s, tr = setup(scope(story=2))
    r = tick(FakeGame(phase=CITY), s, [], tr)
    assert sorted(r.locations) == sorted(LOCS[story_location(k)] for k in range(2))


def test_natural_weapon_removed_and_checked():
    s, tr = setup(linked=True, chapters=set(range(5)))
    g = FakeGame()
    tick(g, s, [], tr)
    g.weapons.add(0x41A)
    tick(g, s, [], tr)
    r = tick(g, s, [], tr)
    assert r.locations == [LOCS[weapon_location(1)]]
    assert 0x41A not in g.weapons


def test_ap_weapon_reinjected_after_reload():
    s, tr = setup(linked=True)
    g = FakeGame()
    tick(g, s, ["Type-40 Sword"], tr)
    g.weapons.discard(0x41A)  # rechargement d'une ancienne save
    tick(g, s, ["Type-40 Sword"], tr)
    assert 0x41A in g.weapons
    assert s.weapons_found == 0


def test_goal_ending_a_on_credits_or_next_route():
    s, tr = setup(FULL_A, linked=True)
    assert tick(FakeGame(phase="EndRoll_A"), s, [], tr).goal is True
    s2, tr2 = setup(FULL_A, linked=True)
    assert tick(FakeGame(phase=CITY), s2, [], tr2).goal is False
    assert tick(FakeGame(phase="00_00_B_RobotM_Pro_RobotBrother"), s2, [], tr2).goal is True  # route B commencee


def test_new_state_keeps_starting_weapons():
    s = new_state("S", 1)
    tr = make_trackers(s, SCOPE)
    g = FakeGame()
    r = tick(g, s, [], tr)
    assert g.weapons == {0x42E, 0x4EC}
    assert LOCS[weapon_location(1)] not in r.locations


def test_due_locations_from_state():
    s, _ = setup()
    s.weapons_found = 2
    s.chapters = {0, 1, 7}
    due = due_locations(s, scope(story=2, weapons=1))
    assert due == {LOCS[story_location(0)], LOCS[story_location(1)], LOCS[weapon_location(1)]}


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
    tick(g, s, [], tr)
    g.weapons.add(0x41A)
    tick(g, s, [], tr)
    g.crash = True
    try:
        tick(g, s, [], tr)  # scan valide l'arme puis phase() plante
    except OSError:
        pass
    assert LOCS[weapon_location(1)] in due_locations(s, SCOPE)


def test_refuses_existing_save_on_first_link():
    s = new_state("S", 1)
    tr = make_trackers(s, SCOPE)
    g = FakeGame(phase=CITY, weapons={0x42E, 0x4EC, 0x3F5})
    r = tick(g, s, ["Small Recovery"], tr)
    assert r.refused
    assert g.weapons == {0x42E, 0x4EC, 0x3F5} and g.items == {}
    assert r.locations == []


def test_accepts_new_game_on_first_link():
    s = new_state("S", 1)
    assert not tick(FakeGame(), s, [], make_trackers(s, SCOPE)).refused


def test_tick_sends_item_location():
    s, tr = setup(linked=True)
    g = FakeGame()
    g.owned = {540}
    tick(g, s, [], tr)
    tick(g, s, [], tr)
    g.owned = {540, 601}
    tick(g, s, [], tr)
    r = tick(g, s, [], tr)
    assert LOCS["Item: Iron Ore"] in r.locations


def test_goal_story_progress_reached_at_last_chapter_of_scope():
    s, _ = setup()
    s.chapters = {0, 1, 2, 3}
    assert goal_reached(s, "x", SCOPE) is False
    s.chapters.add(4)                                   # 5e chapitre = objectif (story=5)
    assert goal_reached(s, "x", SCOPE) is True


def test_goal_ending_b_and_cd():
    s, _ = setup()
    assert goal_reached(s, "BackTitle_B", scope(goal=db.GOAL_ENDING_B)) is True
    assert goal_reached(s, "EndRoll_A", scope(goal=db.GOAL_ENDING_B)) is False
    assert goal_reached(s, "EndRoll_CD", scope(goal=db.GOAL_ENDING_CD)) is True


def test_chest_opened_near_known_chest_sends_its_check():
    s, tr = setup(FULL_A, linked=True)
    i = sorted(FULL_A.chests)[0]
    g = FakeGame(phase=CITY)
    x, y, z = db.CHESTS[i]["pos"]
    g.pos = (x + 1.0, y + 1.5, z)
    g.chests = 3
    tick(g, s, [], tr)
    tick(g, s, [], tr)             # reference (2 lectures)
    g.chests = 4
    tick(g, s, [], tr)
    r = tick(g, s, [], tr)
    assert LOCS[chest_location(i)] in r.locations and i in s.chests_opened


def test_access_point_bits_send_checks():
    s, tr = setup(FULL_A, linked=True)
    i = sorted(FULL_A.access_points)[0]
    g = FakeGame(phase=CITY)
    g.access_point_bits = lambda: {db.ACCESS_POINTS[i]["bit"]}
    r = tick(g, s, [], tr)
    assert LOCS[db.ACCESS_POINTS[i]["name"]] in r.locations


def test_due_includes_levels_capped_by_scope():
    s, _ = setup()
    s.max_level = 4
    due = due_locations(s, FULL_A)
    assert {LOCS["Level 2"], LOCS["Level 3"], LOCS["Level 4"]} <= due and LOCS["Level 5"] not in due
    assert LOCS["Level 4"] not in due_locations(s, scope(goal=db.GOAL_ENDING_A, level=3))
    assert LOCS["Level 2"] not in due_locations(s, SCOPE)       # perimetre = prologue : niveau conseille 1


def test_first_link_accepted_anywhere_in_prologue():
    s = new_state("S", 1)
    assert not tick(FakeGame(phase=BOSS), s, [], make_trackers(s, SCOPE)).refused


def test_linked_after_first_accepted_tick():
    s, tr = setup()
    tick(FakeGame(), s, [], tr)              # prologue : accepte
    assert s.linked
    g = FakeGame(phase=CITY, weapons={0x42E, 0x4EC, 0x41A})
    assert not tick(g, s, [], tr).refused    # arme hors depart apres le prologue : toujours accepte


def test_goal_from_ending_scene_states():
    # le jeu pose l'etat de scene "ending_A" (etc.) juste avant le generique : plus sur que le nom de phase
    s, _ = setup()
    assert goal_reached(s, "x", scope(goal=db.GOAL_ENDING_A), endings={"ending_A"}) is True
    assert goal_reached(s, "x", scope(goal=db.GOAL_ENDING_B), endings={"ending_A"}) is False
    assert goal_reached(s, "x", scope(goal=db.GOAL_ENDING_B), endings={"ending_A", "ending_B"}) is True
    assert goal_reached(s, "x", scope(goal=db.GOAL_ENDING_CD), endings={"ending_D"}) is True
    assert goal_reached(s, "x", scope(goal=db.GOAL_ENDING_CD), endings={"ending_B"}) is False


def test_tick_reads_endings_from_game():
    s, tr = setup(scope(goal=db.GOAL_ENDING_A), linked=True)
    g = FakeGame(phase=CITY)
    g.endings = lambda: {"ending_A"}
    assert tick(g, s, [], tr).goal is True


def test_supplies_given_once_before_the_two_hard_sections():
    # avis du testeur : les 4 boss de fin de route A (chapitre 10) et le debut de la route C (chapitre 11)
    from nier_automata.data.items_data import SUPPLY_DROPS
    sc = scope(goal=db.GOAL_ENDING_E)
    sc.supplies = True
    s, tr = setup(sc, linked=True)
    g = FakeGame(phase="160_A_Ruined_City_2B")                  # chapitre A 10-01
    g.phase_id = lambda: 0x200
    tick(g, s, [], tr)
    want = {}
    for n in SUPPLY_DROPS["A10"]:
        want[n] = want.get(n, 0) + 1
    assert g.items == want and "A10" in s.supplies_given
    tick(g, s, [], tr)
    assert g.items == want                                       # une seule fois
    off, tr2 = setup(scope(goal=db.GOAL_ENDING_E), linked=True)  # option desactivee : rien
    g2 = FakeGame(phase="160_A_Ruined_City_2B")
    g2.phase_id = lambda: 0x200
    tick(g2, off, [], tr2)
    assert g2.items == {}


def test_endings_are_checks():
    # avis du testeur : les fins doivent etre des checks
    from nier_automata.data.tables import ending_location, location_name_to_id
    locs = location_name_to_id()
    sc = scope(goal=db.GOAL_ENDING_E)
    sc.endings = db.ending_checks(sc.goal, sc.regions)
    assert sc.endings == ("A", "B", "C", "D")
    s, tr = setup(sc, linked=True)
    g = FakeGame(phase="30_AB_Ruined_City_ForcedLanding")
    g.endings = lambda: {"ending_A"}
    r = tick(g, s, [], tr)
    assert locs[ending_location("A")] in r.locations and locs[ending_location("B")] not in r.locations
    s.route = "C"                                    # route C commencee : la fin B a forcement ete vue
    g.endings = lambda: set()
    r = tick(g, s, [], tr)
    assert locs[ending_location("B")] in r.locations
    # la fin qui est l'objectif n'est pas un check ; rien si la partie s'arrete avant la fin A
    assert db.ending_checks(db.GOAL_ENDING_A, FULL_A.regions) == ()
    assert db.ending_checks(db.GOAL_ENDING_CD, sc.regions) == ("A", "B")
    assert db.ending_checks(db.GOAL_STORY, SCOPE.regions) == ()


def test_pod_programs_are_items_and_come_back_after_a_reload():
    # avis du testeur : les programmes de Pod doivent etre des objets AP, comme les armes
    from nier_automata.data.items_data import POD_PROGRAMS
    from nier_automata.data.tables import item_name_to_id
    assert "R010: Laser" not in POD_PROGRAMS and POD_PROGRAMS["R020: Mirage"] == 2002 and len(POD_PROGRAMS) == 16
    assert all(n in item_name_to_id() for n in POD_PROGRAMS)
    s, tr = setup(linked=True)
    g = FakeGame(phase="30_AB_Ruined_City_ForcedLanding")
    g.programs = set()
    g.owned_programs = lambda: set(g.programs)
    give = g.give
    g.give = lambda n: (g.programs.add(POD_PROGRAMS[n]) or True) if n in POD_PROGRAMS else give(n)
    tick(g, s, ["R020: Mirage"], tr)
    assert g.programs == {2002} and s.next_item_index == 1
    g.programs.clear()                                   # sauvegarde rechargee : programme perdu
    tick(g, s, ["R020: Mirage"], tr)
    assert g.programs == {2002}


def test_pod_program_found_in_the_game_is_a_check_and_is_taken_back():
    # comme les armes : un programme obtenu dans le jeu envoie "Pod Program Found #n" et est retire ;
    # un programme recu d'Archipelago reste
    from nier_automata.data.items_data import POD_PROGRAMS
    from nier_automata.data.tables import location_name_to_id, program_location
    locs = location_name_to_id()
    sc = scope()
    sc.program_checks = 2
    s, tr = setup(sc, linked=True)
    g = FakeGame(phase="30_AB_Ruined_City_ForcedLanding")
    g.programs = {2001}
    g.owned_programs = lambda: set(g.programs)
    g.remove_program = lambda i: g.programs.discard(i) or True
    give = g.give
    g.give = lambda n: (g.programs.add(POD_PROGRAMS[n]) or True) if n in POD_PROGRAMS else give(n)
    tick(g, s, ["R020: Mirage"], tr)
    g.programs.add(2009)                                  # achete / trouve dans le jeu
    r1 = tick(g, s, ["R020: Mirage"], tr)                 # vu une fois : on attend la confirmation
    r2 = tick(g, s, ["R020: Mirage"], tr)
    assert locs[program_location(1)] not in r1.locations and locs[program_location(1)] in r2.locations
    assert g.programs == {2001, 2002}                     # laser de depart + programme AP ; l'autre est repris
    for pid in (2010, 2011):                              # au-dela du nombre de checks : repris, sans check
        g.programs.add(pid)
        tick(g, s, ["R020: Mirage"], tr)
        r = tick(g, s, ["R020: Mirage"], tr)
    assert s.programs_found == 2 and locs[program_location(2)] in s.sent_locations
    assert g.programs == {2001, 2002}


ROUTE_B_START = "00_00_B_RobotM_Pro_RobotBrother"
ROUTE_C_START = "00_10_CD_Bunker_Hangar_2B"


def locked_scope():
    sc = scope(goal=db.GOAL_ENDING_E)
    sc.route_keys = {"B": "Route B Access", "C": "Route C/D Access"}
    return sc


def test_route_b_without_its_item_is_not_started():
    s, tr = setup(locked_scope(), linked=True, chapters=set(range(37)))
    r = tick(FakeGame(phase=ROUTE_B_START), s, [], tr)
    assert r.locked_route == "B" and s.route == "A"
    assert LOCS[story_location(37)] not in r.locations          # "Story B 01-01" pas envoye


def test_route_b_with_its_item_starts_normally():
    s, tr = setup(locked_scope(), linked=True, chapters=set(range(37)))
    r = tick(FakeGame(phase=ROUTE_B_START), s, ["Route B Access"], tr)
    assert r.locked_route == "" and s.route == "B"
    assert LOCS[story_location(37)] in r.locations


def test_route_c_needs_its_own_item():
    s, tr = setup(locked_scope(), linked=True, chapters=set(range(74)), route="B")
    assert tick(FakeGame(phase=ROUTE_C_START), s, ["Route B Access"], tr).locked_route == "C"
    assert s.route == "B"
    assert tick(FakeGame(phase=ROUTE_C_START), s, ["Route B Access", "Route C/D Access"], tr).locked_route == ""
    assert s.route == "C"


def test_no_route_lock_without_the_option():
    s, tr = setup(scope(goal=db.GOAL_ENDING_E), linked=True, chapters=set(range(37)))
    assert tick(FakeGame(phase=ROUTE_B_START), s, [], tr).locked_route == "" and s.route == "B"


def test_shared_phases_never_lock():
    s, tr = setup(locked_scope(), linked=True, chapters=set(range(6)))
    assert tick(FakeGame(phase=CITY), s, [], tr).locked_route == ""          # "_AB_" : route A
