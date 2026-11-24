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
    for attempt in range(4):                 # Continue -> emplacement -> Oui, jusqu'au menu START
        for mask, wait in ((0x10, 3), (0x10, 2.5), (0x1, 1), (0x10, 2)):
            rp.press(m, c, mask, 0.15)
            time.sleep(wait)
        ok = False
        for _ in range(40):
            if sub() == "START":
                ok = True
                break
            time.sleep(1)
        if ok:
            break
        for _ in range(3):                   # mauvais ecran : on revient en arriere et on recommence
            rp.press(m, c, 0x20, 0.15)
            time.sleep(1)
    time.sleep(6)
    g = NierGame()
    g.attach()
    for _ in range(3):
        rp.press(m, c, 0x10, 0.15)           # Start Game
        for _ in range(45):
            if g.in_game():
                break
            time.sleep(1)
        if g.in_game():
            break
    print("en jeu :", g.in_game(), g.phase())


if __name__ == "__main__":
    main()
