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


def test_story_chapter_reached_marks_previous_ones():
    from nier_automata.data import worlddb as db
    s = st()
    t = StoryTracker(s, max_count=200)
    i = t.check("30_AB_Ruined_City_ForcedLanding")
    assert db.CHAPTERS[i]["name"] == "Story A 02-01: Landing at the City Ruins"
    assert s.chapters == set(range(i + 1))                       # les chapitres precedents sont valides
    assert t.check("30_AB_Ruined_City_ForcedLanding") is None    # deja compte


def test_story_route_b_uses_its_own_chapters():
    from nier_automata.data import worlddb as db
    s = st()
    t = StoryTracker(s, max_count=200)
    t.check("30_AB_Ruined_City_ForcedLanding")
    t.check("00_00_B_RobotM_Pro_RobotBrother")                   # sous-phase propre a la route B
    assert s.route == "B"
    i = t.check("30_AB_Ruined_City_ForcedLanding")               # meme sous-phase, autre route
    assert db.CHAPTERS[i]["route"] == "B" and db.CHAPTERS[i]["chapter"] == "02-01"


def test_story_ignores_menu():
    t = StoryTracker(st(), max_count=3)
    assert t.check("SIGNIN") is None
    assert t.check("START") is None


def test_story_capped():
    s = st()
    t = StoryTracker(s, max_count=2)
    assert t.check("30_AB_Ruined_City_ForcedLanding") is None     # chapitre hors perimetre
    assert s.chapters                                             # mais memorise


def test_story_survives_restart():
    s = st(chapters={0, 1, 2, 3, 4, 5})
    assert StoryTracker(s, max_count=200).check("30_AB_Ruined_City_ForcedLanding") is None


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


def chest_at(i, dx=1.0):
    from nier_automata.data import worlddb as db
    x, y, z = db.CHESTS[i]["pos"]
    return (x + dx, y + 1.5, z)


def test_chest_first_read_is_baseline():
    s = st()
    t = ChestTracker(s, {0, 1})
    assert t.update(5, chest_at(0)) is None
    assert t.update(5, chest_at(0)) is None
    assert s.chests_opened == set()


def test_chest_increment_needs_two_reads_and_names_the_nearest_chest():
    s = st()
    t = ChestTracker(s, {0, 1})
    t.update(5, chest_at(0)); t.update(5, chest_at(0))
    assert t.update(6, chest_at(1)) is None          # 1re lecture : on attend
    assert t.update(6, chest_at(1)) == 1
    assert s.chests_opened == {1}


def test_same_chest_not_counted_twice_and_far_openings_ignored():
    s = st()
    t = ChestTracker(s, {0, 1})
    t.update(5, chest_at(0)); t.update(5, chest_at(0))
    t.update(6, chest_at(0)); assert t.update(6, chest_at(0)) == 0
    t.update(7, chest_at(0, dx=900.0))
    assert t.update(7, chest_at(0, dx=900.0)) is None      # aucun coffre connu a cet endroit
    assert s.chests_opened == {0}


def test_chest_outside_scope_is_remembered_but_not_sent():
    s = st()
    t = ChestTracker(s, {1})
    t.update(5, chest_at(0)); t.update(5, chest_at(0))
    t.update(6, chest_at(0))
    assert t.update(6, chest_at(0)) is None and s.chests_opened == {0}


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


def test_ground_pickup_does_not_count_as_chest():
    s = st()
    t = ChestTracker(s, {0, 1})
    for c in (3, 3):
        t.update(c, chest_at(0))
    t.update(4, chest_at(0), ground_pickup=True)
    assert t.update(4, chest_at(0), ground_pickup=True) is None   # ramassage au sol : pas de check
    assert s.chests_opened == set()
    t.update(5, chest_at(1))
    assert t.update(5, chest_at(1)) == 1                          # vrai coffre
