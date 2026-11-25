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



def test_self_destruct_waits_while_flying_but_edrug_does_not():
    # vu en jeu (prologue en vol, action 0x84) : le jeu annule l'autodestruction en 0,5 s sans rien faire,
    # le piege serait perdu ; l'E-Drug, lui, s'affiche normalement en vol
    from nier_automata.game.traps import effect_allowed
    fly = dict(world_loaded=True, menu_closed=True, action=0x84, hp=500)
    assert not effect_allowed(**fly, kind="selfdestruct")
    assert effect_allowed(**fly, kind="edrug")
    assert effect_allowed(world_loaded=True, menu_closed=True, action=0, hp=500, kind="selfdestruct")
    hack = {**fly, "action": 0x42}                                  # mini-jeu de piratage de 9S : pareil
    assert not effect_allowed(**hack, kind="selfdestruct") and effect_allowed(**hack, kind="edrug")


def test_game_effects_wait_during_in_world_cutscene():
    # vu en jeu (intro du boss Adam, 56_AB_Danchi_Boss_EV1 et 56_10) : monde charge, aucun menu, action 0,
    # mais [0x11EAC4C] vaut 2 pendant la cinematique et 0 en combat / en ville
    from nier_automata.game.traps import effect_allowed
    ok = dict(world_loaded=True, menu_closed=True, action=0, hp=500)
    for kind in ("selfdestruct", "edrug"):
        assert not effect_allowed(**ok, kind=kind, cutscene=True)
        assert effect_allowed(**ok, kind=kind, cutscene=False)


def test_cutscene_hold_delays_traps_but_never_forever():
    # tous les pieges (sauf l'argent) attendent la fin d'une cinematique ; si le signal du jeu restait bloque,
    # on laisse passer apres max_wait pour ne pas geler la file d'objets
    from nier_automata.game.traps import CutsceneHold
    h = CutsceneHold(max_wait=300)
    assert not h.hold(False, now=0)
    assert h.hold(True, now=10) and h.hold(True, now=200)
    assert not h.hold(True, now=311)                 # 300 s de cinematique continue : on laisse passer
    assert not h.hold(False, now=320)
    assert h.hold(True, now=330)                     # nouvelle cinematique : le compteur repart


def test_self_destruct_needs_several_clear_reads_in_a_row():
    # vu en jeu : au debut du piratage l'action vaut 0xAF (lancement), puis 0x42, retombe a 0 pendant ~0,1 s,
    # puis 0x42 ; une seule lecture a 0 ne suffit donc pas
    from nier_automata.game.traps import effect_allowed, self_destruct_clear
    ok = dict(world_loaded=True, menu_closed=True, hp=500, kind="selfdestruct")
    assert not effect_allowed(action=0xAF, **ok)
    assert self_destruct_clear([0, 0, 0])
    assert not self_destruct_clear([0, 0x42, 0x42]) and not self_destruct_clear([0, 0, 0xAF])
    assert not self_destruct_clear([0x84, 0, 0])


def test_lethal_traps_option_kills_only_when_damage_exceeds_hp():
    # avis du testeur : "un piege ne tue jamais" doit etre une option. Ecrire 0 PV ne tue pas (verifie en jeu) :
    # le client passe par la vraie mort du jeu, donc la fonction dit seulement si le piege doit tuer.
    from nier_automata.game.traps import trap_kills
    assert damage_after_trap(hp=30, max_hp=1000, percent=10) == 1
    assert not trap_kills(hp=30, max_hp=1000, percent=10, lethal=False)
    assert trap_kills(hp=30, max_hp=1000, percent=10, lethal=True)
    assert trap_kills(hp=100, max_hp=1000, percent=10, lethal=True)
    assert not trap_kills(hp=500, max_hp=1000, percent=10, lethal=True)
