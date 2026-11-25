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


def test_vtable_hits_finds_aligned_pointers_fast():
    import struct
    from nier_automata.game.spawner import vtable_hits
    vts = {0x7FF600001000, 0x7FF600002000}
    data = bytearray(64)
    struct.pack_into("<Q", data, 8, 0x7FF600001000)
    struct.pack_into("<Q", data, 33, 0x7FF600002000)   # non aligne : ignore
    struct.pack_into("<Q", data, 48, 0x7FF600002000)
    assert vtable_hits(bytes(data), vts) == [8, 48]


def test_enough_types_stops_scan():
    from nier_automata.game.spawner import enough_types
    assert not enough_types([(0x20000, "Corpse"), (0x20000, "")], 2)
    assert enough_types([(0x20000, ""), (0x20030, "")], 2)


def test_enemy_trap_can_be_limited_to_basic_enemies():
    # avis du testeur : option "seulement des ennemis de base" ou "completement aleatoire"
    loaded = [(0x20000, ""), (0x20010, ""), (0x21000, ""), (0x28000, "")]
    seen = []
    choose_enemy_type(loaded, rng=lambda xs: seen.append(xs) or xs[0], basic_only=True)
    assert seen[-1] == [0x20000, 0x20010]
    choose_enemy_type(loaded, rng=lambda xs: seen.append(xs) or xs[0])
    assert seen[-1] == [0x20000, 0x20010]               # 0x21000 jamais essaye en jeu, 0x28000 gros : exclus
    # aucun ennemi de base charge dans la zone : rien (le piege devient des degats), jamais un boss
    assert choose_enemy_type([(0x21000, "")], rng=lambda xs: xs[0], basic_only=True) is None


def test_enemy_trap_never_clones_a_boss():
    # vu en jeu (combat contre Adam, 0x25100) : le piege clonait le boss 3 fois
    arena = [(0x21080, ""), (0x21081, ""), (0x25100, "")]
    seen = []
    assert choose_enemy_type(arena, rng=lambda xs: xs[0]) is None
    assert choose_enemy_type(arena, rng=lambda xs: xs[0], basic_only=True) is None
    assert choose_enemy_type([(0x25100, "")], rng=lambda xs: xs[0]) is None


def test_random_mode_only_uses_types_proven_in_game():
    # mode random : petites machines + types moyens essayes en jeu sans plantage ; em1101 (volant) a fait
    # planter le jeu, les types jamais essayes ne sont pas utilises
    from nier_automata.game.spawner import RANDOM_PROVEN
    zone = [(0x2000b, ""), (0x2003b, ""), (0x2010b, ""), (0x2200b, ""), (0x21101, ""), (0x23000, ""), (0x2b005, "")]
    seen = []
    choose_enemy_type(zone, rng=lambda xs: seen.append(xs) or xs[0])
    assert seen[-1] == [0x2000b, 0x2003b, 0x2010b, 0x2200b]
    assert 0x1101 not in RANDOM_PROVEN


def test_spawn_refused_when_area_is_already_crowded():
    # vu en jeu : 33 ennemis charges + 12 apparitions passent, quelques-unes de plus font planter le jeu
    from nier_automata.game.spawner import room_for_spawn
    assert room_for_spawn(loaded_count=33, count=3) and room_for_spawn(loaded_count=39, count=3)
    assert not room_for_spawn(loaded_count=40, count=3)


def test_spawned_enemies_take_the_level_of_the_area():
    # vu en jeu : les machines creees par le piege etaient au niveau 1 ; elles prennent le niveau des machines
    # du meme type deja presentes (a defaut, celui des autres ennemis de la zone)
    from nier_automata.game.spawner import spawn_level
    assert spawn_level([(0x20002, 7), (0x20002, 9), (0x20000, 12)], 0x20002) == 9
    assert spawn_level([(0x20000, 12), (0x2b005, 30)], 0x20002) == 12       # pas ce type : mediane basse de la zone
    assert spawn_level([], 0x20002) == 1
