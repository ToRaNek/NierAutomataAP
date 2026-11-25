import struct

from nier_automata.game.memory import FakeMemory
from nier_automata.game.inventory import (
    ACTIVE_STATUS, EMPTY, ITEM_SLOTS, WEAPON_SLOTS, item_table, weapon_table,
)

START = 0x1000


def empty_items(m, count=ITEM_SLOTS):
    for i in range(count):
        m.write(m.base + START + i * 12, struct.pack("<III", EMPTY, 0, 0))
    return item_table(m, START, count)


def test_slot_counts_from_nierhook_bounds():
    assert ITEM_SLOTS == 200
    assert WEAPON_SLOTS == 39


def test_add_to_empty_table():
    t = empty_items(FakeMemory())
    assert t.add(1, 5) is True
    s = t.find(1)
    assert s.quantity == 5 and s.status == ACTIVE_STATUS


def test_add_stacks_existing():
    t = empty_items(FakeMemory())
    t.add(1, 5)
    first = t.find(1).index
    t.add(1, 3)
    assert t.find(1).quantity == 8
    assert t.find(1).index == first


def test_add_caps_at_99():
    t = empty_items(FakeMemory())
    t.add(1, 90)
    t.add(1, 50)
    assert t.find(1).quantity == 99


def test_add_when_full_returns_false_and_writes_nothing():
    m = FakeMemory()
    t = empty_items(m, count=3)
    for i in range(3):
        t.add(100 + i, 1)
    before = m.read(m.base + START, 3 * 12)
    assert t.add(999, 1) is False
    assert m.read(m.base + START, 3 * 12) == before


def test_remove_clears_slot_to_empty():
    t = empty_items(FakeMemory())
    t.add(7, 2)
    assert t.remove(7) is True
    assert t.find(7) is None
    assert t.remove(7) is False


def test_read_all_skips_empty():
    t = empty_items(FakeMemory(), count=5)
    t.add(3, 1)
    t.add(4, 2)
    assert [s.item_id for s in t.read_all()] == [3, 4]


def test_weapon_add_uses_20_byte_slots_and_level():
    m = FakeMemory()
    for i in range(4):
        m.write(m.base + START + i * 0x14, struct.pack("<IIIII", EMPTY, 0, 0, 0, 0))
    w = weapon_table(m, START, 4)
    w.add(0x41A, 1)
    w.add(0x4D8, 2)
    raw = m.read(m.base + START + 0x14, 8)
    assert struct.unpack("<II", raw) == (0x4D8, 2)
    assert {s.item_id for s in w.read_all()} == {0x41A, 0x4D8}


def test_weapon_add_existing_does_not_duplicate():
    m = FakeMemory()
    for i in range(4):
        m.write(m.base + START + i * 0x14, struct.pack("<IIIII", EMPTY, 0, 0, 0, 0))
    w = weapon_table(m, START, 4)
    w.add(0x41A, 1)
    assert w.add(0x41A, 1) is True
    assert len(w.read_all()) == 1


def test_weapon_goes_to_its_dedicated_slot():
    m = FakeMemory()
    for i in range(WEAPON_SLOTS):
        m.write(m.base + START + i * 0x14, struct.pack("<IIIII", EMPTY, 0, 0, 0, 0))
    w = weapon_table(m, START)
    w.add(0x41A, 1)  # Type-40 Sword = slot 5 (tableur nierhook, verifie en jeu : 0x42E slot 7)
    assert w.find(0x41A).index == 5
    w.add(0x42E, 1)
    assert w.find(0x42E).index == 7


def test_owned_pod_programs_read_from_the_game_table():
    import struct
    from nier_automata.game.inventory import POD_PROGRAM_SLOTS, read_pod_programs
    from nier_automata.game.memory import FakeMemory
    m = FakeMemory()
    raw = struct.pack("<4i", 2001, 1, 2003, 1) + struct.pack("<2i", -1, 1) * (POD_PROGRAM_SLOTS - 2)
    m.write(m.base + 0x148E680, raw)
    assert read_pod_programs(m) == {2001, 2003}


def test_pod_program_added_silently_in_first_free_slot():
    # le message du jeu bloque l'ecran jusqu'a un appui, un par programme : ecriture directe a la place
    import struct
    from nier_automata.game.inventory import POD_PROGRAM_SLOTS, add_pod_program, read_pod_programs
    from nier_automata.game.memory import FakeMemory
    m = FakeMemory()
    m.write(m.base + 0x148E680, struct.pack("<2i", 2001, 1) + struct.pack("<2i", -1, 1) * (POD_PROGRAM_SLOTS - 1))
    assert add_pod_program(m, 2009) and read_pod_programs(m) == {2001, 2009}
    assert struct.unpack("<4i", m.read(m.base + 0x148E680, 16)) == (2001, 1, 2009, 1)
    assert add_pod_program(m, 2009) and read_pod_programs(m) == {2001, 2009}      # deja possede : rien
    m.write(m.base + 0x148E680, struct.pack("<2i", 2001, 1) * POD_PROGRAM_SLOTS)
    assert not add_pod_program(m, 2010)                                            # table pleine
