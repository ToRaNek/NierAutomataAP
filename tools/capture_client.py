"""Capture la fenetre du client Archipelago (option : clic poste aux coordonnees client x y avant la capture)."""
import ctypes
import sys
import threading
import time

from PIL import Image
from windows_capture import WindowsCapture

u = ctypes.windll.user32
u.FindWindowW.restype = ctypes.c_void_p
u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
h = u.FindWindowW("SDL_app", None)
out_path = sys.argv[1]
if len(sys.argv) >= 4:
    x, y = int(sys.argv[2]), int(sys.argv[3])
    lp = (y << 16) | x
    u.PostMessageW(h, 0x0200, 0, lp)
    u.PostMessageW(h, 0x0201, 1, lp)
    time.sleep(0.1)
    u.PostMessageW(h, 0x0202, 0, lp)
    time.sleep(2.5)
out = {}
done = threading.Event()
cap = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=h)


@cap.event
def on_frame_arrived(frame, control):
    out["img"] = Image.fromarray(frame.frame_buffer[:, :, 2::-1].copy())
    control.stop()
    done.set()


@cap.event
def on_closed():
    done.set()


cap.start_free_threaded()
done.wait(8)
out["img"].save(out_path)
print(out["img"].size)
