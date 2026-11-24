"""9S : pirate le coffre verrouille devant lui. Maintient Y, attend le mini-jeu, repere le noyau (boule sombre)
sur une capture, vise et tire jusqu'a la fin. Renvoie le compteur de coffres avant/apres."""
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture  # noqa: E402
import remote_pad as rp  # noqa: E402


def core_direction(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dark = (r < 95) & (g < 95) & (b < 95) & (abs(r - g) < 18) & (abs(g - b) < 18)     # gris sombre, pas violet
    dark[:30] = False
    h, w = dark.shape
    yy, xx = np.mgrid[0:h, 0:w]
    dark &= ((xx - w * 0.5) ** 2 + (yy - h * 0.555) ** 2) > 95 ** 2      # anneau du vaisseau et minuteur
    ys, xs = np.nonzero(dark)
    if len(xs) < 60:
        return None
    grid = np.zeros((h // 20 + 1, w // 20 + 1), int)
    np.add.at(grid, (ys // 20, xs // 20), 1)
    gy, gx = np.unravel_index(grid.argmax(), grid.shape)
    near = (abs(xs - gx * 20 - 10) < 30) & (abs(ys - gy * 20 - 10) < 30)
    if near.sum() < 60:
        return None
    cx, cy = xs[near].mean(), ys[near].mean()
    h, w = dark.shape
    dx, dy = cx - w * 0.5, cy - h * 0.555           # le vaisseau reste au centre de l'ecran
    n = max(1.0, (dx * dx + dy * dy) ** 0.5)
    return dx / n, dy / n, (round(cx), round(cy), int(near.sum()))


def hack(m, c, save=None):
    cnt = lambda: struct.unpack("<I", m.read(m.base + 0xF50F60, 4))[0]

    def state(buttons, rx=0.0, ry=0.0, lx=0.0, ly=0.0):
        m.write(c + rp.CTL + 4, struct.pack("<II6f", buttons, 1, lx, ly, rx, ry, 0, 0))
        m.write(c + rp.CTL, struct.pack("<I", 1))

    before = cnt()
    rp.set_state(m, c, 0x80)
    time.sleep(2.5)
    rp.set_state(m, c, 0)
    time.sleep(2.4)
    info = None
    for k in range(12):
        img = capture.grab()
        d = core_direction(img)
        if save and k == 0:
            img.save(save)
        if d is None:
            time.sleep(0.2)
            continue
        info = d
        far = ((d[2][0] - 480) ** 2 + (d[2][1] - 300) ** 2) ** 0.5 > 130
        state(0x2000 | 0x4000 | 0x40, d[0], d[1], d[0] * 0.8 if far else 0.0, d[1] * 0.8 if far else 0.0)
        time.sleep(0.35)
    rp.set_state(m, c, 0)
    time.sleep(5)
    return before, cnt(), info


if __name__ == "__main__":
    m = rp.ProcessMemory.attach()
    c = rp.install(m)
    print(hack(m, c, sys.argv[1] if len(sys.argv) > 1 else None))
