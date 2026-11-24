"""Relance le jeu en fenetre, derriere les autres fenetres, et recharge la sauvegarde a la manette."""
import ctypes
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import remote_pad as rp  # noqa: E402

u = ctypes.windll.user32
u.GetForegroundWindow.restype = ctypes.c_void_p
u.FindWindowW.restype = ctypes.c_void_p
u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           ctypes.c_uint]
u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.GetWindowLongPtrW.restype = ctypes.c_longlong
u.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]


def main():
    prev = u.GetForegroundWindow()
    subprocess.run(["taskkill", "/F", "/IM", "NieRAutomata.exe"], capture_output=True)
    time.sleep(4)
    subprocess.Popen(["cmd", "/c", "start", "", "steam://rungameid/524220"])
    h = None
    for _ in range(160):
        h = u.FindWindowW("NieR:Automata_MainWindow", None)
        if h:
            break
        time.sleep(0.5)
    if not h:
        raise SystemExit("jeu non lance")
    time.sleep(6)
    if not u.GetWindowLongPtrW(h, -16) & 0x00C00000:          # pas de barre de titre : plein ecran
        u.PostMessageW(h, 0x104, 0x0D, 0x201C0001)
        u.PostMessageW(h, 0x105, 0x0D, 0xE01C0001)
        time.sleep(3)
    u.SetWindowPos(h, ctypes.c_void_p(1), 0, 0, 0, 0, 0x13)   # derriere, sans activer
    u.SetForegroundWindow(ctypes.c_void_p(prev))
    m = None
    for _ in range(60):
        time.sleep(2)
        m = rp.ProcessMemory.attach()
        if m:
            break
    import phase_jump as pj
    from nier_automata.game.game import NierGame
    sub = lambda: pj.state(m)["sub"]
    for _ in range(90):                      # ecran titre
        try:
            if sub() in ("TITLE", "SIGNIN") and pj.state(m)["machine"] == 2:
                break
        except OSError:
            pass
        time.sleep(1)
    time.sleep(12)
    c = rp.install(m)
    print("titre :", sub())
    # Les menus du titre ne sont PAS pilotes a l'aveugle : une sequence automatique est arrivee sur
    # "New Game > Delete the current save data ?" (vu en jeu, annule a temps). Les faire avec tools/see.py
    # en regardant chaque capture : A (Continue), A (emplacement), gauche puis A ("Load this save file?" Oui),
    # puis A (Start Game).
    print("au titre : continuer avec tools/see.py en verifiant chaque ecran")


if __name__ == "__main__":
    main()
