from nier_automata.data import worlddb as db
from nier_automata.data.tables import item_name_to_id
from nier_automata.data.towerkeys import TOWER_KEYS, keys_in_scope, to_give_back, to_remove
from nier_automata.game.loop import make_trackers, tick
from nier_automata.game.notify import MAX_LEN
from nier_automata.game.state import ClientState

from test_loop import FakeGame, scope

FOREST, OCEAN, PARK = TOWER_KEYS["Forest Access Key"], TOWER_KEYS["Ocean Access Key"], TOWER_KEYS["Park Access Key"]


class KeyGame(FakeGame):
    def give(self, name):
        if name in TOWER_KEYS:
            self.owned.add(TOWER_KEYS[name])
            return True
        return super().give(name)

    def remove_item(self, item_id):
        self.owned.discard(item_id)
        return True


def setup(tower=True):
    sc = scope(goal=db.GOAL_ENDING_E)
    sc.tower_keys = tower
    s = ClientState(seed="S", slot=1, save_slot=None, ap_weapons={0x42E, 0x4EC}, linked=True, route="C",
                    chapters=set(range(100)))
    return s, make_trackers(s, sc)


def test_keys_only_when_the_tower_is_played():
    assert keys_in_scope(db.REGIONS) == list(TOWER_KEYS)
    assert keys_in_scope([r for r in db.REGIONS if r != "C17"]) == []
    ids = item_name_to_id()
    assert all(n in ids and len(n) <= MAX_LEN for n in TOWER_KEYS) and len(set(ids.values())) == len(ids)


def test_which_keys_to_take_back_and_to_give_back():
    assert to_remove({FOREST, OCEAN, 5}, ["Ocean Access Key"]) == [FOREST]
    assert to_remove({5}, []) == []
    assert to_give_back({OCEAN}, ["Ocean Access Key", "Park Access Key"]) == ["Park Access Key"]


def test_a_key_given_by_the_game_is_taken_back():
    s, tr = setup()
    g = KeyGame(phase="160_10_CD_1_Forest_Castle_9S")
    g.owned = {FOREST}
    tick(g, s, [], tr)
    assert FOREST not in g.owned


def test_the_third_key_bringing_the_two_others_back_is_handled():
    # vu par le testeur : en recevant la 3e cle, le jeu remet les deux autres dans l'inventaire
    s, tr = setup()
    g = KeyGame(phase="240_10_CD_Amusement_Park_9S")
    g.owned = {FOREST, OCEAN, PARK}
    tick(g, s, ["Ocean Access Key"], tr)
    assert g.owned == {OCEAN}


def test_keys_from_the_multiworld_are_given_and_come_back_after_a_reload():
    s, tr = setup()
    g = KeyGame(phase="260_00_CD_Ruined_City_9S")
    names = list(TOWER_KEYS)
    tick(g, s, names, tr)
    assert g.owned == {FOREST, OCEAN, PARK}
    g.owned = set()                                   # sauvegarde rechargee
    tick(g, s, names, tr)
    assert g.owned == {FOREST, OCEAN, PARK}


def test_nothing_is_touched_once_the_tower_is_open_or_without_the_option():
    s, tr = setup()
    g = KeyGame(phase="270_CD_Tower_9S")
    g.owned = {FOREST}
    tick(g, s, [], tr)
    assert s.tower_opened and g.owned == {FOREST}
    g2 = KeyGame(phase="275_CD_Tower_walk_9S")        # le jeu a consomme les cles : on ne les redonne pas
    tick(g2, s, list(TOWER_KEYS), tr)
    s.next_item_index = 3
    tick(g2, s, list(TOWER_KEYS), tr)
    assert g2.owned == {FOREST, OCEAN, PARK}          # donnees une fois par la file normale, pas plus
    s3, tr3 = setup(tower=False)
    g3 = KeyGame(phase="160_10_CD_1_Forest_Castle_9S")
    g3.owned = {FOREST}
    tick(g3, s3, [], tr3)
    assert g3.owned == {FOREST}
