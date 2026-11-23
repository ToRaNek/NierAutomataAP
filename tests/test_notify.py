from nier_automata.game.notify import (
    CARRIER_ITEM, MAX_LEN, TEMPLATE, TEMPLATE_LEN, messages_for_item_send, template_for,
)


def test_constants_verified_in_game():
    assert CARRIER_ITEM == 959 and MAX_LEN == 17
    assert TEMPLATE == "Objet récupéré : <ITEM NAME>" and TEMPLATE_LEN == 28


def test_received_from_other_player():
    assert messages_for_item_send(1, 2, 1, "Hookshot", "Niicotine", "ToRaNek") == [("De Niicotine : ", "Hookshot")]


def test_sent_to_other_player():
    assert messages_for_item_send(1, 1, 3, "Grappin", "ToRaNek", "Fifi") == [("Pour Fifi : ", "Grappin")]


def test_own_item_found_by_self():
    assert messages_for_item_send(1, 1, 1, "Soins legers", "ToRaNek", "ToRaNek") == [("Trouvé : ", "Soins legers")]


def test_unrelated_event_ignored():
    assert messages_for_item_send(1, 2, 3, "X", "A", "B") == []


def test_template_fits_and_keeps_placeholder():
    for prefix in ("De Niicotine : ", "Pour Un_Nom_Tres_Long_De_Joueur : ", "Trouvé : "):
        t = template_for(prefix)
        assert len(t) <= TEMPLATE_LEN and t.endswith("<ITEM NAME>")


def test_item_name_truncated():
    (_, item), = messages_for_item_send(1, 2, 1, "Progressive Hookshot Deluxe", "A", "B")
    assert len(item) <= MAX_LEN
