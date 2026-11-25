from nier_automata.data import worlddb as db
from nier_automata.game import worldmap as wm


def test_location_position_for_named_checks():
    c, p, a = db.CHESTS[0], db.PICKUPS[0], db.ACCESS_POINTS[0]
    assert db.location_position(c["name"]) == tuple(c["pos"])
    assert db.location_position(p["name"]) == tuple(p["pos"])
    assert db.location_position(a["name"]) == tuple(a["pos"])
    assert db.location_position("Level 5") is None


def test_world_to_pixel_uses_map_origin_and_scale():
    m = wm.MapInfo(x0=-100.0, z0=-50.0, scale=2.0, width=400, height=300)
    assert m.to_pixel(-100.0, -50.0) == (0.0, 0.0)
    assert m.to_pixel(0.0, 50.0) == (50.0, 50.0)
    assert m.inside(0.0, 50.0) and not m.inside(5000.0, 0.0)


def test_markers_hints_first_then_remaining_checks():
    c0, c1 = db.CHESTS[0], db.CHESTS[1]
    hints = [("Grappin", "Niicotine", c1["name"]), ("X", "Bob", "Level 9")]     # Level : pas de position
    marks = wm.markers(hints, remaining={c0["name"], c1["name"], "Level 9"}, player=(1.0, 2.0, 3.0))
    kinds = [(m.kind, m.label) for m in marks]
    assert ("hint", f"Grappin (Niicotine) - {c1['name']}") in kinds
    assert ("check", c0["name"]) in kinds and ("check", c1["name"]) not in kinds     # deja en indice
    assert marks[-1].kind == "player" and (marks[-1].x, marks[-1].z) == (1.0, 3.0)
    assert not any("Level" in m.label for m in marks)


def test_map_shows_indoor_rooms_in_orange():
    # les salles interieures (grottes, sous-sols) sont dessinees en orange : un check de grotte tombe dessus
    import io
    import pytest
    Image = pytest.importorskip("PIL.Image")
    img = Image.open(io.BytesIO(wm.map_png())).convert("RGB")
    info = wm.load_info()
    cave = [c for c in db.CHESTS if "Deep Cave" in c["name"]]
    assert cave
    orange = 0
    for c in cave:
        px, py = info.to_pixel(c["pos"][0], c["pos"][2])
        r, g, b = img.getpixel((int(px), int(py)))
        orange += r > b + 40
    assert orange >= len(cave) * 0.8
