"""Essai en jeu de chaque verrou avec le vrai client et un serveur (tools/e2e_lock_serve.py), un par un.

    python tools/locktest.py areas | B | C      (resultats ajoutes a tools/locktest_report.json)

areas : pour chaque zone, avance le joueur en ligne droite a travers l'entree (le client doit le repousser), envoie
        le Pass, recommence (il doit passer).
B, C  : pour chaque grand chapitre verrouille, saute a son debut (le client doit ramener au chapitre precedent),
        envoie une cle (le client doit lancer le chapitre et son check doit partir).
"""
import glob
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import phase_jump as pj  # noqa: E402
import remote_pad as rp  # noqa: E402
import sweep  # noqa: E402
from nier_automata.data import chapterlocks as cl  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402
from nier_automata.data.areas import AREA_ID_RVA, AREA_PASSES  # noqa: E402
from nier_automata.game.game import NierGame  # noqa: E402

HERE = Path(__file__).resolve().parent
REPORT = HERE / "locktest_report.json"
CMD = HERE / "e2e_lock" / "out" / "cmd.txt"
# zone -> (x, y, z de depart cote ville, x, z d'arrivee dans la zone)
GATES = {
    "Desert Pass": (-150.0, 16.0, 66.0, -180.0, 14.0),
    "Park Pass": (285.0, 6.0, 344.5, 360.0, 344.5),
    "Village Pass": (372.0, 4.0, -35.0, 425.0, -35.0),
    "Forest Pass": (75.4, 6.0, -195.0, 75.4, -250.0),
    "Flooded City Pass": (471.9, -55.0, 570.0, 471.9, 645.0),
    "Factory Pass": (-185.0, 8.0, 514.0, -250.0, 514.0),
}


def client_log() -> str:
    f = sorted(glob.glob(r"C:\ProgramData\Archipelago\logs\Launcher_*"), key=os.path.getmtime)[-1]
    return open(f, encoding="utf-8", errors="replace").read()


def send(item: str) -> None:
    with open(CMD, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"/send TestNier {item}\n")


def save(rep) -> None:
    REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


def heal(n) -> None:
    p = n.entity()
    if p:
        n.mem.write(p + 0x10668, struct.pack("<I", struct.unpack("<I", n.mem.read(p + 0x85C, 4))[0]))


def glide(n, g, gate, seconds=18.0):
    """Avance de 2,5 m toutes les 0,1 s A PARTIR DE LA POSITION REELLE du joueur (le client peut le repousser).
    Renvoie la plus grande distance atteinte le long du trajet et sa longueur."""
    sx, sy, sz, ex, ez = gate
    g.goto((sx, sy, sz), settle=1.0)
    n.mem.write(n.mem.base + AREA_ID_RVA, struct.pack("<i", 0))     # les bonds ont pu traverser d'autres volumes
    time.sleep(2.5)                                                 # le client reprend une trace a cet endroit
    length = math.hypot(ex - sx, ez - sz)
    ux, uz = (ex - sx) / length, (ez - sz) / length
    far, t0 = 0.0, time.time()
    while time.time() - t0 < seconds:
        heal(n)
        x, _, z = n.entity_position()
        d = (x - sx) * ux + (z - sz) * uz
        far = max(far, d)
        if d >= length - 1.0:
            break
        d = max(d, 0.0) + 2.5
        n.teleport((sx + ux * d, sy, sz + uz * d))
        time.sleep(0.1)
    return round(far, 1), round(length, 1)


def test_areas(rep):
    n = NierGame()
    n.attach()
    g = sweep.Game()
    for name, gate in GATES.items():
        r = rep.setdefault("areas", {}).setdefault(name, {})
        before = client_log().count(f"needs {name})")
        far, length = glide(n, g, gate)
        pushes = client_log().count(f"needs {name})") - before
        r["without_pass"] = {"reached_m": far, "of_m": length, "pushbacks": pushes,
                             "ok": pushes > 0 and far < length - 5}
        send(name)
        time.sleep(6)
        before = client_log().count(f"needs {name})")
        far, length = glide(n, g, gate)
        pushes = client_log().count(f"needs {name})") - before
        r["with_pass"] = {"reached_m": far, "of_m": length, "pushbacks": pushes,
                          "zone": n.area_id(), "ok": pushes == 0 and far >= length - 3}
        print(name, r, flush=True)
        save(rep)


def wait_ready(m, seconds=90.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        s = pj.state(m)
        if s["machine"] == 2 and s["scene"] == 1 and struct.unpack("<I", m.read(m.base + 0x11EAC2C, 4))[0] == 1:
            return True
        time.sleep(1)
    return False


def wait_for(m, text: str, sub: str, seconds: float) -> bool:
    """Attend la ligne `text` dans le journal du client puis la sous-phase `sub` prete."""
    end = time.time() + seconds
    while time.time() < end:
        if text in client_log() and pj.state(m)["sub"] == sub and wait_ready(m, 5):
            return True
        time.sleep(1)
    return False


def test_route(rep, route: str):
    m = rp.ProcessMemory.attach()
    rp.install(m)
    key = cl.CHAPTER_KEYS[route]
    regions = cl.route_regions(db.REGIONS, route)[1:]
    for region in regions:
        first = next(i for i, c in enumerate(db.CHAPTERS) if c["region"] == region)
        start, park = cl.start_chapter(first), cl.park_chapter(first)
        chap = db.CHAPTERS[start]["chapter"]
        r = rep.setdefault("chapters", {}).setdefault(region, {})
        if r.get("locked_ok") and r.get("opened_ok"):
            continue
        st, who, phase, sub = cl.STARTS[start]
        if not wait_ready(m):
            r["error"] = "jeu pas pret avant le saut"
            save(rep)
            continue
        time.sleep(32)                                   # pause du client entre deux sauts
        pj.set_route(m, st, who)
        pj.jump(m, phase, sub, wait=60)
        lock_line = f"Chapter {chap} locked (needs {key}): back to {cl.STARTS[park][3]}"
        r["locked_ok"] = wait_for(m, lock_line, cl.STARTS[park][3], 150)
        r["park"] = cl.STARTS[park][3]
        r["check_sent_while_locked"] = f"({db.CHAPTERS[start]['name']})" in client_log()
        send(key)
        open_line = f"Chapter key received: chapter {chap} starts ({sub})"
        r["opened_ok"] = wait_for(m, open_line, sub, 150)
        end = time.time() + 40
        while time.time() < end and f"({db.CHAPTERS[start]['name']})" not in client_log():
            time.sleep(1)
        r["check_sent_after_key"] = f"({db.CHAPTERS[start]['name']})" in client_log()
        r["start"] = sub
        print(region, chap, r, flush=True)
        save(rep)


if __name__ == "__main__":
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    part = sys.argv[1]
    if part == "areas":
        test_areas(report)
    else:
        test_route(report, part)
    print("fini", part, flush=True)
