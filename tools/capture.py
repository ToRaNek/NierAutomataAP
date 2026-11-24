"""Capture la fenetre du jeu sans la mettre au premier plan (Windows Graphics Capture).
    python tools/capture.py sortie.png [largeur]"""
import sys
import threading

from PIL import Image
from windows_capture import Frame, InternalCaptureControl, WindowsCapture


def grab(width=960, title="NieR:Automata"):
    out = {}
    done = threading.Event()
    import ctypes
    ctypes.windll.user32.FindWindowW.restype = ctypes.c_void_p
    hwnd = ctypes.windll.user32.FindWindowW("NieR:Automata_MainWindow", None)
    if not hwnd:
        raise SystemExit("fenetre du jeu introuvable")
    cap = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=hwnd)

    @cap.event
    def on_frame_arrived(frame: Frame, control: InternalCaptureControl):
        out["n"] = out.get("n", 0) + 1
        buf = frame.frame_buffer
        if out["n"] < 30 and int(buf[::16, ::16, :3].max()) < 12:
            return                      # image noire (premieres images) : attendre la suivante
        out["img"] = Image.fromarray(buf[:, :, 2::-1].copy())
        control.stop()
        done.set()

    @cap.event
    def on_closed():
        done.set()

    cap.start_free_threaded()
    done.wait(8)
    img = out.get("img")
    if img is None:
        raise SystemExit("pas d'image")
    if img.width > width:
        img = img.resize((width, img.height * width // img.width))
    return img


if __name__ == "__main__":
    grab(int(sys.argv[2]) if len(sys.argv) > 2 else 960).save(sys.argv[1])
    print("ok", sys.argv[1])
