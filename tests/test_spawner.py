import struct

from nier_automata.data.enemies import ENEMY_VTABLES
from nier_automata.game.spawner import (
    MANAGER_RVA, REQUEST_CREATE_RVA, choose_enemy_type, ring_positions, set_info_bytes,
)


def test_api_addresses_verified_in_game_v104():
    assert (REQUEST_CREATE_RVA, MANAGER_RVA) == (0x745C80, 0x1029898)


def test_enemy_vtables_known():
    assert "Em0000" in ENEMY_VTABLES.values() and "Em1080" in ENEMY_VTABLES.values()


def test_choose_excludes_corpses():
    loaded = [(0x21080, "Corpse"), (0x20000, ""), (0x20000, "")]
    assert choose_enemy_type(loaded, rng=lambda xs: xs[0]) == 0x20000


def test_choose_none_when_only_corpses():
    assert choose_enemy_type([(0x21080, "Corpse")], rng=lambda xs: xs[0]) is None
    assert choose_enemy_type([], rng=lambda xs: xs[0]) is None


def test_ring_positions_around_player():
    pts = ring_positions((10.0, 2.0, 20.0), count=3, radius=4.0)
    assert len(pts) == 3
    for x, y, z in pts:
        assert abs(((x - 10) ** 2 + (z - 20) ** 2) ** 0.5 - 4.0) < 1e-4 and y == 2.0


def test_set_info_layout_copied_from_game_code():
    b = set_info_bytes((1.0, 2.0, 3.0))
    assert len(b) == 0x90
    assert struct.unpack_from("<16f", b, 0) == (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    assert struct.unpack_from("<4f", b, 0x40) == (1.0, 2.0, 3.0, 1.0)
    assert struct.unpack_from("<4f", b, 0x60) == (1.0, 1.0, 1.0, 1.0)
    assert struct.unpack_from("<iIiI", b, 0x80) == (-1, 0, 1, 0xFFFFFFFF)
