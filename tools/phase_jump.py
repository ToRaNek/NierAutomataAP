"""Saut de phase brut (docs/research/phase_jump.md, option B) : python tools/phase_jump.py <phase hex> <sous-phase>"""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import remote_pad as rp  # noqa: E402
from nier_automata.game.spawner import remote_call  # noqa: E402


def state(m):
    b = m.base
    u = lambda r: struct.unpack("<I", m.read(b + r, 4))[0]
    return {"phase": hex(u(0xF64AA0)), "sub": m.read(b + 0xF64AA8, 0x20).split(b"\0")[0].decode(),
            "machine": u(0xF64A9C), "scene": u(0x102A368)}


def set_scene_state(m, name: str) -> None:
    """Pose un etat de scene (PL/9S, Route/B...) : meme sequence que le menu Chapter Select (phase_jump.md 5A)."""
    import zlib
    cave = rp.install(m)
    buf, tmp = cave + 0x300, cave + 0x380
    raw = name.encode()
    m.write(buf, raw + bytes(1))
    rec = remote_call(m, m.base + 0x150E70, m.base + 0xF8C4E0, zlib.crc32(raw), buf, len(raw))
    m.write(tmp, struct.pack("<Q", rec))
    remote_call(m, m.base + 0x354B20, m.base + 0xFC2680, tmp)
    remote_call(m, m.base + 0x150C60, tmp)


def active_states(m, prefixes=("Route/", "PL/")) -> list:
    b = m.base
    ptr, n = struct.unpack("<QQ", m.read(b + 0xFC2718, 16))
    out = []
    for i in range(min(n, 4000)):
        e = m.read(ptr + i * 0x20, 0x20)
        rec = struct.unpack_from("<Q", e, 0x10)[0]
        name = m.read(rec + 0x38, 0x30).split(bytes(1))[0].decode("ascii", "replace")
        if name.startswith(prefixes):
            out.append(name)
    return out


def set_route(m, route: str, character: str) -> None:
    set_scene_state(m, f"PL/{character}")
    set_scene_state(m, f"Route/{route}")


def jump(m, phase: int, sub: str, wait: float = 90.0) -> bool:
    cave = rp.install(m)
    menus = lambda: struct.unpack("<I", m.read(m.base + 0x11EAC2C, 4))[0]
    for _ in range(3):                       # menu pause ouvert (pause automatique hors focus) : le fermer
        if menus() == 1:
            break
        rp.press(m, cave, 0x100, 0.15)
        time.sleep(2.0)
    st = state(m)
    if menus() != 1:
        raise RuntimeError("un menu est ouvert : saut refuse")
    if st["machine"] != 2 or st["scene"] != 1:
        # un saut lance pendant une pause ou une transition bloque le jeu (vu en jeu) : on refuse
        raise RuntimeError(f"jeu pas pret pour un saut : {st}")
    name = cave + 0x200
    m.write(name, sub.encode() + bytes(0x21 - len(sub)))
    m.write(m.base + 0x14958B0, struct.pack("<I", 0x40000000))
    remote_call(m, m.base + 0x761460, m.base + 0x102A360, phase, name, 1, e=0)
    end = time.time() + wait
    time.sleep(3)
    seen = False
    while time.time() < end:
        s = state(m)
        seen = seen or s["sub"] == sub
        # certaines sous-phases ne durent qu'un chargement (13_B_bunker_Setup, 315_CD_Tower_Unite : ~12 s,
        # scene 0) puis le jeu passe seul a la suivante : le saut a reussi des qu'on l'a vue et que le jeu est pret
        if seen and s["machine"] == 2 and s["scene"] == 1:
            return True
        time.sleep(1)
    return False


if __name__ == "__main__":
    m = rp.ProcessMemory.attach()
    print("avant", state(m))
    ok = jump(m, int(sys.argv[1], 16), sys.argv[2])
    print("saut", ok, state(m), "pos", [round(v, 1) for v in rp.pos(m)] if ok else None)
