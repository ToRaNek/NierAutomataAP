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

from ..data.phases import MENU_PHASES, is_prologue, phase_code


def spawn_allowed(phase: str) -> bool:
    return bool(phase) and phase not in MENU_PHASES and not is_prologue(phase) and "STG" not in phase
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
SET_ITEM_VTABLE_RVA = 0xC79AE8  # BehaviorSetItem (it0000) ; la vtable change quand l'objet est detruit


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
        # le code est une ETAPE de l'histoire, pas un lieu : dedoublonner sur toutes les etapes
        if all(math.dist((x, y, z), (a, b, c)) >= min_dist for _, a, b, c in out):
            chosen.append((x, y, z))
            out.append((code, x, y, z))
    return out


def _route_key(phase: str, phase_limit: int):
    from ..data.phases import ROUTE_A, ap_phase_indices, route_index
    if not spawn_allowed(phase):
        return None
    i = route_index(phase)
    if i is None or i not in ap_phase_indices(phase_limit):
        return None
    return ROUTE_A[i][0]


NEAR_PATH_H, NEAR_PATH_V = 10.0, 3.0   # objet du jeu retenu s'il est pres du trajet reel du joueur (au sol)


def near_path(p, path) -> bool:
    return any(math.hypot(p[0] - q[0], p[2] - q[2]) <= NEAR_PATH_H and abs(p[1] - q[1]) <= NEAR_PATH_V
               for q in path)


def extend_spots(spots, found, phase: str, per_area: int = 2, phase_limit: int = 99,
                 min_dist: float = 60.0, offset: float = 2.0, path=None):
    """Nouveaux emplacements dans la phase d'histoire courante (cle = phase nommee de la route A, d'ou des
    checks "AP Item: <lieu> #k"), au plus `per_area` par phase, a plus de `min_dist` m les uns des autres.
    Candidats, dans l'ordre : objets poses par le jeu PRES DU TRAJET reel du joueur (au sol, pas sur un toit),
    decales de `offset` m ; puis les points du trajet eux-memes. Sans trajet : les objets du jeu."""
    code = _route_key(phase, phase_limit)
    if code is None:
        return []
    taken = [(x, y, z) for _, x, y, z in spots]
    in_area = sum(1 for c, *_ in spots if c == code)
    items = [(round(x + offset, 1), round(y, 1), round(z, 1)) for x, y, z in sorted(found)
             if path is None or near_path((x, y, z), path)]
    walk = [(round(x, 1), round(y, 1), round(z, 1)) for x, y, z in (path or [])]
    new = []
    for p in items + walk:
        if in_area + len(new) >= per_area:
            break
        if all(math.dist(p, q) >= min_dist for q in taken):
            taken.append(p)
            new.append((code, *p))
    return new


def fill_from_path(spots, phase: str, path, per_area: int = 2, phase_limit: int = 99):
    """Fin d'une phase : places restantes sur des points du trajet (les plus espaces possible), pour que
    chaque check reste faisable meme si la phase etait courte."""
    code = _route_key(phase, phase_limit)
    if code is None or not path:
        return []
    n = per_area - sum(1 for c, *_ in spots if c == code)
    if n <= 0:
        return []
    step = max(1, len(path) // n)
    picks = [path[min(i * step, len(path) - 1)] for i in range(n)]
    return [(code, round(x + 1.5 * i, 1), round(y, 1), round(z, 1)) for i, (x, y, z) in enumerate(picks)]


def fallback_spot(spots, phase: str, player_pos, per_area: int = 2, phase_limit: int = 99, offset: float = 2.0):
    """Phase sans objet au sol (arene de boss...) : un emplacement a cote du joueur, pour que chaque check
    "AP Item: <lieu> #k" reste faisable."""
    code = _route_key(phase, phase_limit)
    n = sum(1 for c, *_ in spots if c == code)
    if code is None or n >= per_area:
        return None
    x, y, z = player_pos
    return (code, round(x + offset + 2.0 * n, 1), round(y, 1), round(z, 1))


def scan_ground_objects(mem) -> dict:
    """Objets ramassables poses par le jeu (hors AP Items) -> {objet: position}. Lit d'abord la seule zone
    memoire des entites (0,5 s, verifie en jeu), sinon toute la memoire."""
    import ctypes
    from ctypes import wintypes
    from .spawner import _MBI, entity_region
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    vt = struct.pack("<Q", mem.base + SET_ITEM_VTABLE_RVA)

    def scan(base, size, out):
        try:
            data = mem.read(base, size)
        except OSError:
            return
        i = data.find(vt)
        while i != -1:
            if i % 8 == 0:
                o = base + i
                try:
                    if struct.unpack("<I", mem.read(o + CONTENT_OFFSET, 4))[0] < MARKER_FLAG:
                        out[o] = struct.unpack("<3f", mem.read(o + 0x50, 12))
                except OSError:
                    pass
            i = data.find(vt, i + 1)

    out: dict = {}
    region = entity_region(mem)
    if region:
        scan(*region, out)
        return out          # zone des entites lue : pas d'objet = rien (pas de parcours complet de 17 s)
    addr = 0
    while addr < 0x7FFFFFFFFFFF:
        mbi = _MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress or 0, mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000:
            scan(base, size, out)
        addr = base + size
    return out


def find_game_items(mem) -> list[tuple[float, float, float]]:
    return list(scan_ground_objects(mem).values())


class GroundWatch:
    """Objets au sol autour du joueur (instantane rafraichi regulierement). picked_near() : un objet proche
    a-t-il disparu (ramasse) depuis l'instantane ? Sert a ne pas compter un ramassage comme un coffre."""

    def __init__(self, mem):
        self.mem = mem
        self.items: dict = {}

    def refresh(self) -> None:
        self.items = scan_ground_objects(self.mem)

    def picked_near(self, pos, radius: float = 8.0) -> bool:
        hit = False
        for o, p in list(self.items.items()):
            if math.dist(p, pos) <= radius and not object_alive(self.mem, o):
                hit = True
                self.items.pop(o, None)
        return hit


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
        """Emplacements proches a poser. Le code de phase est une etape de l'histoire (la ville reste la meme
        d'une etape a l'autre) : pas de filtre par code, sauf prologue (autre carte), menus et vaisseau."""
        if not spawn_allowed(phase):
            return []
        return [i for i, (c, x, y, z) in enumerate(self.spots)
                if i not in self.state.ap_spots_collected and i not in self._spawned
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


def pickup_text(me: int, receiver, item, receiver_name, lang: str = "fr") -> tuple[str, str]:
    """(prefixe du modele, nom d'objet) du message de ramassage d'un AP Item."""
    from .i18n import t
    if item is None or receiver is None:
        return "", "AP Item"
    if receiver == me:
        return t(lang, "for_you"), item
    return t(lang, "for", who=receiver_name), item


def nearest_spawned(spots, spawned: set, collected: set, pos, radius: float):
    best, best_d = None, radius
    for i in spawned - collected:
        _, x, y, z = spots[i]
        d = math.dist((x, y, z), pos)
        if d <= best_d:
            best, best_d = i, d
    return best


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
