from nier_automata.data import worlddb as db


def test_database_loaded_and_consistent():
    assert len(db.CHAPTERS) > 100 and db.CHAPTERS[0]["route"] == "A"
    assert [c["route"] for c in db.CHAPTERS] == sorted((c["route"] for c in db.CHAPTERS))   # A puis B puis C
    names = [x["name"] for cat in (db.CHAPTERS, db.CHESTS, db.PICKUPS, db.ACCESS_POINTS, db.QUESTS) for x in cat]
    assert len(names) == len(set(names))
    assert all(x["region"] in db.REGIONS for cat in (db.CHESTS, db.PICKUPS, db.ACCESS_POINTS, db.QUESTS)
               for x in cat)


def test_scope_by_goal():
    a = sum(1 for c in db.CHAPTERS if c["route"] == "A")
    b = sum(1 for c in db.CHAPTERS if c["route"] == "B")
    assert db.chapter_count(db.GOAL_STORY, 12) == 12
    assert db.chapter_count(db.GOAL_ENDING_A, 12) == a
    assert db.chapter_count(db.GOAL_ENDING_B, 12) == a + b
    assert db.chapter_count(db.GOAL_ENDING_CD, 12) == len(db.CHAPTERS)
    assert db.regions_in_scope(12) == ["A01", "A02", "A03", "A04"]       # 12e chapitre = 04-01
    assert db.regions_in_scope(a)[-1] == "A10" and "B01" not in db.regions_in_scope(a)


def test_chapter_matching_uses_route():
    i = db.match_chapter("30_AB_Ruined_City_ForcedLanding", "A")
    j = db.match_chapter("30_AB_Ruined_City_ForcedLanding", "B")
    assert db.CHAPTERS[i]["name"] == "Story A 02-01: Landing at the City Ruins"
    assert db.CHAPTERS[j]["route"] == "B" and db.CHAPTERS[j]["chapter"] == "02-01"
    assert db.match_chapter("SIGNIN", "A") is None


def test_route_detection_only_moves_forward():
    assert db.next_route("A", "30_AB_Ruined_City_ForcedLanding") == "A"     # partage : on garde
    assert db.next_route("A", "00_00_B_RobotM_Pro_RobotBrother") == "B"     # propre a la route B
    assert db.next_route("B", "10_CD_Ruined_City_9S") == "C"
    assert db.next_route("C", "00_30_A_RobotM_Prologue_STG1") == "C"        # selection de chapitre : pas de retour


def test_nearest_chest_within_radius_and_not_opened():
    c = db.CHESTS[0]
    x, y, z = c["pos"]
    assert db.nearest(db.CHESTS, (x + 1.0, y + 1.5, z), opened=set()) == 0
    assert db.nearest(db.CHESTS, (x + 1.0, y + 1.5, z), opened={0}) != 0
    assert db.nearest(db.CHESTS, (x + 500.0, y, z + 500.0), opened=set(), radius=5.0) is None


def test_level_region_follows_recommended_curve():
    assert db.level_region(2) == "A02" and db.level_region(7) == "A03" and db.level_region(10) == "A04"
    assert db.level_region(30)[0] == "B" and db.level_region(49)[0] == "C"


def test_power_gate_grows_with_progress():
    regs = db.regions_in_scope(len(db.CHAPTERS))
    need = [db.required_weapons(regs.index(r), len(regs), 20) for r in regs]
    assert need[0] == 0 and need == sorted(need) and need[-1] <= 15


def test_selected_pickups_per_area():
    sel = db.selected_pickups(2, db.regions_in_scope(12))
    assert sel and all(db.PICKUPS[i]["k"] <= 2 for i in sel)
    assert all(db.PICKUPS[i]["region"] in ("A01", "A02", "A03", "A04") for i in sel)


def test_scope_default_goal_is_small_and_consistent():
    s = db.make_scope(goal=db.GOAL_STORY, story_checks=12, chest_checks=True, ap_items_per_area=3,
                      access_point_checks=True, quest_checks=True, weapon_checks=8, max_level_check=20,
                      item_checks=False)
    assert s.chapters == 12 and s.regions == ("A01", "A02", "A03", "A04")
    assert s.chests and all(db.CHESTS[i]["region"] in s.regions for i in s.chests)
    assert all(db.PICKUPS[i]["k"] <= 3 for i in s.pickups)
    assert all(db.ACCESS_POINTS[i]["region"] in s.regions for i in s.access_points)
    assert s.max_level == 10            # niveau conseille de la derniere region (A04), pas 20
    off = db.make_scope(db.GOAL_STORY, 12, False, 0, False, False, 0, 0, False)
    assert not off.chests and not off.pickups and not off.access_points and not off.quests


def test_scope_full_game_has_everything():
    s = db.make_scope(db.GOAL_ENDING_E, 12, True, 8, True, True, 8, 50, False)
    assert s.chapters == len(db.CHAPTERS) and len(s.chests) == len(db.CHESTS)
    assert len(s.pickups) == len(db.PICKUPS) and len(s.quests) == len(db.QUESTS) and s.max_level == 50


def test_power_gate_is_gentle_for_small_games():
    # 4 regions, 32 armes : pas plus de 2 armes de plus par region (le prologue n'a que 5 emplacements)
    assert [db.required_weapons(i, 4, 32) for i in range(4)] == [0, 2, 4, 6]


def test_quests_done_from_status_array():
    # valeurs du jeu : -1 jamais suivie, 100+n en cours, 1 CLR (objectif atteint, pas rendue), 2/3/4 terminee
    n = max(q["status_index"] for q in db.QUESTS) + 1
    status = [-1] * n
    status[db.QUESTS[0]["status_index"]] = 2
    status[db.QUESTS[1]["status_index"]] = 1
    status[db.QUESTS[2]["status_index"]] = 104
    status[db.QUESTS[3]["status_index"]] = 4
    assert db.quests_done(status) == {0, 3}
    assert db.quests_done([]) == set()          # lecture ratee : rien


def test_same_subphase_name_in_two_chapters_is_told_apart_by_phase_number():
    # verifie en jeu : "80_00_AB_Pascal_Village" existe au chapitre 05-01 (p100) et 07-01 (p200)
    a = db.match_chapter("80_00_AB_Pascal_Village", "A", phase_id=0x100)
    b = db.match_chapter("80_00_AB_Pascal_Village", "A", phase_id=0x200)
    assert db.CHAPTERS[a]["chapter"] == "05-01" and db.CHAPTERS[b]["chapter"] == "07-01"
    assert db.match_chapter("80_00_AB_Pascal_Village", "A") == a          # sans numero : le premier


def test_goal_by_big_chapter_and_route():
    # avis du testeur : objectif par grand chapitre (1 a 17), pas par nombre de sous-chapitres
    n = db.chapters_until("A", 4)
    assert db.CHAPTERS[n - 1]["route"] == "A" and db.CHAPTERS[n - 1]["chapter"].startswith("04-")
    assert n == max(i for i, c in enumerate(db.CHAPTERS) if c["route"] == "A" and c["chapter"][:2] == "04") + 1
    nb = db.chapters_until("B", 4)                       # meme chapitre, autre route : plus loin dans la partie
    assert nb > db.chapters_until("A", 10) and db.CHAPTERS[nb - 1]["route"] == "B"
    assert db.chapters_until("C", 17) == len(db.CHAPTERS)
    assert db.chapters_until("A", 15) == db.chapters_until("A", 10)      # borne a la route
    assert db.chapters_until("C", 3) == db.chapters_until("C", 11)
