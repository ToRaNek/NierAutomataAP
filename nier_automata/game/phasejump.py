"""Saut de chapitre fait par le client (routes verrouillees). Meme sequence que le menu Chapter Select du jeu,
verifiee en jeu sur tous les chapitres des trois routes avec tools/phase_jump.py (docs/research/phase_jump.md)."""
from __future__ import annotations

import struct
import zlib

from .spawner import alloc, remote_call

MACHINE_RVA = 0xF64A9C        # 2 = jeu en cours
SCENE_RVA = 0x102A368         # 1 = scene prete
MENU_RVA = 0x11EAC2C          # 1 = aucun menu ouvert
JUMP_FUNC_RVA = 0x761460
JUMP_MANAGER_RVA = 0x102A360
JUMP_FLAG_RVA = 0x14958B0
STATE_FIND_RVA, STATE_TABLE_RVA = 0x150E70, 0xF8C4E0
STATE_SET_RVA, STATE_LIST_RVA = 0x354B20, 0xFC2680
STATE_RELEASE_RVA = 0x150C60


def _u32(mem, rva: int) -> int:
    return struct.unpack("<I", mem.read(mem.base + rva, 4))[0]


def ready(mem) -> bool:
    """Un saut lance pendant une pause, un menu ou une transition bloque le jeu (vu en jeu) : on attend."""
    try:
        return _u32(mem, MACHINE_RVA) == 2 and _u32(mem, SCENE_RVA) == 1 and _u32(mem, MENU_RVA) == 1
    except OSError:
        return False


def set_scene_state(mem, name: str) -> None:
    raw = name.encode()
    buf = alloc(mem, raw + bytes(0x100 - len(raw)))
    tmp = buf + 0x80
    rec = remote_call(mem, mem.base + STATE_FIND_RVA, mem.base + STATE_TABLE_RVA, zlib.crc32(raw), buf, len(raw))
    mem.write(tmp, struct.pack("<Q", rec))
    remote_call(mem, mem.base + STATE_SET_RVA, mem.base + STATE_LIST_RVA, tmp)
    remote_call(mem, mem.base + STATE_RELEASE_RVA, tmp)


def jump(mem, route: str, character: str, phase: int, sub: str) -> bool:
    """Pose la route et le personnage puis lance le saut. False si le jeu n'est pas pret (rien n'est fait)."""
    if not ready(mem):
        return False
    set_scene_state(mem, f"PL/{character}")
    set_scene_state(mem, f"Route/{route}")
    name = alloc(mem, sub.encode() + bytes(0x40 - len(sub)))
    mem.write(mem.base + JUMP_FLAG_RVA, struct.pack("<I", 0x40000000))
    remote_call(mem, mem.base + JUMP_FUNC_RVA, mem.base + JUMP_MANAGER_RVA, phase, name, 1, e=0)
    return True
