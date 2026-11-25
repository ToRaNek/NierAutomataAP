from nier_automata.data.items_data import TRAP_ITEMS
from nier_automata.data.tables import item_name_to_id
from nier_automata.game.traps import damage_after_trap, funds_after_trap


def test_damage_trap_5_percent():
    assert damage_after_trap(hp=620, max_hp=1058, percent=5) == 620 - 53


def test_damage_trap_10_percent():
    assert damage_after_trap(hp=620, max_hp=1058, percent=10) == 620 - 106


def test_damage_trap_never_kills():
    assert damage_after_trap(hp=30, max_hp=1058, percent=10) == 1


def test_money_trap_takes_10_percent():
    assert funds_after_trap(1720, percent=10) == 1548
    assert funds_after_trap(0, percent=10) == 0


def test_trap_items_registered():
    ids = item_name_to_id()
    assert {"Damage Trap (5%)", "Damage Trap (10%)", "Money Trap"} <= set(TRAP_ITEMS)
    assert all(name in ids for name in TRAP_ITEMS)


def test_enemy_trap_registered():
    assert TRAP_ITEMS["Enemy Trap"] == ("spawn", 3)


def test_system_failure_traps_registered():
    ids = item_name_to_id()
    for name, ability in (("System Failure: Light Attack", "Light Attack"),
                          ("System Failure: Heavy Attack", "Heavy Attack"),
                          ("System Failure: Pod Fire", "Pod Fire")):
        assert TRAP_ITEMS[name] == ("jam:" + ability, 20) and name in ids
