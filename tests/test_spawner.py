from nier_automata.game.spawner import (
    STATE_ACTIVE, STATE_FINISHED, nearest_generator, spawn_requests,
)


def test_nearest_generator_within_range():
    player = (213.1, 0.9, 530.6)
    gens = [(0xA, (213.4, 5.3, 528.8)), (0xB, (150.1, -4.1, 450.4)), (0xC, None)]
    assert nearest_generator(gens, player, max_dist=50.0) == 0xA


def test_no_generator_in_range():
    assert nearest_generator([(0xB, (150.1, -4.1, 450.4))], (213.1, 0.9, 530.6), max_dist=50.0) is None


def test_spawn_requests_cycle_finished_then_active():
    # verifie en jeu : terminé -> actif fait reapparaitre les ennemis du generateur (3 ennemis)
    assert spawn_requests(STATE_ACTIVE) == [STATE_FINISHED, STATE_ACTIVE]
    assert spawn_requests(STATE_FINISHED) == [STATE_ACTIVE]
    assert spawn_requests(0) == []  # generateur non initialise : ne pas toucher


def test_state_hashes_seen_in_game():
    assert (STATE_ACTIVE, STATE_FINISHED) == (0x4B7B6E51, 0x26B80D1F)
