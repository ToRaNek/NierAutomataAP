from nier_automata.data.abilities import ABILITY_PATCHES
from nier_automata.game.abilities import AbilityLock
from nier_automata.game.memory import FakeMemory

DJ, DJ2 = ABILITY_PATCHES["Double Jump"]
AD, = ABILITY_PATCHES["Air Dash"]


def mem_with_originals():
    m = FakeMemory()
    for patches in ABILITY_PATCHES.values():
        for p in patches:
            m.write(m.base + p.rva, p.original)
    return m


def test_patches_verified_in_game_v104():
    assert (DJ.rva, DJ.original, DJ.locked) == (0x47E357, b"\x02", b"\x01")
    assert AD.rva == 0x47E483
    assert AD.original == bytes.fromhex("0f8562020000")
    assert AD.locked == bytes.fromhex("e96302000090")


def test_locks_abilities_not_received():
    m = mem_with_originals()
    AbilityLock(m, randomized={"Double Jump", "Air Dash"}).sync(received=set())
    assert m.read(m.base + DJ.rva, 1) == DJ.locked
    assert m.read(m.base + DJ2.rva, 1) == DJ2.locked
    assert m.read(m.base + AD.rva, 6) == AD.locked


def test_unlocks_when_received():
    m = mem_with_originals()
    lock = AbilityLock(m, randomized={"Double Jump", "Air Dash"})
    lock.sync(received=set())
    lock.sync(received={"Double Jump"})
    assert m.read(m.base + DJ.rva, 1) == DJ.original
    assert m.read(m.base + AD.rva, 6) == AD.locked


def test_not_randomized_never_touched():
    m = mem_with_originals()
    AbilityLock(m, randomized={"Air Dash"}).sync(received=set())
    assert m.read(m.base + DJ.rva, 1) == DJ.original


def test_unexpected_bytes_not_overwritten():
    m = mem_with_originals()
    m.write(m.base + AD.rva, b"\xcc" * 6)  # autre version / autre mod : ne pas ecrire
    AbilityLock(m, randomized={"Air Dash"}).sync(received=set())
    assert m.read(m.base + AD.rva, 6) == b"\xcc" * 6


def test_unlock_all_restores_originals():
    m = mem_with_originals()
    lock = AbilityLock(m, randomized={"Double Jump", "Air Dash"})
    lock.sync(received=set())
    lock.unlock_all()
    assert m.read(m.base + DJ.rva, 1) == DJ.original
    assert m.read(m.base + AD.rva, 6) == AD.original


def test_evade_patch_verified_in_game_v104():
    ev, = ABILITY_PATCHES["Evade"]
    # debut du bloc "passer en etat esquive 0x12" -> jmp vers "aucune action" (bloque esquive sol/air + sprint)
    assert (ev.rva, ev.original, ev.locked) == (0x47E6BB, bytes.fromhex("488b"), bytes.fromhex("eb2e"))


def mem_with_evade():
    m = mem_with_originals()
    return m


def test_ground_evade_locked_only_on_ground():
    m = mem_with_evade()
    ev, = ABILITY_PATCHES["Evade"]
    lock = AbilityLock(m, randomized={"Ground Evade"})
    lock.sync(received=set(), grounded=True)
    assert m.read(m.base + ev.rva, 2) == ev.locked
    lock.sync(received=set(), grounded=False)   # en l'air : l'esquive aerienne reste possible
    assert m.read(m.base + ev.rva, 2) == ev.original


def test_ground_evade_received_never_locked():
    m = mem_with_evade()
    ev, = ABILITY_PATCHES["Evade"]
    AbilityLock(m, randomized={"Ground Evade"}).sync(received={"Ground Evade"}, grounded=True)
    assert m.read(m.base + ev.rva, 2) == ev.original


def test_ground_evade_unknown_grounding_leaves_unlocked():
    m = mem_with_evade()
    ev, = ABILITY_PATCHES["Evade"]
    AbilityLock(m, randomized={"Ground Evade"}).sync(received=set(), grounded=None)
    assert m.read(m.base + ev.rva, 2) == ev.original


def test_pod_fire_patch_verified_in_game_v104():
    pf, = ABILITY_PATCHES["Pod Fire"]
    # call 0x49EA20 (bouton de tir) -> xor eax,eax ; nop3 : le bouton de tir du Pod lit "non presse"
    assert (pf.rva, pf.original, pf.locked) == (0x4306CF, bytes.fromhex("e84ce30600"), bytes.fromhex("31c00f1f00"))
