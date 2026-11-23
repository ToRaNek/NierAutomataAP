import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
import nier_ap_launcher as L  # noqa: E402


def test_find_archipelago_first_valid(tmp_path):
    bad = tmp_path / "nope"
    good = tmp_path / "ap"
    good.mkdir()
    (good / "ArchipelagoLauncher.exe").write_bytes(b"")
    assert L.find_archipelago([str(bad), "", str(good)]) == good
    assert L.find_archipelago([str(bad)]) is None


def test_needs_install_only_when_different(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"v2")
    assert L.needs_install(a, b)            # absent
    b.write_bytes(b"v1")
    assert L.needs_install(a, b)            # different
    b.write_bytes(b"v2")
    assert not L.needs_install(a, b)        # identique
