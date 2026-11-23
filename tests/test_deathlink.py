import struct

from nier_automata.game.deathlink import DeathTracker, add_funds, MAX_FUNDS
from nier_automata.game.memory import FakeMemory, read_u32


def test_death_detected_on_transition_to_zero():
    t = DeathTracker()
    assert t.update(500) is False
    assert t.update(0) is False
    assert t.update(0) is True   # confirmee a la 2e lecture
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
    t.update(0)
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


def test_single_transient_zero_is_not_a_death():
    t = DeathTracker()
    t.update(500, ptr=1)
    assert t.update(0, ptr=1) is False   # 1re lecture a 0 : on attend confirmation
    assert t.update(500, ptr=1) is False  # c'etait passager
    assert t.update(0, ptr=1) is False


def test_death_confirmed_on_second_zero_same_pointer():
    t = DeathTracker()
    t.update(500, ptr=1)
    t.update(0, ptr=1)
    assert t.update(0, ptr=1) is True


def test_pointer_change_resets():
    t = DeathTracker()
    t.update(500, ptr=1)
    t.update(0, ptr=2)
    assert t.update(0, ptr=2) is False  # nouvelle entite (chargement) : pas une mort


def test_reset_when_not_in_game():
    t = DeathTracker()
    t.update(500, ptr=1)
    t.reset()
    t.update(0, ptr=1)
    assert t.update(0, ptr=1) is False
