from nier_automata.data.items_data import TRAP_ITEMS
from nier_automata.data.tables import item_name_to_id
from nier_automata.game.traps import damage_after_trap, funds_after_trap


def test_damage_trap_5_percent():
    assert damage_after_trap(hp=620, max_hp=1058, percent=5) == 620 - 53


def test_damage_trap_10_percent():
    assert damage_after_trap(hp=620, max_hp=1058, percent=10) == 620 - 106


def test_damage_trap_never_kills():
    assert damage_after_trap(hp=30, max_hp=1058, percent=10) == 1


def test_money_trap_takes_10_percent():
    assert funds_after_trap(1720, percent=10) == 1548
    assert funds_after_trap(0, percent=10) == 0


def test_trap_items_registered():
    ids = item_name_to_id()
    assert {"Damage Trap", "Heavy Damage Trap", "Money Trap"} <= set(TRAP_ITEMS)
    assert all(name in ids for name in TRAP_ITEMS)


def test_enemy_trap_registered():
    assert TRAP_ITEMS["Enemy Trap"] == ("spawn", 3)


def test_system_failure_traps_registered():
    ids = item_name_to_id()
    for name, ability in (("System Failure: Light Attack", "Light Attack"),
                          ("System Failure: Heavy Attack", "Heavy Attack"),
                          ("System Failure: Pod Fire", "Pod Fire")):
        assert TRAP_ITEMS[name] == ("jam:" + ability, 20) and name in ids


def test_damage_trap_strength_is_an_option():
    # avis du testeur : 10 % des PV max ne sert a rien pour un joueur moyen -> reglable
    from nier_automata.game.traps import damage_percent
    assert TRAP_ITEMS["Damage Trap"] == ("damage", 1) and TRAP_ITEMS["Heavy Damage Trap"] == ("damage", 2)
    assert damage_percent(1, 25) == 25 and damage_percent(2, 25) == 50
    assert damage_percent(2, 50) == 90                       # plafonne : un piege ne vide jamais la barre
    assert damage_after_trap(hp=1000, max_hp=1000, percent=damage_percent(2, 50)) == 100


def test_game_effect_traps_registered_and_guarded():
    # avis du testeur : pieges autodestruction et E-Drug (effets du jeu lui-meme)
    from nier_automata.game.traps import effect_allowed
    ids = item_name_to_id()
    assert TRAP_ITEMS["Self-Destruct Trap"] == ("selfdestruct", 0) and "Self-Destruct Trap" in ids
    assert TRAP_ITEMS["E-Drug Trap"] == ("edrug", 0) and "E-Drug Trap" in ids
    ok = dict(world_loaded=True, menu_closed=True, action=0, hp=500)
    assert effect_allowed(**ok)
    assert not effect_allowed(**{**ok, "world_loaded": False})      # chargement, dialogue, cinematique
    assert not effect_allowed(**{**ok, "menu_closed": False})
    assert not effect_allowed(**{**ok, "action": 0x38})             # deja en autodestruction
    assert not effect_allowed(**{**ok, "hp": 1})


def test_lethal_traps_option():
    # avis du testeur : "un piege ne tue jamais" doit etre une option
    assert damage_after_trap(hp=30, max_hp=1000, percent=10) == 1
    assert damage_after_trap(hp=30, max_hp=1000, percent=10, lethal=True) == 0
    assert damage_after_trap(hp=500, max_hp=1000, percent=10, lethal=True) == 400
