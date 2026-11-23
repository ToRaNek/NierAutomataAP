from nier_automata.game.game import backup_saves


def test_backup_copies_save_files(tmp_path):
    src = tmp_path / "saves"
    src.mkdir()
    (src / "SlotData_0.dat").write_bytes(b"save0")
    (src / "GameData.dat").write_bytes(b"gd")
    (src / "autre.txt").write_text("x")
    dst = backup_saves(src, tmp_path / "bk")
    assert sorted(p.name for p in dst.iterdir()) == ["GameData.dat", "SlotData_0.dat"]
    assert (dst / "SlotData_0.dat").read_bytes() == b"save0"


def test_backup_nothing_to_copy(tmp_path):
    assert backup_saves(tmp_path, tmp_path / "bk") is None
