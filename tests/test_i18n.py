from nier_automata.game import i18n, notify, ap_items, shop, mail


def test_language_from_game_value():
    assert i18n.language_from_value(4) == "fr"
    assert i18n.language_from_value(1) == "en"
    assert i18n.language_from_value(3) == "de"
    assert i18n.language_from_value(99) == "en"


def test_text_falls_back_to_english():
    assert i18n.t("de", "for_you") == i18n.t("en", "for_you") == "For you: "
    assert i18n.t("fr", "for_you") == "Pour toi : "
    assert i18n.t("fr", "from", who="Niicotine") == "De Niicotine : "


def test_notifications_follow_language():
    en = notify.messages_for_item_send(1, 1, 2, "Grappin", "Me", "Niicotine", "Shop Resistance Camp #1", lang="en")
    assert en == [("Check: ", "Shop Camp #1"), ("For Niicotine: ", "Grappin")]
    fr = notify.messages_for_item_send(1, 2, 1, "Grappin", "Niicotine", "Me", "X", lang="fr")
    assert fr == [("De Niicotine : ", "Grappin")]


def test_pickup_shop_mail_texts_english():
    assert ap_items.pickup_text(1, 2, "Grappin", "Niicotine", lang="en") == ("For Niicotine: ", "Grappin")
    assert shop.description(1, 2, "Grappin", "Niicotine", True, lang="en") == "For Niicotine: Grappin (progression)"
    assert shop.description(1, None, None, None, False, lang="en") == "Archipelago item"
    assert mail.checks_body(["A"], 3, lang="en").startswith("Remaining checks: 1 / 3")
    assert "Grappin for Niicotine" in mail.hints_body([("Grappin", "Niicotine", "X")], lang="en")
    assert i18n.t("en", "hints_title", who="Niicotine") == "Hint from Niicotine"


def test_template_fits_any_original_length():
    for length in (20, 28, 40):
        t = notify.template_for("For Some_Long_Player_Name: ", length)
        assert t.endswith(notify.PLACEHOLDER) and len(t) <= length
