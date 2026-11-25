from nier_automata.data import worlddb as db
from nier_automata.data.routes import PARK, ROUTE_KEYS, START, keys_in_scope, locked_route
from nier_automata.data.tables import BASE_CODE, item_name_to_id
from nier_automata.game.notify import MAX_LEN
from nier_automata.game.state import ClientState


def test_keys_only_for_played_routes():
    assert keys_in_scope(["A01", "A10"]) == {}
    assert keys_in_scope(["A10", "B01"]) == {"B": "Route B Access"}
    assert keys_in_scope(["A10", "B01", "C11"]) == ROUTE_KEYS


def test_locked_route_is_the_first_missing_one():
    assert locked_route("A", "A", ROUTE_KEYS, set()) == ""
    assert locked_route("A", "B", ROUTE_KEYS, set()) == "B"
    assert locked_route("A", "B", ROUTE_KEYS, {"Route B Access"}) == ""
    assert locked_route("A", "C", ROUTE_KEYS, {"Route C/D Access"}) == "B"
    assert locked_route("B", "C", ROUTE_KEYS, {"Route B Access"}) == "C"
    assert locked_route("A", "B", {}, set()) == ""


def test_park_and_start_phases_exist_in_the_story_data():
    subs = {s for c in db.CHAPTERS for s in c["subphases"]}
    for table in (PARK, START):
        for route, (state, who, phase, sub) in table.items():
            assert sub in subs and who in ("2B", "9S", "A2") and phase in (0x100, 0x200, 0x300)
    assert PARK["B"][0] == "A" and PARK["C"][0] == "B"           # on attend dans la route d'avant
    assert db.next_route("A", START["B"][3]) == "B" and db.next_route("B", START["C"][3]) == "C"


def test_key_names_and_ids():
    ids = item_name_to_id()
    assert [ids[n] - BASE_CODE for n in ROUTE_KEYS.values()] == [0x680, 0x681]
    assert all(len(n) <= MAX_LEN for n in ROUTE_KEYS.values())
    assert len(set(ids.values())) == len(ids)


def test_waiting_route_is_saved(tmp_path):
    s = ClientState(seed="S", slot=1, save_slot=None, waiting_route="B")
    s.save(tmp_path / "s.json")
    assert ClientState.load(tmp_path / "s.json").waiting_route == "B"
