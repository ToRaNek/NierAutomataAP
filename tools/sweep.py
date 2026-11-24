"""Balayage automatique en jeu : va a chaque coffre / AP Item des regions donnees, l'ouvre ou le ramasse avec la
manette injectee (tools/remote_pad.py) et note le resultat dans tools/sweep_report.json.

    python tools/sweep.py A02 [A03 ...] [--chests] [--pickups] [--max N]
Le client Archipelago doit tourner (il pose les AP Items et envoie les checks).
"""
import json
import math
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import remote_pad as rp  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402
from nier_automata.game import ap_items as apit  # noqa: E402
from nier_automata.game.spawner import entity_region  # noqa: E402

CHEST_VTABLE = 0xC7D708
CHEST_OPEN_OFFSET = 0xA8C
LOCKED_CHEST_VTABLE = 0xCE9478     # coffre verrouille (ba2016, piratage 9S), vu en jeu
REPORT = Path(__file__).with_name("sweep_report.json")
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0), (0.7, -0.7), (-0.7, -0.7), (0.7, 0.7), (-0.7, 0.7))


class Game:
    def __init__(self):
        self.m = rp.ProcessMemory.attach()
        self.cave = rp.install(self.m)

    @property
    def pl(self):
        return struct.unpack("<Q", self.m.read(self.m.base + 0x1020C88, 8))[0]

    def pos(self):
        return struct.unpack("<3f", self.m.read(self.pl + 0x50, 12))

    def phase(self):
        return self.m.read(self.m.base + 0xF64B20, 40).split(b"\0")[0].decode()

    def tp(self, tx, ty, tz):
        m, pl = self.m, self.pl
        x, y, z = self.pos()
        dx, dy, dz = tx - x, ty - y, tz - z
        blk = m.read(pl, 0x30000)
        ws = []
        for off in range(0, len(blk) - 12, 4):
            a, b, c = struct.unpack_from("<3f", blk, off)
            if abs(a - x) < 0.05 and abs(c - z) < 0.05 and abs(b - y) < 3:
                ws.append((pl + off, struct.pack("<3f", a + dx, b + dy, c + dz)))
        g = m.base + 0x1774F00
        gv = struct.unpack("<3f", m.read(g, 12))
        ws.append((g, struct.pack("<3f", gv[0] + dx, gv[1] + dy, gv[2] + dz)))
        for a, b in ws:
            m.write(a, b)

    def goto(self, target, settle=5.0):
        """Teleporte par bonds de 150 m (laisse le decor se charger) ; renvoie False si le joueur tombe."""
        tx, ty, tz = target
        for _ in range(40):
            x, y, z = self.pos()
            d = math.hypot(tx - x, tz - z)
            if d <= 150:
                break
            f = 150 / d
            self.tp(x + (tx - x) * f, max(y, ty) + 40, z + (tz - z) * f)
            time.sleep(1.5)
        self.tp(tx, ty + 1.0, tz)
        time.sleep(settle)
        x, y, z = self.pos()
        return abs(y - ty) < 6 and math.hypot(tx - x, tz - z) < 8

    def chest_at(self, p):
        base, size = entity_region(self.m)
        data = self.m.read(base, size)
        best = None
        for rva in (CHEST_VTABLE, LOCKED_CHEST_VTABLE):
            vt = struct.pack("<Q", self.m.base + rva)
            i = data.find(vt)
            while i != -1:
                if i % 8 == 0 and i + 0x5C <= len(data):
                    q = struct.unpack_from("<3f", data, i + 0x50)
                    d = math.dist(q, p)
                    if d < 4 and (best is None or d < best[1]):
                        best = (base + i, d, rva)
                i = data.find(vt, i + 8)
        self.last_class = best[2] if best else None
        return best[0] if best else None

    def opened(self, chest):
        if getattr(self, "last_class", None) == LOCKED_CHEST_VTABLE:
            return False                      # drapeau d'ouverture inconnu pour les coffres verrouilles
        return struct.unpack("<I", self.m.read(chest + CHEST_OPEN_OFFSET, 4))[0] != 0

    def walk_to(self, target, stop=1.3):
        """Marche vers la cible : un petit pas de calibrage donne le sens du stick (relatif a la camera)."""
        for _ in range(6):
            p0 = self.pos()
            if math.hypot(target[0] - p0[0], target[2] - p0[2]) <= stop:
                return
            rp.move(self.m, self.cave, 0, -1, 0.2)
            time.sleep(0.15)
            p1 = self.pos()
            fx, fz = p1[0] - p0[0], p1[2] - p0[2]
            n = math.hypot(fx, fz)
            if n < 0.05:
                continue
            fx, fz = fx / n, fz / n               # "avant" du stick dans le monde
            rx, rz = -fz, fx                      # "droite" (a verifier : on corrige au tour suivant sinon)
            dx, dz = target[0] - p1[0], target[2] - p1[2]
            d = math.hypot(dx, dz)
            if d <= stop:
                return
            f, r = (dx * fx + dz * fz) / d, (dx * rx + dz * rz) / d
            rp.move(self.m, self.cave, r * self.side, -f, min(0.6, max(0.1, (d - stop) / 6.0)))
            time.sleep(0.2)
            d2 = math.hypot(target[0] - self.pos()[0], target[2] - self.pos()[2])
            if d2 > d + 0.3 and abs(r) > 0.5:
                self.side = -self.side            # la droite etait inversee

    side = 1

    def interact_until(self, done, target):
        for k in range(6):
            if done():
                return True
            if math.dist(self.pos(), target) > 6 or k == 3:
                self.tp(target[0] + (1.5 if k < 3 else -1.5), target[1] + 0.5, target[2] + (0 if k < 3 else 1.0))
                time.sleep(1.5)
            self.walk_to(target)
            rp.press(self.m, self.cave, 0x20, 0.2)
            time.sleep(1.5)
        return done()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in flags else 999
    args = [a for a in args if not a.isdigit()]
    do_chests = "--chests" in flags or "--pickups" not in flags
    do_pickups = "--pickups" in flags or "--chests" not in flags
    g = Game()
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    todo = []
    if do_chests:
        todo += [("chest", i, c) for i, c in enumerate(db.CHESTS) if c["region"] in args]
    if do_pickups:
        todo += [("pickup", i, p) for i, p in enumerate(db.PICKUPS) if p["region"] in args and p["k"] <= 3]
    n = 0
    for kind, i, e in todo:
        name = e["name"]
        if report.get(name, {}).get("result") in ("ok", "already", "present"):
            continue
        if n >= limit:
            break
        n += 1
        pos = e["pos"]
        r = {"phase": g.phase(), "time": time.strftime("%H:%M:%S")}
        try:
            if "--open" not in flags and kind == "chest":
                # presence seule : on se place au-dessus (pas besoin d'atterrir) et on cherche l'objet coffre
                g.goto((pos[0], pos[1] + 25, pos[2]), settle=0.5)
                ch = None
                for _ in range(4):
                    g.tp(pos[0], pos[1] + 25, pos[2])
                    time.sleep(1.2)
                    ch = g.chest_at(pos)
                    if ch:
                        break
                r["result"] = "absent" if ch is None else ("already" if g.opened(ch) else "present")
            elif not g.goto((pos[0] + 1.2, pos[1], pos[2])):
                r["result"] = "unreachable"
                r["pos"] = [round(v, 1) for v in g.pos()]
            elif kind == "chest":
                ch = g.chest_at(pos)
                if ch is None:
                    r["result"] = "absent"
                elif g.opened(ch):
                    r["result"] = "already"
                else:
                    r["result"] = "ok" if g.interact_until(lambda: g.opened(ch), pos) else "not_opened"
            else:
                time.sleep(6)      # le client pose l'AP Item
                near = lambda: [o for o, q in apit.find_marked_objects(g.m).items() if math.dist(q, pos) < 8]
                objs = near()
                if not objs:
                    r["result"] = "absent"
                else:
                    q = struct.unpack("<3f", g.m.read(objs[0] + 0x50, 12))
                    g.tp(q[0] + 0.8, q[1] + 0.3, q[2])
                    time.sleep(3)
                    r["result"] = "ok" if g.interact_until(lambda: not near(), q) else "not_picked"
        except OSError as ex:
            r["result"] = f"error {ex}"
        report[name] = r
        print(name, "->", r["result"], flush=True)
        REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
