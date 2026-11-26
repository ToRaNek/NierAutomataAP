"""Construit dist/dinput8.dll (le mod) avec zig cc. A placer a cote de NieRAutomata.exe.
Sous Linux / Proton, ajouter aux options de lancement Steam : WINEDLLOVERRIDES="dinput8=n,b" %command%"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = ROOT / "dist" / "dinput8.dll"
out.parent.mkdir(exist_ok=True)
cmd = ["zig", "cc", "-target", "x86_64-windows-gnu", "-shared", "-O2", "-s", "-Wall", "-Wextra",
       str(ROOT / "mod" / "nier_ap_mod.c"), str(ROOT / "mod" / "overlay.c"), "-o", str(out), "-lws2_32", "-ladvapi32", "-ld3d11", "-ldxgi", "-lgdi32", "-luser32"]
r = subprocess.run(cmd)
if r.returncode:
    sys.exit(r.returncode)
for junk in (out.with_suffix(".lib"), out.with_suffix(".pdb")):
    junk.unlink(missing_ok=True)
print(out, out.stat().st_size, "octets")
