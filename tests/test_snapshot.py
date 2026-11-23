import struct

import pytest

from nier_automata.game.snapshot import diff_u32, filter_small, exclude_offsets


def words(*vals):
    return struct.pack(f"<{len(vals)}I", *vals)


def test_diff_detects_changed_word():
    a = words(1, 2, 3)
    b = words(1, 9, 3)
    assert diff_u32(a, b, base=0x1000) == [(0x1004, 2, 9)]


def test_diff_size_mismatch_raises():
    with pytest.raises(ValueError):
        diff_u32(words(1), words(1, 2), base=0)


def test_filter_small_keeps_single_bit_flag():
    changes = [(0, 0, 0x80000000), (4, 5, 6), (8, 0, 123456)]
    assert filter_small(changes, max_delta=2) == [(0, 0, 0x80000000), (4, 5, 6)]


def test_exclude_offsets_removes_noise():
    assert exclude_offsets([(0, 1, 2), (4, 1, 2)], noise={4}) == [(0, 1, 2)]


def test_exclude_unreadable_blocks():
    from nier_automata.game.snapshot import exclude_blocks
    changes = [(0x10004, 0, 1), (0x20008, 0, 1)]
    assert exclude_blocks(changes, bad_blocks={0x10000}, block=0x10000) == [(0x20008, 0, 1)]


def test_filter_small_signed_decrement():
    assert filter_small([(0, 0, 0xFFFFFFFF)], max_delta=2) == [(0, 0, 0xFFFFFFFF)]
