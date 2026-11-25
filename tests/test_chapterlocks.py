from nier_automata.data import chapterlocks as cl
from nier_automata.data import worlddb as db
from nier_automata.data.tables import item_name_to_id
from nier_automata.game.loop import make_trackers, tick
from nier_automata.game.notify import MAX_LEN
from nier_automata.game.state import ClientState

from test_loop import FakeGame, LOCS, scope
from nier_automata.data.tables import story_location

KEYS = dict(cl.CHAPTER_KEYS)
B03 = next(i for i, c in enumerate(db.CHAPTERS) if c["region"] == "B03")       # premier chapitre du desert, route B
C12 = next(i for i, c in enumerate(db.CHAPTERS) if c["region"] == "C12")


def test_one_key_per_big_chapter_after_the_first():
    assert cl.key_counts(db.REGIONS) == {"B": 9, "C": 6}
    assert cl.key_counts([r for r in db.REGIONS if r[0] in "AB"]) == {"B": 9}
    assert cl.key_counts([r for r in db.REGIONS if r[0] == "A"]) == {}
    assert cl.keys_needed("B01") == 0 and cl.keys_needed("B03") == 2 and cl.keys_needed("C12") == 1


def test_locked_counts_the_keys_received():
    assert cl.locked(B03, KEYS, []) and cl.locked(B03, KEYS, ["B Chapter Key"])
    assert not cl.locked(B03, KEYS, ["B Chapter Key", "B Chapter Key"])
    assert not cl.locked(B03, {}, [])
    assert not cl.locked(0, KEYS, []) and not cl.locked(40, KEYS, [])        # route A, premier chapitre de B
    assert cl.locked(C12, KEYS, ["B Chapter Key"] * 9) and not cl.locked(C12, KEYS, ["C/D Chapter Key"])


def test_park_is_the_end_of_the_previous_big_chapter_and_start_its_beginning():
    park, start = cl.park_chapter(B03), cl.start_chapter(B03)
    assert db.CHAPTERS[park]["region"] == "B02" and park == B03 - 1
    assert start == B03 and db.CHAPTERS[start]["region"] == "B03"
    for i, c in enumerate(db.CHAPTERS):
        if c["route"] in "BC" and cl.keys_needed(c["region"]) > 0:
            assert cl.park_chapter(i) in cl.STARTS and cl.start_chapter(i) in cl.STARTS


def test_starts_are_real_subphases():
    for i, (route, who, phase, sub) in cl.STARTS.items():
        assert sub in db.CHAPTERS[i]["subphases"] and route == db.CHAPTERS[i]["route"]
        assert who in ("2B", "9S", "A2") and phase in (0x100, 0x200, 0x300)


def test_key_names_fit_and_have_ids():
    ids = item_name_to_id()
    assert all(len(n) <= MAX_LEN and n in ids for n in KEYS.values())
    assert len(set(ids.values())) == len(ids)


def _setup(received_chapters):
    sc = scope(goal=db.GOAL_ENDING_E)
    sc.chapter_keys = KEYS
    s = ClientState(seed="S", slot=1, save_slot=None, ap_weapons={0x42E, 0x4EC}, linked=True, route="B",
                    chapters=set(range(received_chapters)))
    return s, make_trackers(s, sc)


def test_tick_does_not_validate_a_locked_chapter():
    sub = cl.STARTS[B03][3]
    s, tr = _setup(B03)
    r = tick(FakeGame(phase=sub), s, ["B Chapter Key"], tr)
    assert r.locked_chapter == B03 and B03 not in s.chapters
    assert LOCS[story_location(B03)] not in r.locations
    r = tick(FakeGame(phase=sub), s, ["B Chapter Key", "B Chapter Key"], tr)
    assert r.locked_chapter == -1 and B03 in s.chapters and LOCS[story_location(B03)] in r.locations


def test_tick_ignores_chapter_locks_without_the_option():
    sc = scope(goal=db.GOAL_ENDING_E)
    s = ClientState(seed="S", slot=1, save_slot=None, ap_weapons={0x42E, 0x4EC}, linked=True, route="B",
                    chapters=set(range(B03)))
    assert tick(FakeGame(phase=cl.STARTS[B03][3]), s, [], make_trackers(s, sc)).locked_chapter == -1


def test_waiting_chapter_is_saved(tmp_path):
    s = ClientState(seed="S", slot=1, save_slot=None, waiting_chapter=B03)
    s.save(tmp_path / "s.json")
    assert ClientState.load(tmp_path / "s.json").waiting_chapter == B03
