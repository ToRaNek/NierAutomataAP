from nier_automata.game.ap_items import (
    AP_MARKER_ITEM, CAVE_SITE_RVA, DIRECT_GIVE_RVA, DROP_CALL_RVA, MARKER_FLAG, SpotTracker, pick_spots,
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


def test_pick_spots_spacing():
    path = [("30_AB_A", float(x), 0.0, 0.0) for x in range(0, 200, 5)]
    spots = pick_spots(path, min_dist=40.0, per_area=3)
    xs = [s[1] for s in spots]
    assert len(spots) == 3 and all(b - a >= 40.0 for a, b in zip(xs, xs[1:]))
    assert all(s[0] == "30_AB" for s in spots)


from nier_automata.game.ap_items import resolve_pickups


def test_pickup_resolved_when_object_gone_and_marker_received():
    tracked = {0xA: 0, 0xB: 1}
    objs = {0xA: 0, 0xB: 0x1234}           # l'objet du spot 0 a disparu
    assert resolve_pickups(tracked, objs.get, marker_received=True) == [0]
    assert resolve_pickups(tracked, objs.get, marker_received=False) == []  # disparu sans ramassage (zone quittee)


def test_due_includes_ap_items():
    from nier_automata.data.tables import location_name_to_id
    from nier_automata.game.loop import due_locations
    camp = "40_AB_Resistance_Camp_Leader"
    s = st(ap_spots_collected={0, 2}, ap_dynamic_spots=[(camp, 0.0, 0, 0), (camp, 1.0, 0, 0), (camp, 2.0, 0, 0)])
    locs = location_name_to_id()
    due = due_locations(s, 0, 0)
    assert {locs["AP Item: Camp Resistance #1"], locs["AP Item: Camp Resistance #3"]} <= due
    assert locs["AP Item: Camp Resistance #2"] not in due

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


def test_pick_spots_dedupes_positions_across_phases():
    path = [("30_AB_A", 0.0, 0.0, 0.0), ("40_AB_B", 1.0, 0.0, 0.0), ("40_AB_B", 100.0, 0.0, 0.0)]
    spots = pick_spots(path, min_dist=25.0, per_area=6)
    assert [s[1] for s in spots] == [0.0, 100.0]


from nier_automata.game.ap_items import extend_spots


def test_extend_spots_adds_spaced_new_spots_up_to_limit():
    camp = "40_AB_Resistance_Camp_Leader"
    spots = [(camp, 0.0, 0.0, 0.0)]
    found = [(1.0, 0.0, 0.0), (50.0, 0.0, 0.0), (52.0, 0.0, 0.0), (120.0, 0.0, 0.0), (300.0, 0.0, 0.0)]
    new = extend_spots(spots, found, camp, per_area=3, min_dist=25.0, offset=2.0)
    assert new == [(camp, 52.0, 0.0, 0.0), (camp, 122.0, 0.0, 0.0)]  # decales de 2 m, 3 par phase au total

def test_extend_spots_ignores_prologue_and_menus():
    assert extend_spots([], [(0.0, 0.0, 0.0)], "00_60_A_RobotM_Pro_Tutorial") == []
    assert extend_spots([], [(0.0, 0.0, 0.0)], "SIGNIN") == []

def test_extend_spots_deterministic_order():
    found = [(100.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    a = extend_spots([], found, "40_AB_Resistance_Camp_Leader")
    b = extend_spots([], list(reversed(found)), "40_AB_Resistance_Camp_Leader")
    assert a == b  # ordre de la memoire sans importance

def test_extend_spots_spreads_along_route():
    found = [(float(x), 0.0, 0.0) for x in range(0, 1000, 10)]
    new = extend_spots([], found, "40_AB_Resistance_Camp_Leader", min_dist=60.0, per_area=3)
    assert len(new) == 3                                                  # au plus 3 par phase
    assert all(b[1] - a[1] >= 60.0 for a, b in zip(new, new[1:]))
    more = extend_spots(new, found, "50_AB_Desert_temple", min_dist=60.0, per_area=3)
    assert len(more) == 3 and more[0][0] == "50_AB_Desert_temple"

from nier_automata.data.tables import ap_item_location, spot_location
from nier_automata.data.phases import ROUTE_A


def test_ap_item_locations_named_by_story_phase():
    assert ap_item_location(7, 1) == "AP Item: Camp Resistance #1"   # 8e phase (indice 7)


def test_spot_location_counts_within_its_phase():
    camp, desert = ROUTE_A[7][0], ROUTE_A[9][0]
    spots = [(camp, 0.0, 0.0, 0.0), (desert, 1.0, 0.0, 0.0), (camp, 2.0, 0.0, 0.0)]
    assert spot_location(spots, 0) == "AP Item: Camp Resistance #1"
    assert spot_location(spots, 1) == "AP Item: Desert #1"
    assert spot_location(spots, 2) == "AP Item: Camp Resistance #2"


def test_extend_spots_keyed_by_route_phase_and_limited():
    found = [(float(x), 0.0, 0.0) for x in range(0, 1000, 100)]
    new = extend_spots([], found, "40_AB_Resistance_Camp_Leader", per_area=2, phase_limit=27)
    assert [s[0] for s in new] == ["40_AB_Resistance_Camp_Leader"] * 2
    assert extend_spots([], found, "40_AB_Resistance_Camp_Leader", per_area=2, phase_limit=5) == []  # au-dela
    assert extend_spots([], found, "99_ZZ_Inconnu", per_area=2, phase_limit=27) == []              # hors route


def test_fallback_spot_near_player_when_no_ground_item():
    from nier_automata.game.ap_items import fallback_spot
    s = fallback_spot([], "76_AB_Amusement_Park_Boss_x", (10.0, 0.0, 5.0), per_area=2, phase_limit=27)
    assert s == ("76_AB_Amusement_Park_Boss", 12.0, 0.0, 5.0)
    full = [("76_AB_Amusement_Park_Boss", 0.0, 0.0, 0.0)] * 2
    assert fallback_spot(full, "76_AB_Amusement_Park_Boss_x", (10.0, 0.0, 5.0), per_area=2, phase_limit=27) is None


def test_no_ap_items_in_prologue_or_flight_phases():
    from nier_automata.data.phases import ap_phase_indices
    names = [ROUTE_A[i][1] for i in ap_phase_indices(27)]
    assert "Boss du prologue" not in names and "Vol vers la Terre" not in names
    assert not any(n.startswith("Ville engloutie") for n in names)
    assert "Camp Resistance" in names
    assert extend_spots([], [(0.0, 0.0, 0.0)], "20_AB_buker_Aerial_battle") == []


def test_fallback_fills_remaining_slots_spaced():
    from nier_automata.game.ap_items import fallback_spot
    camp = "40_AB_Resistance_Camp_Leader"
    one = [(camp, 100.0, 0.0, 0.0)]
    s = fallback_spot(one, camp, (10.0, 0.0, 5.0), per_area=2)
    assert s == (camp, 14.0, 0.0, 5.0)   # decalage croissant : 2 m + 2 m par emplacement deja la


def test_extend_spots_only_items_near_walked_path():
    camp = "40_AB_Resistance_Camp_Leader"
    path = [(0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (100.0, 0.0, 0.0)]
    found = [(52.0, 0.5, 3.0),      # au sol pres du trajet : garde
             (100.0, 20.0, 0.0),    # sur un toit (20 m au-dessus) : rejete
             (300.0, 0.0, 0.0)]     # loin du trajet : rejete
    new = extend_spots([], found, camp, per_area=3, min_dist=40.0, path=path)
    assert (camp, 54.0, 0.5, 3.0) in new
    assert all(abs(s[2] - 0.0) < 3 for s in new)        # tout au sol
    assert all(s[1] < 200 for s in new)


def test_extend_spots_uses_path_points_when_no_item():
    camp = "40_AB_Resistance_Camp_Leader"
    path = [(float(x), 0.0, 0.0) for x in range(0, 200, 5)]
    new = extend_spots([], [], camp, per_area=2, min_dist=60.0, path=path)
    assert len(new) == 2 and abs(new[1][1] - new[0][1]) >= 60.0


def test_fill_phase_from_path_ignores_spacing_when_needed():
    from nier_automata.game.ap_items import fill_from_path
    camp = "40_AB_Resistance_Camp_Leader"
    path = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]               # trajet tres court (cinematique)
    new = fill_from_path([], camp, path, per_area=2)
    assert len(new) == 2
