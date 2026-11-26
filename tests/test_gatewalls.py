import math
import struct

from nier_automata.data import gatewalls as gw
from nier_automata.data.areas import AREA_PASSES
from nier_automata.game.gatewall import GateWalls, OP_WALLS


def test_every_pass_has_a_gate():
    assert set(gw.GATES) == set(AREA_PASSES)
    for (x, y, z), (dx, dz) in gw.GATES.values():
        assert abs(math.hypot(dx, dz) - 1) < 0.01


def test_wall_is_across_the_way_just_before_the_entrance():
    x1, y, z1, x2, z2, h = gw.wall("Park Pass")                      # on arrive vers +x
    assert math.isclose(x1, x2) and math.isclose(x1, 313.1 - gw.BEFORE, abs_tol=1e-4)
    assert math.isclose(abs(z2 - z1), gw.WIDTH) and math.isclose((z1 + z2) / 2, 344.5)
    assert y < 4.6 - 8 and y + h > 4.6 + 20                          # couvre large : hauteur du sol incertaine
    x1, y, z1, x2, z2, h = gw.wall("Desert Pass")                    # arrivee en biais : mur perpendiculaire
    assert abs((x2 - x1) * -0.5 + (z2 - z1) * -0.866) < 0.05


def test_locked_passes_drop_the_ones_received():
    passes = ["Desert Pass", "Park Pass", "Factory Pass"]
    assert gw.locked_passes(passes, []) == ["Desert Pass", "Park Pass", "Factory Pass"]
    assert gw.locked_passes(passes, ["Park Pass", "500 G"]) == ["Desert Pass", "Factory Pass"]
    assert gw.locked_passes([], []) == []


def test_text_fits_the_mod_field():
    for p in gw.GATES:
        t = gw.text_for(p)
        assert p in t and len(t) <= 63 and t.isascii()
    assert len(gw.pack(["Desert Pass", "Park Pass"])) == 2 * gw.WALL_SIZE


class FakeMod:
    def __init__(self, version=3, ok=b"\x01"):
        self.mod_version, self.pid, self.base, self.ok, self.sent = version, 7, 0x1000, ok, []

    def _ask(self, req, size):
        self.sent.append(req)
        return self.ok


def test_walls_are_sent_only_when_they_change():
    mem, g = FakeMod(), GateWalls()
    passes = ["Desert Pass", "Park Pass"]
    assert g.update(mem, passes, [])
    op, eye, target, fov, n = struct.unpack_from("<BQQQI", mem.sent[0])
    assert (op, n) == (OP_WALLS, 2) and eye == 0x1000 + 0x1020BC0 and len(mem.sent[0]) == 29 + 2 * gw.WALL_SIZE
    assert not g.update(mem, passes, []) and len(mem.sent) == 1          # rien de neuf
    assert g.update(mem, passes, ["Desert Pass"])                       # un Pass arrive : un panneau en moins
    assert struct.unpack_from("<BQQQI", mem.sent[1])[4] == 1
    assert g.update(mem, passes, ["Desert Pass", "Park Pass"])          # plus aucun : liste vide envoyee
    assert struct.unpack_from("<BQQQI", mem.sent[2])[4] == 0
    mem.pid = 8                                                         # jeu relance : on renvoie
    assert g.update(mem, passes, ["Desert Pass", "Park Pass"])


def test_nothing_without_the_mod_or_with_an_old_one():
    g = GateWalls()
    assert not g.update(object(), ["Desert Pass"], [])
    old = FakeMod(version=2)
    assert not g.update(old, ["Desert Pass"], []) and not old.sent
    bad = FakeMod(ok=b"\x00")
    assert not g.update(bad, ["Desert Pass"], [])
    assert not g.update(bad, ["Desert Pass"], []) and len(bad.sent) == 2      # refuse : reessaye au tour suivant
