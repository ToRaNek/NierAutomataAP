from nier_automata.game.notify import (
    CARRIER_ITEM, MAX_LEN, TEMPLATE, TEMPLATE_LEN, messages_for_item_send, template_for,
)


def test_constants_verified_in_game():
    assert CARRIER_ITEM == 959 and MAX_LEN == 17
    assert TEMPLATE == "Objet récupéré : <ITEM NAME>" and TEMPLATE_LEN == 28


def test_received_from_other_player():
    assert messages_for_item_send(1, 2, 1, "Hookshot", "Niicotine", "ToRaNek", "Chest 3") == [("De Niicotine : ", "Hookshot")]


def test_sent_to_other_player_shows_check_then_gift():
    assert messages_for_item_send(1, 1, 3, "Grappin", "ToRaNek", "Fifi", "Story Progress #2") == [
        ("Check : ", "Story Progress #2"), ("Pour Fifi : ", "Grappin")]


def test_own_item_check():
    assert messages_for_item_send(1, 1, 1, "Soins legers", "ToRaNek", "ToRaNek", "Level 2") == [
        ("Check : ", "Level 2"), ("Pour toi : ", "Soins legers")]


def test_unrelated_event_ignored():
    assert messages_for_item_send(1, 2, 3, "X", "A", "B", "L") == []


def test_template_fits_and_keeps_placeholder():
    for prefix in ("De Niicotine : ", "Pour Un_Nom_Tres_Long_De_Joueur : ", "Check : "):
        t = template_for(prefix)
        assert len(t) <= TEMPLATE_LEN and t.endswith("<ITEM NAME>")


def test_item_name_truncated():
    (_, item), = messages_for_item_send(1, 2, 1, "Progressive Hookshot Deluxe", "A", "B", "L")
    assert len(item) <= MAX_LEN


from nier_automata.game.notify import encode_fixed


def test_encode_fixed_never_exceeds_capacity_with_emoji():
    b = encode_fixed("😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀", 17)   # 2 unites UTF-16 par emoji
    assert len(b) == 17 * 2
    assert b.decode("utf-16-le", "surrogatepass").count("\ud83d") == b.decode("utf-16-le", "surrogatepass").count("\ude00")


def test_encode_fixed_strips_control_and_pads():
    b = encode_fixed("A\nB\x00C", 5)
    assert b == "ABC".encode("utf-16-le") + b"\0\0" * 2


def test_shop_location_shortened_in_notification():
    msgs = messages_for_item_send(1, 1, 2, "Full Recovery", "ToRaNek", "Niicotine", "Shop Resistance Camp #1")
    assert msgs[0] == ("Check : ", "Magasin Camp #1")
    msgs = messages_for_item_send(1, 1, 2, "X", "ToRaNek", "Niicotine", "Shop Forest Castle #2")
    assert msgs[0] == ("Check : ", "Magasin Foret #2")


def test_story_location_shortened_in_notification():
    msgs = messages_for_item_send(1, 1, 2, "X", "ToRaNek", "Niicotine", "Story A 02-01: Landing at the City Ruins")
    assert msgs[0] == ("Check : ", "Landing at the Ci")


def test_short_names_for_new_check_types():
    from nier_automata.game.notify import short_location
    assert short_location("Story A 02-01: Landing at the City Ruins", "en") == "Landing at the Ci"
    assert short_location("Chest: City Ruins: Shopping Center #12", "en") == "City Ruins: S #12"
    assert short_location("AP Item: Desert Zone: Housing Complex #2", "en") == "Desert Zone: H #2"
    assert short_location("Access Point: Desert: Camp", "en") == "Desert: Camp"
    assert short_location("Quest: Lost Girl", "en") == "Lost Girl"
    assert all(len(short_location(n, "en")) <= 17 for n in (
        "Chest: Abandoned Factory: Underground Area #18", "Access Point: Forest Zone: Royal Chamber"))


def test_access_point_bits_decoding():
    from nier_automata.game.game import decode_bits
    import struct
    raw = struct.pack("<4I", 0x80000000 | (0x80000000 >> 3), 0x80000000 >> 1, 0, 0)
    assert decode_bits(raw) == {0, 3, 33}


def test_own_filler_is_silent_in_multiplayer():
    msgs = messages_for_item_send(1, 1, 1, "Small Recovery", "Me", "Me", "Level 3", lang="en", hide_own=True)
    assert msgs == [("Check: ", "Level 3")]                       # pas de ligne "For you"
    solo = messages_for_item_send(1, 1, 1, "Small Recovery", "Me", "Me", "Level 3", lang="en")
    assert solo == [("Check: ", "Level 3"), ("For you: ", "Small Recovery")]
