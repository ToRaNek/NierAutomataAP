from nier_automata.game.memory import FakeMemory, read_u32, write_u32, read_cstr
from nier_automata.data.offsets import OFFSETS, detect_version


def test_u32_roundtrip():
    m = FakeMemory()
    write_u32(m, 0x100, 0xDEADBEEF)
    assert read_u32(m, 0x100) == 0xDEADBEEF
    assert m.read(m.base + 0x100, 4) == b"\xef\xbe\xad\xde"


def test_read_cstr_stops_at_nul():
    m = FakeMemory()
    m.write(m.base + 0x200, b"58_AB_BossArea_Fall\x00zz")
    assert read_cstr(m, 0x200) == "58_AB_BossArea_Fall"


def test_detect_version_unknown(tmp_path):
    exe = tmp_path / "fake.exe"
    exe.write_bytes(b"pas un vrai exe")
    assert detect_version(str(exe)) is None


def test_detect_version_known_hash(tmp_path, monkeypatch):
    import nier_automata.data.offsets as off
    exe = tmp_path / "fake.exe"
    exe.write_bytes(b"abc")
    sha_abc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    monkeypatch.setitem(off.VERSIONS, sha_abc, "v1.04")
    assert detect_version(str(exe)) == "v1.04"


def test_offsets_v104_values():
    o = OFFSETS["v1.04"]
    assert o["currentPhase"] == 0xF64B20
    assert o["itemTableStart"] == 0x148C834
    assert o["chipTableStart"] == 0x148E780
    assert o["isLoading"] == 0x13ECEB8
    assert o["isWorldLoaded"] == 0xF6E3C0
    assert o["weaponTableStart"] == 0x148E034


def test_v104_hash_registered():
    from nier_automata.data.offsets import VERSIONS
    assert VERSIONS["09854c2d45d9a72e66357e72f50cee379bb2eafe35b3d64e5e88f4eddc8613fa"] == "v1.04"


def test_offsets_found_in_game_v104():
    o = OFFSETS["v1.04"]
    assert o["funds"] == 0x148C830
    assert o["playerEntity"] == 0x1020C88
