import ctypes
import socket
import struct
import threading

import pytest

from nier_automata.game import modlink as ml
from nier_automata.game.memory import FakeMemory
from nier_automata.game.spawner import _MBI, alloc, remote_call

BASE = 0x140000000
TOKEN = bytes(range(16))


class FakeMod:
    """Faux mod : meme protocole que mod/nier_ap_mod.c, au-dessus d'une FakeMemory."""

    def __init__(self):
        self.mem = FakeMemory(size=0x200000, base=BASE)
        self.calls, self.allocs, self.freed, self.next_alloc = [], [], [], BASE + 0x100000
        self.call_result, self.call_ok = 42, 1
        self.version, self.scans = 2, []
        self.ls = socket.socket()
        self.ls.bind(("127.0.0.1", 0))
        self.ls.listen(2)
        self.port = self.ls.getsockname()[1]
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            try:
                s, _ = self.ls.accept()
            except OSError:
                return
            try:
                if ml._recv(s, 16) == TOKEN:
                    self.serve(s)
            except (OSError, ConnectionError):
                pass
            s.close()

    def serve(self, s):
        rx = lambda n: ml._recv(s, n)
        while True:
            op = rx(1)[0]
            if op == ml.OP_INFO:
                s.sendall(struct.pack("<IIQ", self.version, 4242, BASE))
            elif op == ml.OP_READ:
                addr, n = struct.unpack("<QI", rx(12))
                if BASE <= addr and addr + n <= BASE + 0x200000:
                    s.sendall(b"\x01" + self.mem.read(addr, n))
                else:
                    s.sendall(b"\x00")                    # adresse invalide : refusee, comme le vrai mod
            elif op == ml.OP_WRITE:
                addr, n, code = struct.unpack("<QIB", rx(13))
                data = rx(n)
                try:
                    self.mem.write(addr, data)
                    s.sendall(b"\x01")
                except Exception:
                    s.sendall(b"\x00")
            elif op == ml.OP_QUERY:
                addr = struct.unpack("<Q", rx(8))[0]
                ok = BASE <= addr < BASE + 0x200000
                if addr == 0:                             # debut d'un parcours : region libre jusqu'au jeu
                    s.sendall(struct.pack("<BQQII", 1, 0, BASE, 0x10000, 0x01))
                else:
                    s.sendall(struct.pack("<BQQII", ok, BASE, 0x200000, 0x1000, 0x04))
            elif op == ml.OP_ALLOC:
                at, size, protect = struct.unpack("<QII", rx(16))
                out = at or self.next_alloc
                self.next_alloc += 0x10000
                self.allocs.append((at, size, protect))
                s.sendall(struct.pack("<Q", out))
            elif op == ml.OP_FREE:
                self.freed.append(struct.unpack("<Q", rx(8))[0])
                s.sendall(b"\x01")
            elif op == ml.OP_SCAN:
                n, align, cap = struct.unpack("<HHI", rx(8))
                pat = rx(n)
                self.scans.append(pat)
                raw, hits, i = self.mem.read(BASE, 0x200000), [], 0
                while len(hits) < cap:
                    i = raw.find(pat, i)
                    if i < 0:
                        break
                    if (BASE + i) % align == 0:
                        hits.append(BASE + i)
                    i += 1
                s.sendall(struct.pack(f"<I{len(hits)}Q", len(hits), *hits))
            elif op == ml.OP_CALL:
                q = struct.unpack("<Q5QI", rx(52))
                self.calls.append(q)
                s.sendall(struct.pack("<BQ", self.call_ok, self.call_result))


@pytest.fixture
def link():
    mod = FakeMod()
    mem = ml.ModMemory.attach(port=mod.port, token=TOKEN)
    assert mem is not None
    yield mod, mem
    mem.close()


def test_attach_reads_the_game_identity(link):
    mod, mem = link
    assert (mem.pid, mem.base, mem.mod_version) == (4242, BASE, 2) and mem.is_alive()


def test_attach_returns_none_when_no_mod_listens():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert ml.ModMemory.attach(port=port, token=TOKEN) is None


def test_attach_needs_the_right_token():
    mod = FakeMod()
    assert ml.ModMemory.attach(port=mod.port, token=bytes(16), timeout=2) is None      # mauvaise cle : ferme
    assert ml.ModMemory.attach(port=mod.port, token=b"short") is None
    good = ml.ModMemory.attach(port=mod.port, token=TOKEN)
    assert good is not None
    good.close()


def test_token_is_read_from_the_user_profile(tmp_path):
    assert ml.read_token(env={}, home=tmp_path) is None
    win = tmp_path / "Local" / "NierAutomataAP"
    win.mkdir(parents=True)
    (win / "mod_token").write_bytes(TOKEN)
    assert ml.read_token(env={"LOCALAPPDATA": str(tmp_path / "Local")}, home=tmp_path) == TOKEN
    (win / "mod_token").write_bytes(b"bad")                                 # mauvaise taille : ignore
    assert ml.read_token(env={"LOCALAPPDATA": str(tmp_path / "Local")}, home=tmp_path) is None
    proton = (tmp_path / ".local/share/Steam/steamapps/compatdata/524220/pfx/drive_c/users/steamuser"
              / "AppData/Local/NierAutomataAP")
    proton.mkdir(parents=True)
    (proton / "mod_token").write_bytes(TOKEN)
    assert ml.read_token(env={}, home=tmp_path) == TOKEN                    # Linux : prefixe Proton du jeu
    other = tmp_path / "elsewhere"
    other.write_bytes(bytes(16))
    assert ml.read_token(env={"NIER_AP_MOD_TOKEN_FILE": str(other)}, home=tmp_path) == bytes(16)


def test_read_write_go_through_the_mod(link):
    mod, mem = link
    mem.write(BASE + 0x10, b"hello")
    assert mod.mem.read(BASE + 0x10, 5) == b"hello" and mem.read(BASE + 0x10, 5) == b"hello"
    mem.write_code(BASE + 0x20, b"\x90\x90")
    assert mem.read(BASE + 0x20, 2) == b"\x90\x90"
    with pytest.raises(OSError):
        mem.read(8, 4)
    assert mem.is_alive()                       # une lecture refusee ne coupe pas le lien


def test_query_alloc_free_call(link):
    mod, mem = link
    assert mem.query(BASE + 5) == (BASE, 0x200000, 0x1000, 0x04) and mem.query(1) is None
    a = mem.alloc(0x1000, protect=0x40)
    assert a and mod.allocs[-1] == (0, 0x1000, 0x40)
    assert mem.alloc(0x1000, at=BASE + 0x50000) == BASE + 0x50000
    assert mem.free(a) and mod.freed == [a]
    assert mem.call(0x1234, 1, 2, 3, 4, 5, timeout_ms=900) == 42
    assert mod.calls[-1] == (0x1234, 1, 2, 3, 4, 5, 900)
    mod.call_ok = 0
    assert mem.call(0x1234) is None             # delai depasse


def test_existing_win32_style_code_runs_unchanged(link):
    """Le client appelle VirtualQueryEx / VirtualAllocEx / CreateRemoteThread a travers mem._k."""
    mod, mem = link
    k = mem._k
    k.VirtualQueryEx.argtypes = [ctypes.c_void_p]          # le code existant pose ces attributs
    mbi = _MBI()
    assert k.VirtualQueryEx(mem.handle, ctypes.c_void_p(BASE + 8), ctypes.byref(mbi), ctypes.sizeof(mbi))
    assert (mbi.BaseAddress, mbi.RegionSize, mbi.State, mbi.Protect) == (BASE, 0x200000, 0x1000, 0x04)
    assert not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(1), ctypes.byref(mbi), ctypes.sizeof(mbi))
    p = alloc(mem, b"abc")
    assert mod.mem.read(p, 3) == b"abc"
    remote_call(mem, BASE + 0x400, 1, 2, 3, 4, e=5)
    page = mod.calls[-1][0]
    assert struct.pack("<Q", BASE + 0x400) in mod.mem.read(page, 0x60)       # la page d'appel a ete ecrite
    assert page in mod.freed                                                # puis liberee


def test_big_reads_are_split(link, monkeypatch):
    mod, mem = link
    monkeypatch.setattr(ml, "CHUNK", 0x1000)
    mod.mem.write(BASE + 0x2FFE, b"abcd")                 # a cheval sur deux morceaux
    data = mem.read(BASE, 0x5000)
    assert len(data) == 0x5000 and data[0x2FFE:0x3002] == b"abcd"
    mem.write(BASE + 0x8000, bytes(range(256)) * 40)      # 0x2800 octets : trois morceaux
    assert mod.mem.read(BASE + 0x8000, 0x2800) == bytes(range(256)) * 40


def _link(version):
    mod = FakeMod()
    mod.version = version
    mem = ml.ModMemory.attach(port=mod.port, token=TOKEN)
    assert mem is not None and mem.mod_version == version
    return mod, mem


def test_recent_mod_searches_memory_itself():
    # vu en jeu : chaque recherche rapatriait 1,9 Go par la socket (16 s), 5 fois au demarrage du client, qui ne
    # posait aucun AP Item et ne detectait rien pendant ce temps (signale par un testeur : AP Items absents)
    from nier_automata.game import notify
    mod, mem = _link(ml.SCAN_MOD_VERSION)
    try:
        mem.write(BASE + 0x1000, b"NEEDLE!!")
        mem.write(BASE + 0x2001, b"NEEDLE!!")                          # adresse impaire : ecartee (alignement 2)
        mem.write(BASE + 0x3000, b"NEEDLE!!")
        assert notify._scan(mem, [b"NEEDLE!!"]) == {b"NEEDLE!!": [BASE + 0x1000, BASE + 0x3000]}
        assert mod.scans == [b"NEEDLE!!"]
    finally:
        mem.close()


def test_old_mod_still_reads_the_memory_to_search():
    from nier_automata.game import notify
    mod, mem = _link(7)
    try:
        mem.write(BASE + 0x1000, b"NEEDLE!!")
        assert mem.scan(b"NEEDLE!!") is None
        assert notify._scan(mem, [b"NEEDLE!!"]) == {b"NEEDLE!!": [BASE + 0x1000]}
        assert mod.scans == []
    finally:
        mem.close()


def test_search_with_too_many_results_falls_back_to_the_full_read():
    from nier_automata.game import notify
    mod, mem = _link(ml.SCAN_MOD_VERSION)
    try:
        mem.write(BASE, b"AB" * (ml.SCAN_MAX_RESULTS + 10))
        assert mem.scan(b"AB") is None
        assert len(notify._scan(mem, [b"AB"])[b"AB"]) == ml.SCAN_MAX_RESULTS + 10
    finally:
        mem.close()
