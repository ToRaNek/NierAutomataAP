from nier_automata.data.weapons import WEAPONS, STARTING_WEAPONS
from nier_automata.data.items_data import FILLER_ITEMS
from nier_automata.data.phases import GOAL_PHASE_PREFIX, phase_code
from nier_automata.data.tables import (
    BASE_CODE, item_name_to_id, location_name_to_id, story_location, weapon_location,
)


def test_weapon_ids_match_spreadsheet():
    assert WEAPONS["Type-40 Sword"] == 0x41A
    assert WEAPONS["Virtuous Contract"] == 0x42E
    assert WEAPONS["Virtuous Treaty"] == 0x4EC
    assert len(set(WEAPONS.values())) == len(WEAPONS) == 39


def test_starting_weapons_excluded_from_pool_names():
    assert STARTING_WEAPONS == {"Virtuous Contract", "Virtuous Treaty"}


def test_item_codes_unique_and_based():
    ids = item_name_to_id()
    assert len(set(ids.values())) == len(ids)
    assert min(ids.values()) >= BASE_CODE
    assert "Type-40 Sword" in ids and "Small Recovery" in ids


def test_location_names_and_codes_unique():
    locs = location_name_to_id()
    assert len(set(locs.values())) == len(locs)
    assert story_location(1) in locs and story_location(30) in locs
    assert weapon_location(1) in locs and weapon_location(30) in locs


def test_items_and_locations_codes_dont_overlap_meaningfully():
    assert not set(item_name_to_id().values()) & set(location_name_to_id().values())


def test_filler_has_recovery():
    assert FILLER_ITEMS["Small Recovery"] == 0


def test_phase_code_first_two_tokens():
    assert phase_code("00_60_A_RobotM_Pro_Tutorial") == "00_60"
    assert phase_code("58_AB_BossArea_Fall") == "58_AB"
    assert phase_code("SIGNIN") is None
    assert phase_code("START") is None
    assert phase_code("") is None


def test_goal_prefix():
    assert GOAL_PHASE_PREFIX == "58_AB_BossArea_Fall"
