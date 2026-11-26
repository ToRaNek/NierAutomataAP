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
    # em0000-em001f : petites machines. Mode random : en plus, les types moyens essayes en jeu sans plantage.
    # Jamais de boss (Adam em5100 se faisait cloner) ni de type non essaye (em1101 a fait planter le jeu).
    ids = [i for i in ids if i & 0xFFFF < 0x20 or (not basic_only and i & 0xFFFF in RANDOM_PROVEN)]
    return rng(ids) if ids else None


RANDOM_PROVEN = frozenset({0x003B, 0x004B, 0x005B, 0x010B, 0x200B})   # 3 exemplaires chacun, verifie en jeu
MAX_ENEMIES = 42     # 33 charges + 12 apparitions passent, 13 a 15 font planter le jeu (vu deux fois)


LEVEL_OFFSET = 0x28030          # niveau de l'ennemi (ecrit par SetLevel)
SET_LEVEL_RVA = 0x631700        # EmBase::SetLevel(ennemi, niveau) : borne 1..99 et recalcule les statistiques


def spawn_level(levels, oid: int) -> int:
    """levels : (objId, niveau) des ennemis presents avant le piege."""
    same = [lv for o, lv in levels if o == oid]
    if same:
        return max(same)
    others = sorted(lv for _, lv in levels)
    return others[(len(others) - 1) // 2] if others else 1


def room_for_spawn(loaded_count: int, count: int) -> bool:
    return loaded_count + count <= MAX_ENEMIES


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


def enemy_entities(mem) -> list[tuple[int, int, str]]:
    """(adresse, objId, nom) de tous les ennemis presents."""
    ptrs: list = []
    try:
        player = struct.unpack("<Q", mem.read(mem.base + PLAYER_PTR_RVA, 8))[0]
    except OSError:
        player = 0
    found = _scan_enemies(mem, 0, only=player, ptrs=ptrs) if player else []
    if not found:
        ptrs.clear()
        found = _scan_enemies(mem, 0, ptrs=ptrs)
    return [(p, o, n) for p, (o, n) in zip(ptrs, found)]


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


def _scan_enemies(mem, want: int, only: int = 0, ptrs: Optional[list] = None) -> list[tuple[int, str]]:
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
                    if ptrs is not None:
                        ptrs.append(o)
                except OSError:
                    continue
            if want and enough_types(out, want):
                break
        if only:
            break
        addr = base + size
    return out


def near_addresses(base: int):
    """Adresses ou tenter une allocation a moins de 2 Go de l'exe (portee d'un saut relatif). D'abord la plage
    habituelle sous l'exe ; puis plus pres dessous, puis au-dessus : selon le lancement, Windows occupe toute la
    premiere plage et rien ne s'y alloue (vu en jeu : erreur 487 sur les 103 essais)."""
    for delta in range(0x10000000, 0x7F000000, 0x1000000):
        yield (base - delta) & ~0xFFFF
    for delta in range(0x100000, 0x10000000, 0x100000):
        yield (base - delta) & ~0xFFFF
    for delta in range(0x2000000, 0x7E000000, 0x1000000):
        yield (base + delta) & ~0xFFFF


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
    before = enemy_entities(mem)
    loaded = [(o, n) for _, o, n in before]
    oid = choose_enemy_type(loaded, basic_only=basic_only)
    if oid is None or not room_for_spawn(len(loaded), count):
        return 0
    levels = []
    for ptr, o, n in before:
        if n not in NOT_SPAWNABLE_NAMES:
            try:
                levels.append((o, struct.unpack("<I", mem.read(ptr + LEVEL_OFFSET, 4))[0]))
            except OSError:
                pass
    level = spawn_level(levels, oid)
    name = f"em{oid & 0xFFFF:04x}".encode() + b"\0"
    for pos in ring_positions(player_pos, count, radius):
        buf = alloc(mem, set_info_bytes(pos) + b"\0" * 0x70 + name)
        remote_call(mem, mem.base + REQUEST_CREATE_RVA, mem.base + MANAGER_RVA, buf + 0x100, oid, buf)
    if level > 1:                      # les nouvelles machines naissent au niveau 1 : leur donner celui de la zone
        import time
        known = {ptr for ptr, _, _ in before}
        done = 0
        for _ in range(4):             # la creation se termine quelques images plus tard
            time.sleep(0.5)
            for ptr, o, _ in enemy_entities(mem):
                if o == oid and ptr not in known:
                    known.add(ptr)
                    try:
                        remote_call(mem, mem.base + SET_LEVEL_RVA, ptr, level)
                        done += 1
                    except OSError:
                        pass
            if done >= count:
                break
    return count


MAX_ENEMY_LEVEL = 99
LEVEL_UP_MAX_TARGETS = 20


def raised_level(level: int, delta: int) -> int:
    """Niveau apres le piege : +delta, borne a 99. 0 = valeur illisible, on n'y touche pas."""
    return min(MAX_ENEMY_LEVEL, level + delta) if 1 <= level < MAX_ENEMY_LEVEL else 0


def raise_enemy_levels(mem, delta: int) -> int:
    """Piege "Level Up" : les ennemis presents (hors objets non clonables) gagnent `delta` niveaux par la fonction
    du jeu EmBase::SetLevel, qui recalcule leurs statistiques. Renvoie le nombre d'ennemis modifies."""
    done = 0
    for ptr, _oid, name in enemy_entities(mem):
        if name in NOT_SPAWNABLE_NAMES or done >= LEVEL_UP_MAX_TARGETS:
            continue
        try:
            new = raised_level(struct.unpack("<I", mem.read(ptr + LEVEL_OFFSET, 4))[0], delta)
            if new:
                remote_call(mem, mem.base + SET_LEVEL_RVA, ptr, new)
                done += 1
        except OSError:
            pass
    return done
