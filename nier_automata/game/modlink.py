"""Acces au jeu par le mod (dinput8.dll, mod/nier_ap_mod.c) au lieu d'ouvrir son processus de l'exterieur.

`ModMemory` a la meme interface que `ProcessMemory` (read, write, write_code, base, pid...). Le reste du client
appelle encore quelques fonctions de Windows a travers `mem._k` (VirtualQueryEx, VirtualAllocEx,
CreateRemoteThread...) : `_Kernel` les traduit en operations du mod, pour que ce code marche tel quel, y compris
sous Linux ou ces fonctions n'existent pas.

Le mod exige une cle de 16 octets, tiree a chaque lancement du jeu et ecrite dans le profil de l'utilisateur
(%LOCALAPPDATA%/NierAutomataAP/mod_token ; sous Proton, dans le prefixe du jeu)."""
from __future__ import annotations

import ctypes
import glob
import os
import socket
import struct
import threading
from pathlib import Path
from typing import Optional

DEFAULT_PORT = 38291
TOKEN_SIZE = 16
CHUNK = 8 * 1024 * 1024            # taille maximale d'une lecture ou ecriture (le mod accepte 16 Mo)
OP_INFO, OP_READ, OP_WRITE, OP_QUERY, OP_ALLOC, OP_FREE, OP_CALL = 1, 2, 3, 4, 5, 6, 7
OP_SCAN = 11
SCAN_MOD_VERSION = 8        # premiere version du mod qui cherche elle-meme dans la memoire
SCAN_MAX_PATTERN, SCAN_MAX_RESULTS = 1024, 4096
WAIT_OBJECT_0, WAIT_TIMEOUT = 0, 0x102
STEAM_APP_ID = "524220"


def mod_port() -> int:
    try:
        return int(os.environ.get("NIER_AP_MOD_PORT", "") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def token_files(env=None, home: Optional[Path] = None) -> list:
    """Fichiers ou la cle peut se trouver, du plus probable au moins probable."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    out = []
    if env.get("NIER_AP_MOD_TOKEN_FILE"):
        out.append(Path(env["NIER_AP_MOD_TOKEN_FILE"]))
    if env.get("LOCALAPPDATA"):
        out.append(Path(env["LOCALAPPDATA"]) / "NierAutomataAP" / "mod_token")
    # Linux / Proton : le profil Windows du jeu est dans son prefixe (une bibliotheque Steam peut etre ailleurs :
    # donner alors le fichier avec NIER_AP_MOD_TOKEN_FILE)
    for root in (".steam/steam", ".steam/root", ".local/share/Steam",
                 ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
        pattern = home / root / "steamapps" / "compatdata" / STEAM_APP_ID / "pfx" / "drive_c" / "users" / "*" \
            / "AppData" / "Local" / "NierAutomataAP" / "mod_token"
        out += [Path(p) for p in sorted(glob.glob(str(pattern)))]
    return out


def read_token(env=None, home: Optional[Path] = None) -> Optional[bytes]:
    for f in token_files(env, home):
        try:
            if os.name != "nt":
                # Sous Linux / Proton le mod cree le fichier avec les droits par defaut : on le reserve a son
                # proprietaire (la cle change a chaque lancement du jeu).
                os.chmod(f, 0o600)
            data = f.read_bytes()
        except OSError:
            continue
        if len(data) == TOKEN_SIZE:
            return data
    return None


def _addr(v) -> int:
    """Adresse passee a la facon de ctypes : None, entier ou c_void_p."""
    if v is None:
        return 0
    return int(getattr(v, "value", v) or 0)


class _Fn:
    """Fonction de kernel32 simulee. Le code appelant pose .argtypes / .restype comme sur une vraie : ignores."""

    def __init__(self, f):
        self._f = f
        self.argtypes = None
        self.restype = None

    def __call__(self, *a):
        return self._f(*a)


class _Kernel:
    def __init__(self, mem: "ModMemory"):
        self._mem = mem
        self._threads: dict = {}
        self._next = 1
        self.OpenProcess = _Fn(lambda *a: 1)
        self.CloseHandle = _Fn(lambda h: 1)
        self.VirtualQueryEx = _Fn(self._query)
        self.VirtualAllocEx = _Fn(self._alloc)
        self.VirtualFreeEx = _Fn(lambda h, addr, size, kind: 1 if mem.free(_addr(addr)) else 0)
        self.CreateRemoteThread = _Fn(self._thread)
        self.WaitForSingleObject = _Fn(self._wait)

    def _query(self, _h, addr, mbi_ref, _size):
        q = self._mem.query(_addr(addr))
        if q is None:
            return 0
        mbi = getattr(mbi_ref, "_obj", mbi_ref)          # byref(mbi) -> mbi
        mbi.BaseAddress, mbi.RegionSize, mbi.State, mbi.Protect = q[0] or None, q[1], q[2], q[3]
        return ctypes.sizeof(mbi)

    def _alloc(self, _h, addr, size, _kind, protect):
        return self._mem.alloc(int(size), _addr(addr), int(protect)) or None

    def _thread(self, _h, _attrs, _stack, start, _param, _flags, _tid):
        """Le fil n'est lance qu'a l'attente (WaitForSingleObject) : le mod appelle la fonction puis repond."""
        t = self._next
        self._next += 1
        self._threads[t] = _addr(start)
        return t

    def _wait(self, t, timeout_ms):
        func = self._threads.pop(int(t), None)
        if func is None:
            return WAIT_TIMEOUT
        return WAIT_OBJECT_0 if self._mem.call(func, timeout_ms=int(timeout_ms)) is not None else WAIT_TIMEOUT


class ModMemory:
    def __init__(self, sock: socket.socket, version: int, pid: int, base: int):
        self._s = sock
        self._lock = threading.Lock()      # le client lit depuis plusieurs fils : une requete a la fois
        self.mod_version = version
        self.pid = pid
        self.base = base
        self.exe_path = ""                 # inconnu par le mod : la version se lit dans la memoire
        self.handle = 1
        self._k = _Kernel(self)

    @classmethod
    def attach(cls, port: Optional[int] = None, timeout: float = 0.5,
               token: Optional[bytes] = None) -> Optional["ModMemory"]:
        """None si le mod ne repond pas (jeu ferme, mod non installe) ou si la cle manque ou est refusee."""
        token = token if token is not None else read_token()
        if token is None or len(token) != TOKEN_SIZE:
            return None
        try:
            s = socket.create_connection(("127.0.0.1", port or mod_port()), timeout=timeout)
        except OSError:
            return None
        try:
            s.settimeout(30)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.sendall(token + bytes([OP_INFO]))
            version, pid, base = struct.unpack("<IIQ", _recv(s, 16))
        except OSError:
            s.close()
            return None
        return cls(s, version, pid, base)

    def _drop(self):
        try:
            if self._s is not None:
                self._s.close()
        finally:
            self._s = None

    def _ask(self, request: bytes, size: int) -> bytes:
        with self._lock:
            if self._s is None:
                raise OSError("mod link closed")
            try:
                self._s.sendall(request)
                return _recv(self._s, size)
            except OSError:
                self._drop()
                raise

    def scan(self, pattern: bytes, align: int = 2) -> Optional[list]:
        """Adresses du motif dans les regions lecture/ecriture du jeu, cherchees par le mod lui-meme. None si ce
        mod ne sait pas le faire, si le motif est trop long ou s'il y a trop de resultats : l'appelant refait
        alors la recherche lente (lecture de toute la memoire)."""
        if self.mod_version < SCAN_MOD_VERSION or not 0 < len(pattern) <= SCAN_MAX_PATTERN:
            return None
        with self._lock:
            if self._s is None:
                raise OSError("mod link closed")
            try:
                self._s.sendall(struct.pack("<BHHI", OP_SCAN, len(pattern), align, SCAN_MAX_RESULTS) + pattern)
                n = struct.unpack("<I", _recv(self._s, 4))[0]
                data = _recv(self._s, n * 8) if n else b""
            except OSError:
                self._drop()
                raise
        return None if n >= SCAN_MAX_RESULTS else list(struct.unpack(f"<{n}Q", data))

    def read(self, addr: int, size: int) -> bytes:
        """Les grandes lectures (une region de plusieurs centaines de Mo) passent par morceaux : le mod refuse
        une requete de plus de 16 Mo et coupe le lien (vu en jeu)."""
        if size <= CHUNK:
            return self._read(addr, size)
        out = bytearray()
        for o in range(0, size, CHUNK):
            out += self._read(addr + o, min(CHUNK, size - o))
        return bytes(out)

    def _read(self, addr: int, size: int) -> bytes:
        with self._lock:
            if self._s is None:
                raise OSError("mod link closed")
            try:
                self._s.sendall(struct.pack("<BQI", OP_READ, addr, size))
                ok = _recv(self._s, 1) == b""
                data = _recv(self._s, size) if ok else b""
            except OSError:
                self._drop()
                raise
        if not ok:
            raise OSError(f"read failed at {addr:#x}")       # adresse invalide : le lien reste ouvert
        return data

    def _write(self, addr: int, data: bytes, code: int) -> None:
        data = bytes(data)
        for o in range(0, max(len(data), 1), CHUNK):
            part = data[o:o + CHUNK]
            if self._ask(struct.pack("<BQIB", OP_WRITE, addr + o, len(part), code) + part, 1) != b"":
                raise OSError(f"write failed at {addr + o:#x}")

    def write(self, addr: int, data: bytes) -> None:
        self._write(addr, data, 0)

    def write_code(self, addr: int, data: bytes) -> None:
        self._write(addr, data, 1)

    def query(self, addr: int):
        """(base, taille, etat, protection) de la region qui contient `addr`, None hors de l'espace d'adresses."""
        ok, base, size, state, protect = struct.unpack("<BQQII", self._ask(struct.pack("<BQ", OP_QUERY, addr), 25))
        return (base, size, state, protect) if ok else None

    def alloc(self, size: int, at: int = 0, protect: int = 0x04) -> int:
        return struct.unpack("<Q", self._ask(struct.pack("<BQII", OP_ALLOC, at, size, protect), 8))[0]

    def free(self, addr: int) -> bool:
        return self._ask(struct.pack("<BQ", OP_FREE, addr), 1) == b"\x01"

    def call(self, func: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, e: int = 0,
             timeout_ms: int = 5000) -> Optional[int]:
        """Appelle func(a, b, c, d, e) dans le jeu ; None si l'appel n'a pas fini dans le delai."""
        ok, ret = struct.unpack("<BQ", self._ask(struct.pack("<BQ5QI", OP_CALL, func, a, b, c, d, e, timeout_ms), 9))
        return ret if ok else None

    def is_alive(self) -> bool:
        try:
            self._ask(bytes([OP_INFO]), 16)
            return True
        except OSError:
            return False

    def close(self) -> None:
        with self._lock:
            self._drop()


def _recv(s: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = s.recv(n - len(out))
        if not chunk:
            raise ConnectionError("mod closed the link")
        out += chunk
    return bytes(out)
