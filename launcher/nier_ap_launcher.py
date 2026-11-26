"""Lanceur autonome du client NieR:Automata pour Archipelago.

1. trouve l'installation d'Archipelago (dossier par defaut, registre, ou chemin passe en argument) ;
2. installe / met a jour nier_automata.apworld dans <Archipelago>/custom_worlds (fourni avec l'exe) ;
2 bis. installe / met a jour le mod dinput8.dll a cote de NieRAutomata.exe (panneaux des zones verrouillees ;
   --no-mod pour ne pas le faire, --game="dossier du jeu" si Steam ne le trouve pas) ;
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
MOD = "dinput8.dll"
MOD_MARK = b"NierApMod"            # present dans notre dinput8.dll : on n'ecrase jamais celui d'un autre mod
GAME_EXE = "NieRAutomata.exe"
GAME_SUBDIR = ("steamapps", "common", "NieRAutomata")
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


def bundled(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def bundled_apworld() -> Path:
    return bundled(APWORLD)


def steam_roots() -> list[str]:
    out = []
    try:
        import winreg
    except ImportError:
        return out
    for hive, path, value in ((winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam", "SteamPath"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
        try:
            with winreg.OpenKey(hive, path) as k:
                out.append(str(winreg.QueryValueEx(k, value)[0]))
        except OSError:
            continue
    return out


def steam_libraries(root: Path) -> list[Path]:
    """La bibliotheque de `root` et celles listees dans steamapps/libraryfolders.vdf."""
    libs = [root]
    try:
        text = (root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libs
    import re
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        p = Path(m.group(1).replace("\\\\", "\\"))
        if p not in libs:
            libs.append(p)
    return libs


def find_game(candidates: list[str], roots: list[str]) -> Optional[Path]:
    """Dossier qui contient NieRAutomata.exe : un chemin donne, sinon dans les bibliotheques Steam."""
    for c in candidates:
        if c and (Path(c) / GAME_EXE).is_file():
            return Path(c)
    for r in roots:
        if not r:
            continue
        for lib in steam_libraries(Path(r)):
            d = lib.joinpath(*GAME_SUBDIR)
            if (d / GAME_EXE).is_file():
                return d
    return None


def install_mod(src: Path, game: Path) -> str:
    """Copie le mod a cote du jeu. Renvoie : "installed", "up to date", "foreign" (un dinput8.dll qui n'est pas le
    notre est deja la : on n'y touche pas) ou "locked" (jeu en cours : fichier non remplacable)."""
    dst = game / MOD
    if dst.is_file():
        if not needs_install(src, dst):
            return "up to date"
        if MOD_MARK not in dst.read_bytes():
            return "foreign"
    try:
        shutil.copyfile(src, dst)
    except OSError:
        return "locked"
    return "installed"


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith(("--archipelago=", "--game=")) and a != "--no-mod"]
    games = [a.split("=", 1)[1] for a in argv if a.startswith("--game=")]
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
    mod = bundled(MOD)
    if "--no-mod" not in argv and mod.is_file():
        game = find_game(games + [os.environ.get("NIER_AUTOMATA_DIR", "")], steam_roots())
        if game is None:
            print('Jeu introuvable : mod non installe (panneaux des zones). Pour l\'installer :\n'
                  '  NierAutomataAP.exe --game="C:\\chemin\\vers\\NieRAutomata"')
        else:
            result = install_mod(mod, game)
            print({"installed": f"mod installe : {game / MOD} (relance le jeu s'il est ouvert)",
                   "up to date": "mod a jour",
                   "foreign": f"un autre {MOD} est deja dans {game} : mod NON installe (panneaux des zones "
                              "absents, le reste marche)",
                   "locked": f"jeu en cours : {MOD} non remplace, ferme le jeu et relance ce programme"}[result])
    subprocess.Popen([str(ap / "ArchipelagoLauncher.exe"), CLIENT, *args], cwd=str(ap))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
