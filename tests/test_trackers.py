from nier_automata.game.state import ClientState
from nier_automata.game.trackers import PhaseTracker, WeaponTracker


def st(**kw):
    return ClientState(seed="S", slot=1, save_slot=1, **kw)


def test_natural_weapon_counted_and_removed():
    s = st()
    t = WeaponTracker(s, max_found=5)
    assert t.scan({0x41A}) == ([], None)  # vue une 1re fois : on attend confirmation
    assert t.scan({0x41A}) == ([0x41A], 1)
    assert s.weapons_found == 1


def test_second_natural_weapon_gets_next_number():
    s = st()
    t = WeaponTracker(s, max_found=5)
    t.scan({0x41A}); t.scan({0x41A})
    t.scan({0x4D8})
    assert t.scan({0x4D8}) == ([0x4D8], 2)


def test_ap_weapon_not_counted():
    s = st(ap_weapons={0x41A})
    assert WeaponTracker(s, max_found=5).scan({0x41A}) == ([], None)
    assert s.weapons_found == 0


def test_reinjected_weapon_after_reload_not_counted():
    s = st(ap_weapons={0x41A}, weapons_found=2)
    t = WeaponTracker(s, max_found=5)
    t.scan(set())  # rechargement : l'arme AP a disparu
    assert t.scan({0x41A}) == ([], None)  # reinjectee par le client
    assert s.weapons_found == 2


def test_counter_capped_at_max_found():
    s = st(weapons_found=2)
    t = WeaponTracker(s, max_found=2)
    t.scan({0x41A})
    assert t.scan({0x41A}) == ([0x41A], None)
    assert s.weapons_found == 2


PHASES = [("Story: Engels", "00_60_A_RobotM_Pro"), ("Story: Ending A", "58_AB_BossArea_Fall")]


def test_phase_matches_prefix():
    t = PhaseTracker(PHASES)
    assert t.check("00_60_A_RobotM_Pro_Tutorial") == ["Story: Engels"]


def test_phase_check_once():
    t = PhaseTracker(PHASES)
    t.check("00_60_A_RobotM_Pro_Tutorial")
    assert t.check("00_60_A_RobotM_Pro_Tutorial") == []


def test_phase_already_sent_skipped():
    t = PhaseTracker(PHASES, already_sent={"Story: Engels"})
    assert t.check("00_60_A_RobotM_Pro_Tutorial") == []


def test_menu_phase_ignored():
    t = PhaseTracker(PHASES)
    assert t.check("START") == []
    assert t.check("SIGNIN") == []
    assert t.check("") == []


def test_is_goal():
    t = PhaseTracker(PHASES)
    assert t.is_goal("58_AB_BossArea_Fall") is True
    assert t.is_goal("00_60_A_RobotM_Pro_Tutorial") is False


from nier_automata.game.trackers import StoryTracker


def test_story_one_check_per_named_route_phase():
    s = st()
    t = StoryTracker(s, max_count=30)
    assert t.check("00_60_A_RobotM_Pro_Tutorial") is None          # prologue : pas encore le boss
    assert t.check("05_00_A_RobotM_Pro_ArmBoss_2nd") == 1          # boss du prologue
    assert t.check("30_AB_Ruined_City_ForcedLanding") == 7
    assert t.check("30_AB_Pascal_Village") == 23                    # meme code 30_AB, autre phase
    assert t.check("30_AB_Pascal_Village") is None                  # deja compte


def test_story_ignores_menu():
    t = StoryTracker(st(), max_count=3)
    assert t.check("SIGNIN") is None
    assert t.check("START") is None


def test_story_capped():
    s = st()
    t = StoryTracker(s, max_count=7)
    assert t.check("40_AB_Resistance_Camp_Leader") is None          # 8e phase > 7
    assert "40_AB_Resistance_Camp_Leader" in s.story_codes


def test_story_survives_restart():
    s = st(story_codes={"30_AB_Ruined_City_ForcedLanding"})
    assert StoryTracker(s, max_count=30).check("30_AB_Ruined_City_ForcedLanding") is None


def test_story_location_names_are_readable_and_short():
    from nier_automata.data.tables import story_location
    from nier_automata.data.phases import ROUTE_A
    assert story_location(8) == "Story: Camp Resistance"
    assert all(len(label) <= 17 for _, label in ROUTE_A)


def test_unknown_weapon_id_ignored():
    s = st()
    t = WeaponTracker(s, max_found=5)
    t.scan({0x12345})
    assert t.scan({0x12345}) == ([], None)


def test_transient_weapon_not_counted():
    s = st()
    t = WeaponTracker(s, max_found=5)
    t.scan({0x41A})          # valeur passagere pendant un chargement
    assert t.scan(set()) == ([], None)
    assert s.weapons_found == 0


def test_refound_weapon_after_reload_not_recounted():
    s = st()
    t = WeaponTracker(s, max_found=5)
    t.scan({0x3F5}); t.scan({0x3F5})          # Iron Pipe trouvee -> #1, retiree
    t.scan({0x3F5})                           # rechargement : retrouvee
    assert t.scan({0x3F5}) == ([0x3F5], None)  # retiree mais pas recomptee
    assert s.weapons_found == 1


from nier_automata.game.trackers import ItemTracker


def test_item_baseline_not_checked():
    s = st()
    t = ItemTracker(s, enabled_ids={540, 601})
    assert t.scan({540}) == []
    assert t.scan({540}) == []
    assert s.item_baseline == {540}


def test_new_material_checked_once():
    s = st()
    t = ItemTracker(s, enabled_ids={540, 601})
    t.scan({540}); t.scan({540})
    assert t.scan({540, 601}) == []
    assert t.scan({540, 601}) == [601]
    assert t.scan({540, 601}) == []
    assert s.items_found == {601}


def test_disabled_item_ignored():
    s = st()
    t = ItemTracker(s, enabled_ids={601})
    t.scan(set())
    assert t.scan({0}) == []


def test_item_transient_value_not_checked():
    s = st()
    t = ItemTracker(s, enabled_ids={540, 601})
    t.scan({540}); t.scan({540})          # baseline confirmee
    assert t.scan({540, 601}) == []       # vu une fois
    assert t.scan({540}) == []            # disparu : passager
    assert s.items_found == set()


def test_item_baseline_needs_two_identical_reads():
    s = st()
    t = ItemTracker(s, enabled_ids={540, 601})
    t.scan(set())                         # table vide pendant un chargement
    t.scan({540, 601})
    assert s.item_baseline is None or s.item_baseline == {540, 601}
    t.scan({540, 601})
    assert s.item_baseline == {540, 601}
    assert s.items_found == set()


from nier_automata.game.trackers import ChestTracker

P1 = (-554.5, 37.2, 276.8)
P2 = (-300.0, 10.0, 100.0)


def ch(s, n, code="00_80", pos=P1, t=None):
    t = t or ChestTracker(s, max_count=10)
    return t, t.update(n, code, pos)


def test_chest_first_read_is_baseline():
    s = st()
    t = ChestTracker(s, max_count=10)
    assert t.update(3, "00_80", P1) is None
    assert t.update(3, "00_80", P1) is None
    assert s.chests_found == 0


def test_chest_increment_needs_two_reads():
    s = st()
    t = ChestTracker(s, max_count=10)
    t.update(3, "00_80", P1); t.update(3, "00_80", P1)
    assert t.update(4, "00_80", P2) is None      # vu une fois
    assert t.update(4, "00_80", P2) == 1         # confirme
    assert s.chests_found == 1


def test_same_chest_after_reload_not_recounted():
    s = st()
    t = ChestTracker(s, max_count=10)
    t.update(3, "00_80", P1); t.update(3, "00_80", P1)
    t.update(4, "00_80", P2); t.update(4, "00_80", P2)
    t.update(3, "00_80", P1); t.update(3, "00_80", P1)    # rechargement : compteur redescend
    t.update(4, "00_80", P2)
    assert t.update(4, "00_80", (P2[0] + 1, P2[1], P2[2] + 1)) is None  # meme coffre (meme endroit)
    assert s.chests_found == 1


def test_chest_capped():
    s = st()
    t = ChestTracker(s, max_count=1)
    t.update(0, "00_80", P1); t.update(0, "00_80", P1)
    t.update(1, "00_80", P1); t.update(1, "00_80", P1)
    t.update(2, "00_80", P2)
    assert t.update(2, "00_80", P2) is None
    assert s.chests_found == 1


from nier_automata.game.trackers import LevelTracker


def test_level_needs_two_reads():
    s = st()
    t = LevelTracker(s)
    t.update(4)
    assert s.max_level == 1
    t.update(4)
    assert s.max_level == 4


def test_level_never_decreases_and_ignores_garbage():
    s = st(max_level=4)
    t = LevelTracker(s)
    t.update(2); t.update(2)          # rechargement d'une ancienne save
    t.update(5000); t.update(5000)    # valeur absurde (chargement)
    t.update(0); t.update(0)
    assert s.max_level == 4
