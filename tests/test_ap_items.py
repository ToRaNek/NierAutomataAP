from nier_automata.game.ap_items import (
    AP_MARKER_ITEM, CAVE_SITE_RVA, DIRECT_GIVE_RVA, DROP_CALL_RVA, MARKER_FLAG, SpotTracker,
)
from nier_automata.game.state import ClientState

SPOTS = [("30_AB", 0.0, 0.0, 0.0), ("30_AB", 100.0, 0.0, 0.0), ("40_AB", 5.0, 0.0, 5.0)]


def st(**kw):
    return ClientState(seed="S", slot=1, save_slot=None, **kw)


def test_constants_verified_in_game_v104():
    assert (CAVE_SITE_RVA, DIRECT_GIVE_RVA, DROP_CALL_RVA) == (0x5EB5B7, 0x5EB597, 0x7CA790)
    assert (MARKER_FLAG, AP_MARKER_ITEM) == (0x10000, 688)


def test_spots_to_spawn_only_near_any_phase():
    t = SpotTracker(st(), SPOTS, radius=150.0)
    assert t.to_spawn("30_AB_Ruined_City", (10.0, 0.0, 0.0)) == [0, 1, 2]
    assert t.to_spawn("40_AB_Desert", (500.0, 0.0, 0.0)) == []  # trop loin


def test_spawned_once_per_session_and_never_after_collect():
    s = st()
    t = SpotTracker(s, SPOTS, radius=150.0)
    t.mark_spawned(0)
    assert t.to_spawn("30_AB_x", (0.0, 0.0, 0.0)) == [1, 2]
    t.collected(1)
    assert s.ap_spots_collected == {1}
    t.reset_session()  # rechargement / changement de zone : on repose ce qui n'est pas ramasse
    assert t.to_spawn("30_AB_x", (0.0, 0.0, 0.0)) == [0, 2]


from nier_automata.game.ap_items import resolve_pickups


def test_pickup_resolved_when_object_gone_and_marker_received():
    tracked = {0xA: 0, 0xB: 1}
    objs = {0xA: 0, 0xB: 0x1234}           # l'objet du spot 0 a disparu
    assert resolve_pickups(tracked, objs.get, marker_received=True) == [0]
    assert resolve_pickups(tracked, objs.get, marker_received=False) == []  # disparu sans ramassage (zone quittee)


from nier_automata.game.ap_items import PICKUP_CARRIER, nearest_spawned, pickup_text


def test_pickup_carrier_is_long_name_item():
    assert PICKUP_CARRIER == 921  # "Sachet de qualite", 17 caracteres


def test_pickup_text_for_other_player():
    assert pickup_text(me=1, receiver=2, item="Cure All Status", receiver_name="Niicotine") == (
        "Pour Niicotine : ", "Cure All Status")


def test_pickup_text_for_self():
    assert pickup_text(me=1, receiver=1, item="Phoenix Sword", receiver_name="ToRaNek") == ("Pour toi : ", "Phoenix Sword")


def test_pickup_text_unknown_content():
    assert pickup_text(me=1, receiver=None, item=None, receiver_name=None) == ("", "AP Item")


def test_nearest_spawned_within_radius():
    spots = [("30_AB", 0.0, 0.0, 0.0), ("30_AB", 10.0, 0.0, 0.0)]
    assert nearest_spawned(spots, spawned={0, 1}, collected=set(), pos=(9.0, 0.0, 0.0), radius=4.0) == 1
    assert nearest_spawned(spots, spawned={0, 1}, collected={1}, pos=(9.0, 0.0, 0.0), radius=4.0) is None
    assert nearest_spawned(spots, spawned={0}, collected=set(), pos=(9.0, 0.0, 0.0), radius=4.0) is None


def test_no_respawn_after_client_restart_in_same_game_process():
    s = st()
    t = SpotTracker(s, SPOTS, radius=150.0)
    t.set_game_process(1234)
    t.mark_spawned(0)
    t2 = SpotTracker(s, SPOTS, radius=150.0)      # client relance, meme jeu
    t2.set_game_process(1234)
    assert 0 not in t2.to_spawn("30_AB_x", (0.0, 0.0, 0.0))
    t3 = SpotTracker(s, SPOTS, radius=150.0)      # jeu redemarre : on repose
    t3.set_game_process(5678)
    assert 0 in t3.to_spawn("30_AB_x", (0.0, 0.0, 0.0))


from nier_automata.game.ap_items import nearest_object, match_objects_to_spots


def test_nearest_object_uses_real_position():
    objs = {0xA: 0, 0xB: 1}
    pos_of = {0xA: (100.0, 0.0, 0.0), 0xB: (1.0, 0.0, 0.0)}.get
    assert nearest_object(objs, pos_of, (0.0, 0.0, 0.0), radius=4.0) == 0xB
    assert nearest_object(objs, pos_of, (50.0, 0.0, 0.0), radius=4.0) is None


def test_existing_marked_objects_matched_to_nearest_spot():
    spots = [("30_AB", 0.0, 0.0, 0.0), ("30_AB", 100.0, 0.0, 0.0)]
    found = {0xA: (2.0, 0.0, 0.0), 0xB: (99.0, 0.0, 0.0), 0xC: (500.0, 0.0, 0.0)}
    assert match_objects_to_spots(found, spots, collected=set(), max_dist=50.0) == {0xA: 0, 0xB: 1}


def test_spots_spawn_in_any_story_phase_but_not_prologue_or_menu():
    t = SpotTracker(st(), [("30_AB", 0.0, 0.0, 0.0)], radius=150.0)
    assert t.to_spawn("40_AB_Resistance_Camp_Leader", (10.0, 0.0, 0.0)) == [0]   # meme ville, autre phase
    assert t.to_spawn("00_60_A_RobotM_Pro_Tutorial", (10.0, 0.0, 0.0)) == []     # prologue (autre carte)
    assert t.to_spawn("SIGNIN", (10.0, 0.0, 0.0)) == []
    assert t.to_spawn("12_STG_x", (10.0, 0.0, 0.0)) == []


def test_spot_tracker_only_spawns_allowed_spots():
    t = SpotTracker(st(), SPOTS, radius=150.0, allowed={1})
    assert t.to_spawn("30_AB_Ruined_City", (10.0, 0.0, 0.0)) == [1]


def test_due_includes_collected_ap_items_in_scope():
    from nier_automata.data import worlddb as db
    from nier_automata.data.tables import location_name_to_id
    from nier_automata.game.loop import due_locations
    scope = db.make_scope(db.GOAL_STORY, 12, False, 2, False, False, 0, 0, False)
    inside = sorted(scope.pickups)[0]
    outside = next(i for i in range(len(db.PICKUPS)) if i not in scope.pickups)
    s = st(ap_spots_collected={inside, outside})
    locs = location_name_to_id()
    due = due_locations(s, scope)
    assert locs[db.PICKUPS[inside]["name"]] in due and locs[db.PICKUPS[outside]["name"]] not in due
