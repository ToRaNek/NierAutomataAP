import struct

from nier_automata.game.deathlink import DeathTracker, add_funds, MAX_FUNDS
from nier_automata.game.memory import FakeMemory, read_u32


def test_death_detected_on_transition_to_zero():
    t = DeathTracker()
    assert t.update(500) is False
    assert t.update(0) is True
    assert t.update(0) is False  # deja mort
    assert t.update(300) is False


def test_unknown_hp_ignored():
    t = DeathTracker()
    t.update(500)
    assert t.update(None) is False
    assert t.update(0) is False  # pas de valeur connue juste avant -> pas de mort comptee


def test_death_caused_by_deathlink_not_resent():
    t = DeathTracker()
    t.update(500)
    t.expect_death()
    assert t.update(0) is False


def test_first_reading_zero_is_not_a_death():
    assert DeathTracker().update(0) is False


def test_add_funds_and_cap():
    m = FakeMemory()
    m.write(m.base + 0x100, struct.pack("<I", 1720))
    add_funds(m, 0x100, 500)
    assert read_u32(m, 0x100) == 2220
    add_funds(m, 0x100, 99_999_999)
    assert read_u32(m, 0x100) == MAX_FUNDS


def test_hp_offset_is_real_value_not_copy():
    from nier_automata.game.deathlink import HP_OFFSET
    # +0x858 n'est qu'une copie recalculee a chaque image (verifie en jeu) ; vraie valeur a +0x10668
    assert HP_OFFSET == 0x10668
