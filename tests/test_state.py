import json

import pytest

from nier_automata.game import state as state_mod
from nier_automata.game.state import ClientState


def make():
    return ClientState(seed="S1", slot=2, save_slot=1, next_item_index=4,
                       sent_locations={10, 11}, weapons_found=3, ap_weapons={0x41A})


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = make()
    s.save(p)
    assert ClientState.load(p) == s


def test_load_missing_returns_none(tmp_path):
    assert ClientState.load(tmp_path / "absent.json") is None


def test_state_save_is_atomic(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    make().save(p)
    original = p.read_text()

    def boom(*a, **k):
        raise RuntimeError("crash pendant l'ecriture")

    monkeypatch.setattr(state_mod.json, "dump", boom)
    s = make()
    s.weapons_found = 99
    with pytest.raises(RuntimeError):
        s.save(p)
    assert p.read_text() == original


def test_state_path_uses_seed_and_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p = state_mod.state_path("ABC", 3)
    assert p.parent == tmp_path / "NierAutomataAP"
    assert p.name == "ABC_3.json"
