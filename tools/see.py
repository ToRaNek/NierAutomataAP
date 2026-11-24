"""Appuie sur des boutons (masques hex, separes par des espaces) puis capture le jeu : python tools/see.py out.png [masque...]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture  # noqa: E402
import remote_pad as rp  # noqa: E402

m = rp.ProcessMemory.attach()
c = rp.install(m)
for a in sys.argv[2:]:
    if a.startswith("w"):
        time.sleep(float(a[1:]))
    else:
        rp.press(m, c, int(a, 16), 0.15)
        time.sleep(0.9)
time.sleep(1.2)
capture.grab().save(sys.argv[1])
