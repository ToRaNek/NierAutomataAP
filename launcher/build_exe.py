"""Construit dist/NierAutomataAP.exe (lanceur autonome, avec le .apworld et le mod dinput8.dll embarques)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
apworld = ROOT / "dist" / "nier_automata.apworld"
mod = ROOT / "dist" / "dinput8.dll"
subprocess.check_call([sys.executable, str(ROOT / "build.py")], cwd=ROOT)
subprocess.check_call([sys.executable, str(ROOT / "mod" / "build_mod.py")], cwd=ROOT)
subprocess.check_call([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
    "--name", "NierAutomataAP",
    "--add-data", f"{apworld};.",
    "--add-data", f"{mod};.",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
    "--specpath", str(ROOT / "build"),
    str(ROOT / "launcher" / "nier_ap_launcher.py"),
], cwd=ROOT)
print("OK :", ROOT / "dist" / "NierAutomataAP.exe")
