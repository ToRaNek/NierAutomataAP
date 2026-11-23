"""Objets "AP Item" poses au sol a des emplacements predefinis.

Verifie en jeu (v1.04, 2026-11-23) :
- requestCreate(it0000) pose un objet ramassable (classe BehaviorSetItem) ;
- au ramassage, le jeu tire un contenu au hasard (0x7CA790) sauf si on detourne l'appel : la deviation
  envoie les objets marques ([obj+0x838] = 0x10000 | id) vers le chemin "donner l'objet id" (0x5EB597) ;
- l'objet donne est la Meteorite (688) dont le texte est renomme "AP Item" : le message de ramassage
  affiche "AP Item" ; le client retire ensuite l'objet de l'inventaire.
"""
from __future__ import annotations

import math
import struct
from typing import Optional

from ..data.phases import phase_code
from .state import ClientState

CAVE_SITE_RVA = 0x5EB5B7       # mov edx,[rdi+0x838] ; mov rcx,rdi ; call 0x7CA790 (tirage au hasard)
DIRECT_GIVE_RVA = 0x5EB597     # chemin "donner l'objet [rdi+0x838]"
DROP_CALL_RVA = 0x7CA790
RETURN_RVA = 0x5EB5C5
SITE_ORIGINAL = bytes.fromhex("8b9738080000488bcf")
MARKER_FLAG = 0x10000
AP_MARKER_ITEM = 688           # (ancien marqueur, garde pour compatibilite)
PICKUP_CARRIER = 921           # "Sachet de qualité" (17 car.) : nom reecrit avec le contenu de l'AP Item
PICKUP_CARRIER_KEY = "ITEM_NAME_921"
AP_MARKER_NAME = "Météorite"
CONTENT_OFFSET = 0x838
IT0000 = 0x70000


def pick_spots(path, min_dist: float = 40.0, per_area: int = 5):
    """path : [(phase, x, y, z)] enregistre en jouant. Renvoie [(code de zone, x, y, z)]."""
    out: list[tuple[str, float, float, float]] = []
    per: dict[str, list] = {}
    for phase, x, y, z in path:
        code = phase_code(phase)
        if code is None:
            continue
        chosen = per.setdefault(code, [])
        if len(chosen) >= per_area:
            continue
        if all(math.dist((x, y, z), c) >= min_dist for c in chosen):
            chosen.append((x, y, z))
            out.append((code, x, y, z))
    return out


class SpotTracker:
    def __init__(self, state: ClientState, spots, radius: float = 150.0):
        self.state = state
        self.spots = spots
        self.radius = radius
        self._spawned: set[int] = set()

    def set_game_process(self, pid: int) -> None:
        """Un objet pose reste au sol tant que le processus du jeu vit : on s'en souvient (dans l'etat)
        pour ne pas le reposer si le client est relance."""
        if self.state.ap_spawned_pid != pid:
            self.state.ap_spawned_pid = pid
            self.state.ap_spawned_spots.clear()

    def to_spawn(self, phase: str, player_pos) -> list[int]:
        code = phase_code(phase)
        return [i for i, (c, x, y, z) in enumerate(self.spots)
                if c == code and i not in self.state.ap_spots_collected and i not in self._spawned
                and i not in self.state.ap_spawned_spots
                and math.dist((x, y, z), player_pos) <= self.radius]

    def mark_spawned(self, i: int) -> None:
        self._spawned.add(i)
        self.state.ap_spawned_spots.add(i)

    def collected(self, i: int) -> None:
        self.state.ap_spots_collected.add(i)

    def reset_session(self) -> None:
        """Changement de zone : les objets non ramasses sont decharges par le jeu, on pourra les reposer."""
        self._spawned.clear()
        self.state.ap_spawned_spots.clear()


def pickup_text(me: int, receiver, item, receiver_name) -> tuple[str, str]:
    """(prefixe du modele, nom d'objet) du message de ramassage d'un AP Item."""
    if item is None or receiver is None:
        return "", "AP Item"
    if receiver == me:
        return "Check validé : ", item
    return f"Pour {receiver_name} : ", item


def nearest_spawned(spots, spawned: set, collected: set, pos, radius: float):
    best, best_d = None, radius
    for i in spawned - collected:
        _, x, y, z = spots[i]
        d = math.dist((x, y, z), pos)
        if d <= best_d:
            best, best_d = i, d
    return best


SET_ITEM_VTABLE_RVA = 0xC79AE8  # BehaviorSetItem (it0000) ; la vtable change quand l'objet est detruit


def nearest_object(objs: dict, pos_of, pos, radius: float):
    """objs : {objet: indice de spot}. Renvoie l'objet le plus proche (vraie position) dans le rayon."""
    best, best_d = None, radius
    for o in objs:
        p = pos_of(o)
        if p is None:
            continue
        d = math.dist(p, pos)
        if d <= best_d:
            best, best_d = o, d
    return best


def match_objects_to_spots(found: dict, spots, collected: set, max_dist: float) -> dict:
    """found : {objet: position}. Associe chaque AP Item deja au sol a l'emplacement le plus proche."""
    out = {}
    for o, p in found.items():
        best, best_d = None, max_dist
        for i, (_, x, y, z) in enumerate(spots):
            if i in collected:
                continue
            d = math.dist((x, y, z), p)
            if d <= best_d:
                best, best_d = i, d
        if best is not None:
            out[o] = best
    return out


def find_marked_objects(mem) -> dict:
    """AP Items deja au sol (objets it0000 portant le marqueur) -> {objet: position}."""
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    vt = mem.base + SET_ITEM_VTABLE_RVA
    out, addr = {}, 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000 and size % 8 == 0:
            try:
                arr = memoryview(mem.read(base, size)).cast("Q")
                for i, v in enumerate(arr):
                    if v == vt:
                        o = base + i * 8
                        if struct.unpack("<I", mem.read(o + CONTENT_OFFSET, 4))[0] == MARKER_FLAG | PICKUP_CARRIER:
                            out[o] = struct.unpack("<3f", mem.read(o + 0x50, 12))
            except OSError:
                pass
        addr = base + size
    return out


def object_alive(mem, obj: int) -> bool:
    try:
        return struct.unpack("<Q", mem.read(obj, 8))[0] == mem.base + SET_ITEM_VTABLE_RVA
    except OSError:
        return False


def resolve_pickups(tracked: dict, obj_of, marker_received: bool) -> list[int]:
    """tracked : {fiche: indice de spot}. Un spot est ramasse si son objet a disparu ET qu'un marqueur
    est arrive dans l'inventaire (sinon l'objet a juste ete decharge en quittant la zone)."""
    if not marker_received:
        return []
    return [i for w, i in tracked.items() if not obj_of(w)]


def cave_bytes(cave: int, base: int, call_rel_original: bytes) -> bytes:
    """Code de la deviation (voir docstring du module)."""
    def rel(src_next, dst):
        return struct.pack("<i", dst - src_next)
    c = bytearray()
    c += b"\x81\xBF\x38\x08\x00\x00" + struct.pack("<I", MARKER_FLAG)   # cmp dword [rdi+0x838], 0x10000
    jb = len(c); c += b"\x72\x00"                                        # jb -> tirage normal
    c += b"\x81\xA7\x38\x08\x00\x00\xFF\xFF\x00\x00"                     # and dword [rdi+0x838], 0xFFFF
    c += b"\xE9" + rel(cave + len(c) + 5, base + DIRECT_GIVE_RVA)        # jmp chemin direct
    c[jb + 1] = len(c) - (jb + 2)
    c += SITE_ORIGINAL                                                   # mov edx,[rdi+0x838] ; mov rcx,rdi
    c += b"\xE8" + rel(cave + len(c) + 5, base + DROP_CALL_RVA)          # call tirage
    c += b"\xE9" + rel(cave + len(c) + 5, base + RETURN_RVA)             # retour
    return bytes(c)


def install(mem) -> bool:
    """Installe la deviation (une fois par processus) et renomme le texte de l'objet marqueur."""
    import ctypes
    from ctypes import wintypes
    site = mem.base + CAVE_SITE_RVA
    cur = mem.read(site, 5)
    if cur[0] == 0xE9:
        return True  # deja installee
    if mem.read(site, 9) != SITE_ORIGINAL:
        return False  # version inattendue : ne rien toucher
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    cave: Optional[int] = None
    for delta in range(0x10000000, 0x7F000000, 0x1000000):
        cave = k.VirtualAllocEx(h, ctypes.c_void_p((mem.base - delta) & ~0xFFFF), 0x1000, 0x3000, 0x40)
        if cave:
            break
    k.CloseHandle(h)
    if not cave:
        return False
    mem.write(cave, cave_bytes(cave, mem.base, b""))
    mem.write_code(site, b"\xE9" + struct.pack("<i", cave - (site + 5)) + b"\x90" * 4)
    rename_marker(mem)
    return True


def rename_marker(mem) -> int:
    """Remplace le nom UTF-16 de l'objet marqueur par "AP Item" (message de ramassage)."""
    import ctypes
    from .spawner import _MBI
    from ctypes import wintypes
    pat = AP_MARKER_NAME.encode("utf-16-le")
    new = ("AP Item".encode("utf-16-le") + b"\0\0").ljust(len(pat), b"\0")
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    n, addr = 0, 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000:
            try:
                data = mem.read(base, size)
                i = data.find(pat)
                while i != -1:
                    if data[i + len(pat):i + len(pat) + 2] == b"\0\0":
                        mem.write(base + i, new); n += 1
                    i = data.find(pat, i + 1)
            except OSError:
                pass
        addr = base + size
    return n


def spawn_ap_item(mem, pos) -> int:
    """Pose un objet AP. Renvoie la fiche de travail (objet en [fiche+0x60])."""
    import time
    from .spawner import MANAGER_RVA, REQUEST_CREATE_RVA, alloc, remote_call, set_info_bytes
    buf = alloc(mem, set_info_bytes(pos) + b"\0" * 0x70 + b"it0000\0")
    work = remote_call(mem, mem.base + REQUEST_CREATE_RVA, mem.base + MANAGER_RVA, buf + 0x100, IT0000, buf)
    for _ in range(20):
        obj = struct.unpack("<Q", mem.read(work + 0x60, 8))[0] if work else 0
        if obj:
            mem.write(obj + CONTENT_OFFSET, struct.pack("<I", MARKER_FLAG | PICKUP_CARRIER))
            return obj
        time.sleep(0.05)
    return 0
