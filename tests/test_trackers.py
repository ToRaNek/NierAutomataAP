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


def test_story_new_code_counts():
    s = st()
    t = StoryTracker(s, max_count=3)
    assert t.check("00_60_A_RobotM_Pro_Tutorial") == 1
    assert t.check("00_60_A_Other_Section") is None  # meme code
    assert t.check("10_AB_City") == 2


def test_story_ignores_menu():
    t = StoryTracker(st(), max_count=3)
    assert t.check("SIGNIN") is None
    assert t.check("START") is None


def test_story_capped():
    s = st()
    t = StoryTracker(s, max_count=1)
    t.check("00_60_A")
    assert t.check("10_AB_City") is None
    assert s.story_codes == {"00_60", "10_AB"}


def test_story_survives_restart():
    s = st(story_codes={"00_60"})
    assert StoryTracker(s, max_count=3).check("00_60_A") is None


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
