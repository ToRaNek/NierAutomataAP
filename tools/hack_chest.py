"""9S : pirate le coffre verrouille devant lui, avec visee automatique.
Maintient Y, attend l'ecran du mini-jeu (fond beige), puis a chaque capture repere le noyau (boule gris sombre),
oriente le tir (stick droit) et tire, jusqu'a la fin du mini-jeu. Renvoie le compteur de coffres avant/apres."""
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture  # noqa: E402
import remote_pad as rp  # noqa: E402

FIRE = 0x2000 | 0x4000 | 0x40
SHIP = (0.5, 0.555)            # le vaisseau reste a cet endroit de l'ecran (fraction largeur, hauteur)


def in_minigame(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    beige = (r > 170) & (g > 165) & (b > 130) & (r - b > 15) & (r - b < 70)
    return beige.mean() > 0.45


def core(a):
    """Centre (x, y) du noyau : plus gros amas gris sombre hors de l'anneau du vaisseau."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dark = (r < 95) & (g < 95) & (b < 95) & (abs(r - g) < 18) & (abs(g - b) < 18)
    h, w = dark.shape
    dark[:30] = False
    yy, xx = np.mgrid[0:h, 0:w]
    dark &= ((xx - w * SHIP[0]) ** 2 + (yy - h * SHIP[1]) ** 2) > 95 ** 2
    ys, xs = np.nonzero(dark)
    if len(xs) < 60:
        return None
    grid = np.zeros((h // 20 + 1, w // 20 + 1), int)
    np.add.at(grid, (ys // 20, xs // 20), 1)
    gy, gx = np.unravel_index(grid.argmax(), grid.shape)
    near = (abs(xs - gx * 20 - 10) < 30) & (abs(ys - gy * 20 - 10) < 30)
    if near.sum() < 60:
        return None
    return float(xs[near].mean()), float(ys[near].mean())


def hack(m, c, save=None, log=None):
    cnt = lambda: struct.unpack("<I", m.read(m.base + 0xF50F60, 4))[0]

    def state(buttons, rx=0.0, ry=0.0, lx=0.0, ly=0.0):
        m.write(c + rp.CTL + 4, struct.pack("<II6f", buttons, 1, lx, ly, rx, ry, 0, 0))
        m.write(c + rp.CTL, struct.pack("<I", 1))

    before = cnt()
    rp.set_state(m, c, 0x80)                       # maintenir Y : lancement du piratage
    started = False
    t0 = time.time()
    while time.time() - t0 < 9:
        a = np.asarray(capture.grab().convert("RGB")).astype(int)
        if in_minigame(a):
            started = True
            break
        if time.time() - t0 > 3.0:
            rp.set_state(m, c, 0)
    rp.set_state(m, c, 0)
    if not started:
        return {"started": False, "before": before, "after": cnt()}
    shots, last = 0, (0.0, -1.0)
    t1 = time.time()
    while time.time() - t1 < 14:
        img = capture.grab()
        a = np.asarray(img.convert("RGB")).astype(int)
        if not in_minigame(a):
            break
        h, w = a.shape[:2]
        p = core(a)
        if save and shots == 2:
            img.save(save)
        if p:
            dx, dy = p[0] - w * SHIP[0], p[1] - h * SHIP[1]
            n = max(1.0, (dx * dx + dy * dy) ** 0.5)
            last = (dx / n, dy / n)
            if log is not None:
                log.append((round(time.time() - t1, 1), round(p[0]), round(p[1])))
        state(FIRE, last[0], last[1])
        shots += 1
    rp.set_state(m, c, 0)
    time.sleep(5)
    return {"started": True, "frames": shots, "seconds": round(time.time() - t1 - 5, 1), "before": before,
            "after": cnt()}


if __name__ == "__main__":
    m = rp.ProcessMemory.attach()
    c = rp.install(m)
    print(hack(m, c, sys.argv[1] if len(sys.argv) > 1 else None))
