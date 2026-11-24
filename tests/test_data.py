from nier_automata.data.weapons import WEAPONS, STARTING_WEAPONS
from nier_automata.data.items_data import FILLER_ITEMS
from nier_automata.data.phases import phase_code
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
    from nier_automata.data.tables import MAX_STORY
    assert story_location(0) in locs and story_location(MAX_STORY - 1) in locs
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


def test_filler_never_material():
    from nier_automata.data.items_data import MATERIALS
    assert len(MATERIALS) == 71
    assert not set(FILLER_ITEMS.values()) & set(MATERIALS.values())


def test_item_location_codes_unique():
    from nier_automata.data.tables import item_location
    locs = location_name_to_id()
    assert item_location("Iron Ore") == "Item: Iron Ore"
    assert item_location("Iron Ore") in locs
    assert len(set(locs.values())) == len(locs)


def test_pool_weapon_count_never_exceeds_open_locations():
    from nier_automata.data.tables import pool_weapon_count
    # 12 histoire (non exclues) + 79 exclues : 12 armes max, le reste en filler
    assert pool_weapon_count(story_locations=12, total_locations=91, candidates=37) == 12
    assert pool_weapon_count(story_locations=40, total_locations=60, candidates=37) == 30
    assert pool_weapon_count(story_locations=3, total_locations=3, candidates=37) == 1


def test_abilities_never_locked_in_prologue_or_flight():
    from nier_automata.data.phases import abilities_allowed
    assert abilities_allowed("00_60_A_RobotM_Pro_Tutorial") is False   # tutoriel des controles
    assert abilities_allowed("00_40_A_RobotM_Prologue_STG2") is False  # vaisseau du prologue
    assert abilities_allowed("10_AB_City_STG_Test") is False           # phase vaisseau hors prologue
    assert abilities_allowed("SIGNIN") is False
    assert abilities_allowed("") is False
    assert abilities_allowed("10_AB_City") is True


def test_prologue_includes_factory_phases_beyond_00():
    from nier_automata.data.phases import abilities_allowed, is_prologue
    assert is_prologue("05_00_A_RobotM_Pro_ArmBoss_2nd")  # vu en jeu, toujours le prologue
    assert is_prologue("00_90_A_RobotM_Pro_3rdArea")
    assert not is_prologue("10_AB_City")
    assert abilities_allowed("05_00_A_RobotM_Pro_ArmBoss_2nd") is False


def test_item_checks_off_by_default():
    import ast, pathlib
    src = (pathlib.Path(__file__).parent.parent / "nier_automata" / "options.py").read_text(encoding="utf-8")
    cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "ItemChecks")
    assert [b.id for b in cls.bases] == ["Toggle"]  # Toggle = desactive par defaut


def test_shop_locations_have_codes():
    from nier_automata.data.tables import location_name_to_id, shop_location, SHOP_PLACES_ORDER, MAX_SHOP_SLOTS
    ids = location_name_to_id()
    names = [shop_location(p, k) for p in SHOP_PLACES_ORDER for k in range(1, MAX_SHOP_SLOTS + 1)]
    assert all(n in ids for n in names)
    assert len({ids[n] for n in names}) == len(names)
    assert shop_location("Resistance Camp", 1) == "Shop Resistance Camp #1"


def test_others_only_rule():
    from nier_automata.data.tables import others_only
    class It:  # objet minimal
        def __init__(self, p): self.player = p
    rule = others_only(1)
    assert rule(It(2)) and not rule(It(1))


def test_others_or_filler_rule():
    from nier_automata.data.tables import others_or_filler
    class It:
        def __init__(self, p, adv=False, useful=False): self.player, self.advancement, self.useful = p, adv, useful
    rule = others_or_filler(1)
    assert rule(It(2, adv=True)) and rule(It(1)) and not rule(It(1, adv=True)) and not rule(It(1, useful=True))
