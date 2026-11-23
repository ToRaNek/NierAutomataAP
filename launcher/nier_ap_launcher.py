"""Lanceur autonome du client NieR:Automata pour Archipelago.

1. trouve l'installation d'Archipelago (dossier par defaut, registre, ou chemin passe en argument) ;
2. installe / met a jour nier_automata.apworld dans <Archipelago>/custom_worlds (fourni avec l'exe) ;
3. lance "NieR:Automata Client" via ArchipelagoLauncher.exe, en transmettant un lien archipelago:// eventuel.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

APWORLD = "nier_automata.apworld"
CLIENT = "NieR:Automata Client"
DEFAULT_DIRS = [r"C:\ProgramData\Archipelago", r"C:\Program Files\Archipelago",
                r"C:\Program Files (x86)\Archipelago"]


def is_archipelago_dir(p: Path) -> bool:
    return (p / "ArchipelagoLauncher.exe").is_file()


def registry_dirs() -> list[str]:
    """Dossiers d'installation des programmes dont le nom commence par "Archipelago" (liste de desinstallation)."""
    out = []
    try:
        import winreg
    except ImportError:
        return out
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, i)) as k:
                            if str(winreg.QueryValueEx(k, "DisplayName")[0]).startswith("Archipelago"):
                                out.append(str(winreg.QueryValueEx(k, "InstallLocation")[0]))
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def find_archipelago(candidates: list[str]) -> Optional[Path]:
    for c in candidates:
        if c and is_archipelago_dir(Path(c)):
            return Path(c)
    return None


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def needs_install(bundled: Path, installed: Path) -> bool:
    return file_hash(bundled) != file_hash(installed)


def bundled_apworld() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / APWORLD


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--archipelago=")]
    custom = [a.split("=", 1)[1] for a in argv if a.startswith("--archipelago=")]
    ap = find_archipelago(custom + [os.environ.get("ARCHIPELAGO_DIR", "")] + registry_dirs() + DEFAULT_DIRS)
    if ap is None:
        print("Archipelago introuvable. Installe-le (https://archipelago.gg) ou lance :\n"
              '  NierAutomataAP.exe --archipelago="C:\\chemin\\vers\\Archipelago"')
        input("Entree pour quitter...")
        return 1
    src = bundled_apworld()
    dst = ap / "custom_worlds" / APWORLD
    if src.is_file() and needs_install(src, dst):
        dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"apworld installe : {dst}")
    subprocess.Popen([str(ap / "ArchipelagoLauncher.exe"), CLIENT, *args], cwd=str(ap))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
