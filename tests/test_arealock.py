from nier_automata.data.areas import AREA_PASSES, pass_for_area, pass_for_region, passes_in_scope
from nier_automata.game.arealock import AreaLock, area_lock_active

DESERT = "Desert Pass"


def walk(lock, owned, steps):
    out = None
    for t, area, pos in steps:
        out = lock.update(area, pos, t, owned)
    return out


def test_passes_cover_distinct_areas():
    seen = set()
    for _, (_, _, ids) in AREA_PASSES.items():
        assert not ids & seen
        seen |= ids
    assert 0 not in seen and 160 not in seen and 155 not in seen     # ville, camp, bunker : jamais verrouilles


def test_scope_and_regions():
    assert passes_in_scope(["A01", "A02", "A03", "A04"]) == [DESERT, "Park Pass"]
    assert passes_in_scope(["A01", "A02"]) == []
    assert pass_for_region("A03") == DESERT and pass_for_region("A02") is None
    assert pass_for_area(35) == DESERT and pass_for_area(0) is None


def test_entering_locked_area_goes_back():
    lock = AreaLock([DESERT])
    steps = [(t * 0.5, 0, (float(t), 0.0, 0.0)) for t in range(10)]
    assert walk(lock, set(), steps) is None
    back = lock.update(30, (10.0, 0.0, 0.0), 5.0, set())
    assert back is not None and back.pass_name == DESERT and back.area_id == 0
    assert back.pos == (2.0, 0.0, 0.0)          # derniere position a 8 m au moins du refus
    assert back.notify


def test_with_the_pass_nothing_happens():
    lock = AreaLock([DESERT])
    walk(lock, {DESERT}, [(0.0, 0, (0.0, 0.0, 0.0))])
    assert lock.update(30, (5.0, 0.0, 0.0), 1.0, {DESERT}) is None


def test_area_not_locked_in_this_game():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(0.0, 0, (0.0, 0.0, 0.0))])
    assert lock.update(95, (5.0, 0.0, 0.0), 1.0, set()) is None      # ville inondee : pas de Pass dans la partie


def test_no_known_position_no_teleport():
    lock = AreaLock([DESERT])
    assert lock.update(30, (5.0, 0.0, 0.0), 1.0, set()) is None
    assert lock.blocked_without_trail


def test_far_position_is_never_used():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(0.0, 0, (0.0, 0.0, 0.0))])
    assert lock.update(30, (900.0, 0.0, 0.0), 1.0, set()) is None


def test_inactive_player_is_left_alone():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(0.0, 0, (0.0, 0.0, 0.0))])
    assert lock.update(30, (5.0, 0.0, 0.0), 1.0, set(), active=False) is None


def test_message_not_repeated_every_time():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(0.0, 0, (0.0, 0.0, 0.0))])
    first = lock.update(30, (5.0, 0.0, 0.0), 2.0, set())
    lock.update(0, first.pos, 2.1, set())
    second = lock.update(30, (5.0, 0.0, 0.0), 4.0, set())
    assert first.notify and second is not None and not second.notify
    assert second.pos == first.pos


def test_wall_stays_even_if_the_game_does_not_signal_the_area_again():
    """Vu en jeu : apres un retour, le jeu ne resignale pas toujours l'entree ; le mur doit tenir quand meme."""
    lock = AreaLock([DESERT])
    walk(lock, set(), [(t * 0.5, 0, (float(t), 0.0, 0.0)) for t in range(21)])
    first = lock.update(30, (20.0, 0.0, 0.0), 11.0, set())
    assert first.pos == (12.0, 0.0, 0.0)
    assert lock.update(0, (13.0, 0.0, 0.0), 11.5, set()) is None        # encore loin du refus
    again = lock.update(0, (17.0, 0.0, 0.0), 12.0, set())               # zone toujours "ville" pour le jeu
    assert again is not None and again.pos == (12.0, 0.0, 0.0) and again.area_id == 0
    for k in range(5):                                                  # l'ancre ne se rapproche jamais
        assert lock.update(30, (20.0, 0.0, 0.0), 13.0 + k, set()).pos == (12.0, 0.0, 0.0)


def test_wall_disappears_with_the_pass_or_far_away():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(t * 0.5, 0, (float(t), 0.0, 0.0)) for t in range(21)])
    assert lock.update(30, (20.0, 0.0, 0.0), 11.0, set()) is not None
    assert lock.update(0, (19.0, 0.0, 0.0), 12.0, {DESERT}) is None     # Pass recu : on passe
    lock2 = AreaLock([DESERT])
    walk(lock2, set(), [(t * 0.5, 0, (float(t), 0.0, 0.0)) for t in range(21)])
    assert lock2.update(30, (20.0, 0.0, 0.0), 11.0, set()) is not None
    assert lock2.update(0, (-60.0, 0.0, 0.0), 30.0, set()) is None      # parti loin : mur oublie
    assert lock2._wall is None


def test_game_teleport_clears_the_trail():
    lock = AreaLock([DESERT])
    walk(lock, set(), [(0.0, 0, (0.0, 0.0, 0.0)), (0.5, 0, (500.0, 0.0, 0.0))])
    back = lock.update(30, (505.0, 0.0, 0.0), 3.0, set())
    assert back is not None and back.pos == (500.0, 0.0, 0.0)


def test_lock_only_acts_when_the_player_is_in_control():
    city = "30_AB_Ruined_City_ForcedLanding"
    assert area_lock_active(city, False, 0, 1000)
    assert area_lock_active(city, False, 2, 1000)                      # en train de courir
    assert not area_lock_active(city, True, 0, 1000)                   # cinematique
    assert not area_lock_active(city, False, 0x84, 1000)               # vol
    assert not area_lock_active(city, False, 0x42, 1000)               # piratage
    assert not area_lock_active(city, False, 0x35, 0)                  # mort
    assert not area_lock_active(city, False, None, 1000)
    assert not area_lock_active("00_60_A_RobotM_Pro_Tutorial", False, 0, 1000)    # prologue (dans l'usine)
    assert not area_lock_active("05_10_B_RobotM_ProBoss_phase1", False, 0, 1000)  # prologue de la route B
    assert not area_lock_active("90_10_AB_Ruined_City_AerialBTL_STG", False, 0, 1000)
    assert not area_lock_active("START", False, 0, 1000)
    assert not area_lock_active("", False, 0, 1000)


def test_pass_item_ids_are_stable_and_distinct():
    from nier_automata.data.tables import BASE_CODE, item_name_to_id
    ids = item_name_to_id()
    assert [ids[n] - BASE_CODE for n in AREA_PASSES] == [0x600 + i for i in range(len(AREA_PASSES))]
    assert len(set(ids.values())) == len(ids)


def test_pass_names_fit_in_a_game_notification():
    from nier_automata.game.notify import MAX_LEN
    assert all(len(n) <= MAX_LEN for n in AREA_PASSES)
