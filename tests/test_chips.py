import struct

from nier_automata.game.memory import FakeMemory
from nier_automata.game.chips import CHIP_SLOT_SIZE, ChipTable

START = 0x2000
EMPTY = 0xFFFFFFFF


def chip_raw(chip_id, type_index, level, cost, os_chip=False):
    u = 0 if os_chip else EMPTY
    return struct.pack("<12I", 0, chip_id, type_index, level, cost, EMPTY, EMPTY, EMPTY, u, u, u, 0)


def table(m, count=4):
    for i in range(count):
        m.write(m.base + START + i * CHIP_SLOT_SIZE, struct.pack("<12I", 0, EMPTY, *([0] * 10)))
    return ChipTable(m, START, count)


def test_read_chip_fields():
    m = FakeMemory()
    t = table(m)
    m.write(m.base + START, chip_raw(3007, 6, 0, 4))
    c = t.read_all()[0]
    assert (c.chip_id, c.type_index, c.level, c.cost, c.is_os) == (3007, 6, 0, 4, False)


def test_remove_os_chip_refused():
    m = FakeMemory()
    t = table(m)
    m.write(m.base + START, chip_raw(3001, 0, 0, 0, os_chip=True))
    assert t.remove(0) is False
    assert t.read_all()[0].is_os


def test_remove_normal_chip():
    m = FakeMemory()
    t = table(m)
    m.write(m.base + START + CHIP_SLOT_SIZE, chip_raw(3007, 6, 0, 4))
    assert t.remove(1) is True
    assert t.read_all() == []


def test_add_raw_writes_48_bytes_id_last():
    m = FakeMemory()
    t = table(m)
    raw = chip_raw(3007, 6, 0, 4)
    assert t.add_raw(raw) is True
    assert m.read(m.base + START, CHIP_SLOT_SIZE) == raw


def test_add_raw_full_returns_false():
    m = FakeMemory()
    t = table(m, count=1)
    t.add_raw(chip_raw(3007, 6, 0, 4))
    assert t.add_raw(chip_raw(3008, 6, 1, 5)) is False
