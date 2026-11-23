"""Construit dist/NierAutomataAP.exe (lanceur autonome, avec le .apworld embarque)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
apworld = ROOT / "dist" / "nier_automata.apworld"
subprocess.check_call([sys.executable, str(ROOT / "build.py")], cwd=ROOT)
subprocess.check_call([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
    "--name", "NierAutomataAP",
    "--add-data", f"{apworld};.",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
    "--specpath", str(ROOT / "build"),
    str(ROOT / "launcher" / "nier_ap_launcher.py"),
], cwd=ROOT)
print("OK :", ROOT / "dist" / "NierAutomataAP.exe")
