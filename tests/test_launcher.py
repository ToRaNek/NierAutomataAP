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


def _game(tmp_path, lib="lib"):
    d = tmp_path / lib / "steamapps" / "common" / "NieRAutomata"
    d.mkdir(parents=True)
    (d / "NieRAutomata.exe").write_bytes(b"")
    return d


def test_find_game_in_a_given_folder_or_a_steam_library(tmp_path):
    game = _game(tmp_path)
    assert L.find_game([str(game)], []) == game
    assert L.find_game(["", str(tmp_path / "nope")], []) is None
    assert L.find_game([], [str(tmp_path / "lib")]) == game               # bibliotheque de Steam elle-meme
    steam = tmp_path / "steam"
    (steam / "steamapps").mkdir(parents=True)
    other = _game(tmp_path, "games")
    vdf = '"libraryfolders"\n{\n "0" { "path" "%s" }\n "1" { "path" "%s" }\n}\n' % (
        str(steam).replace("\\", "\\\\"), str(tmp_path / "games").replace("\\", "\\\\"))
    (steam / "steamapps" / "libraryfolders.vdf").write_text(vdf, encoding="utf-8")
    assert L.find_game([], [str(steam)]) == other                         # autre bibliotheque, lue dans le vdf


def test_install_mod_never_overwrites_another_dinput8(tmp_path):
    game = _game(tmp_path)
    src = tmp_path / "dinput8.dll"
    src.write_bytes(b"MZ..NierApMod..v2")
    assert L.install_mod(src, game) == "installed" and (game / "dinput8.dll").read_bytes() == src.read_bytes()
    assert L.install_mod(src, game) == "up to date"
    (game / "dinput8.dll").write_bytes(b"MZ..NierApMod..v1")              # ancienne version du notre : remplacee
    assert L.install_mod(src, game) == "installed"
    (game / "dinput8.dll").write_bytes(b"MZ..some other mod")             # mod de quelqu'un d'autre : intact
    assert L.install_mod(src, game) == "foreign"
    assert (game / "dinput8.dll").read_bytes() == b"MZ..some other mod"
