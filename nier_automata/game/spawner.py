"""Piege "Enemy Trap" : fait apparaitre des ennemis a cote de 2B via l'API de creation du moteur.

Verifie en jeu (v1.04, 2026-11-23) : requestCreate(mgr, nom, objId, setInfo) cree un ennemi complet
(3 x em0000 visibles autour du joueur). Un type dont les fichiers ne sont pas charges dans la zone fait
planter le jeu : on ne demande QUE des types deja presents (ennemis vivants trouves par leur vtable).
"""
from __future__ import annotations

import ctypes
import math
import random
import struct
from ctypes import wintypes
from typing import Callable, Optional, Sequence

from ..data.enemies import ENEMY_VTABLES, NOT_SPAWNABLE_NAMES

REQUEST_CREATE_RVA = 0x745C80   # requestCreate(mgr, const char* nom, objId, setInfo*)
MANAGER_RVA = 0x1029898         # gestionnaire global des creations
OBJID_OFFSET = 0x5B8            # objId dans l'entite
INFO_OFFSET = 0x610             # fiche d'entite (nom en +0x8)


def set_info_bytes(pos: tuple[float, float, float]) -> bytes:
    """Fiche de placement (0x90 octets), meme contenu que le code du jeu a 0x7C3400."""
    b = bytearray(0x90)
    struct.pack_into("<16f", b, 0x00, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    struct.pack_into("<4f", b, 0x40, pos[0], pos[1], pos[2], 1.0)
    struct.pack_into("<4f", b, 0x50, 0, 0, 0, 1.0)
    struct.pack_into("<4f", b, 0x60, 1, 1, 1, 1.0)
    struct.pack_into("<IIQiIiI", b, 0x70, 0, 0, 0, -1, 0, 1, 0xFFFFFFFF)
    return bytes(b)


def ring_positions(center, count: int, radius: float) -> list[tuple[float, float, float]]:
    cx, cy, cz = center
    return [(cx + radius * math.cos(2 * math.pi * i / count), cy, cz + radius * math.sin(2 * math.pi * i / count))
            for i in range(count)]


def choose_enemy_type(loaded: Sequence[tuple[int, str]],
                      rng: Callable[[list], int] = random.choice, basic_only: bool = False) -> Optional[int]:
    """loaded : (objId, nom de fiche) des ennemis vivants. Exclut les carcasses.
    basic_only : seulement les petites machines de base (em0000 / em0010) si la zone en a."""
    ids = sorted({oid for oid, name in loaded if oid >> 16 == 2 and name not in NOT_SPAWNABLE_NAMES})
    # em0000-em001f : petites machines ; a partir de em4000 : geants, Adam / Eve (em5100), boss -> jamais clones
    limit = 0x20 if basic_only else 0x4000
    ids = [i for i in ids if i & 0xFFFF < limit]
    return rng(ids) if ids else None


# --- acces au processus --------------------------------------------------------------------

class _MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


def vtable_hits(data: bytes, vts) -> list[int]:
    """Offsets (alignes sur 8) des pointeurs de vtable dans `data`. Les vtables d'ennemis sont regroupees
    dans le module : on cherche (bytes.find, en C) leurs 6 octets de poids fort communs puis on verifie."""
    groups = {struct.pack("<Q", v)[2:] for v in vts}
    hits = []
    for g in groups:
        i = data.find(g, 2)
        while i != -1:
            start = i - 2
            if start % 8 == 0 and struct.unpack_from("<Q", data, start)[0] in vts:
                hits.append(start)
            i = data.find(g, i + 1)
    return sorted(hits)


def enough_types(found: Sequence[tuple[int, str]], want: int) -> bool:
    """Assez de types d'ennemis utilisables pour arreter le parcours de la memoire."""
    return len({oid for oid, name in found if oid >> 16 == 2 and name not in NOT_SPAWNABLE_NAMES}) >= want


PLAYER_PTR_RVA = 0x1020C88


def entity_region(mem):
    """(debut, taille) de la zone memoire qui contient le joueur : les entites (ennemis, objets au sol)
    y sont aussi (verifie en jeu, ~370 Mo)."""
    try:
        player = struct.unpack("<Q", mem.read(mem.base + PLAYER_PTR_RVA, 8))[0]
    except OSError:
        return None
    if not player:
        return None
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    mbi = _MBI()
    if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(player), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        return None
    return mbi.BaseAddress or 0, mbi.RegionSize


def loaded_enemies(mem, want: int = 3) -> list[tuple[int, str]]:
    """(objId, nom) des ennemis vivants. Verifie en jeu : les entites (joueur et ennemis) sont dans la meme
    zone memoire (~370 Mo) ; on ne lit qu'elle (1-2 s au lieu de ~17 s), puis tout si rien n'y est trouve."""
    try:
        player = struct.unpack("<Q", mem.read(mem.base + PLAYER_PTR_RVA, 8))[0]
    except OSError:
        player = 0
    if player:
        found = _scan_enemies(mem, want, only=player)
        if found:
            return found
    return _scan_enemies(mem, want)


def _scan_enemies(mem, want: int, only: int = 0) -> list[tuple[int, str]]:
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    vts = {mem.base + rva for rva in ENEMY_VTABLES}
    out: list[tuple[int, str]] = []
    addr = 0
    if only:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(only), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return []
        addr = mbi.BaseAddress or 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000:
            try:
                data = mem.read(base, size)
            except OSError:
                data = b""
            for off in vtable_hits(data, vts):
                o = base + off
                try:
                    oid = struct.unpack("<I", mem.read(o + OBJID_OFFSET, 4))[0]
                    info = struct.unpack("<Q", mem.read(o + INFO_OFFSET, 8))[0]
                    name = mem.read(info + 0x8, 0x20).split(bytes(1))[0].decode("ascii", "replace") if info else ""
                    out.append((oid, name))
                except OSError:
                    continue
            if want and enough_types(out, want):
                break
        if only:
            break
        addr = base + size
    return out


def remote_call(mem, func: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, timeout_ms: int = 5000,
                e: int = 0) -> int:
    """Appelle func(a, b, c, d, e) dans le jeu (nouveau fil) et renvoie rax. La page de code est liberee."""
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    k.CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                     ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    k.CreateRemoteThread.restype = wintypes.HANDLE
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    page = k.VirtualAllocEx(h, None, 0x1000, 0x3000, 0x40)
    if not page:
        raise OSError("VirtualAllocEx")
    result = page + 0x800
    code = (b"\x48\x83\xEC\x38"                                            # sub rsp,0x38
            + b"\x48\xB8" + struct.pack("<Q", e) + b"\x48\x89\x44\x24\x20"   # 5e parametre [rsp+0x20]
            + b"\x48\xB9" + struct.pack("<Q", a) + b"\x48\xBA" + struct.pack("<Q", b)
            + b"\x49\xB8" + struct.pack("<Q", c) + b"\x49\xB9" + struct.pack("<Q", d)
            + b"\x48\xB8" + struct.pack("<Q", func) + b"\xFF\xD0" + b"\x48\xA3" + struct.pack("<Q", result)
            + b"\x48\x83\xC4\x38\xC3")                                      # add rsp,0x38 ; ret
    mem.write(page, code)
    t = k.CreateRemoteThread(h, None, 0, ctypes.c_void_p(page), None, 0, None)
    if not t:
        raise OSError("CreateRemoteThread")
    finished = k.WaitForSingleObject(t, timeout_ms) == 0
    k.CloseHandle(t)
    ret = struct.unpack("<Q", mem.read(result, 8))[0]
    if finished:  # ne jamais liberer une page encore en cours d'execution
        k.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
        k.VirtualFreeEx(h, ctypes.c_void_p(page), 0, 0x8000)
    k.CloseHandle(h)
    return ret


def alloc(mem, data: bytes) -> int:
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    p = k.VirtualAllocEx(h, None, max(0x1000, len(data)), 0x3000, 0x04)
    k.CloseHandle(h)
    if not p:
        raise OSError("VirtualAllocEx")
    mem.write(p, data)
    return p


def spawn_enemies(mem, player_pos, count: int = 3, radius: float = 4.0, basic_only: bool = False) -> int:
    """Fait apparaitre `count` ennemis d'un type deja charge. Renvoie le nombre demande (0 si impossible)."""
    oid = choose_enemy_type(loaded_enemies(mem), basic_only=basic_only)
    if oid is None:
        return 0
    name = f"em{oid & 0xFFFF:04x}".encode() + b"\0"
    for pos in ring_positions(player_pos, count, radius):
        buf = alloc(mem, set_info_bytes(pos) + b"\0" * 0x70 + name)
        remote_call(mem, mem.base + REQUEST_CREATE_RVA, mem.base + MANAGER_RVA, buf + 0x100, oid, buf)
    return count
