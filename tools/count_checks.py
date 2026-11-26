"""Compte les checks, les verrous et les objets d'une partie, par objectif, avec les options par defaut.
Meme calcul que nier_automata/world.py (generate_early, _spots, create_items), sans Archipelago.

    python tools/count_checks.py            tableau lisible
    python tools/count_checks.py md         tableaux Markdown pour le README
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.data import gagendings  # noqa: E402
from nier_automata.data import worlddb as db  # noqa: E402
from nier_automata.data.areas import passes_in_scope  # noqa: E402
from nier_automata.data.chapterlocks import key_counts  # noqa: E402
from nier_automata.data.items_data import FISH, MATERIALS, POD_PROGRAMS  # noqa: E402
from nier_automata.data.routes import keys_in_scope  # noqa: E402
from nier_automata.data.tables import (SHOP_PLACES_ORDER, SHOP_REGION, pool_weapon_count, quest_excluded,  # noqa: E402
                                       shop_missable)
from nier_automata.data.towerkeys import keys_in_scope as tower_keys_in_scope  # noqa: E402
from nier_automata.data.weapons import STARTING_WEAPONS, WEAPONS  # noqa: E402

# options par defaut (nier_automata/options.py)
DEFAULTS = dict(story_route=0, story_chapter=4, weapon_checks=8, max_level_check=20, shop_checks=2, ap_items_per_area=3,
                pod_program_checks=4, abilities=3, area_locks=1, trap_percentage=20)
GOALS = [("story_progress (default: route A, chapter 4)", db.GOAL_STORY), ("ending_a", db.GOAL_ENDING_A),
         ("ending_b", db.GOAL_ENDING_B), ("ending_cd", db.GOAL_ENDING_CD), ("ending_e", db.GOAL_ENDING_E)]


def count(goal: int, area_locks: int = DEFAULTS["area_locks"], fish=False, gag=False, items=False) -> dict:
    d = DEFAULTS
    scope = db.make_scope(goal=goal, story_checks=db.chapters_until("ABC"[d["story_route"]], d["story_chapter"]),
                          chest_checks=True, ap_items_per_area=d["ap_items_per_area"], access_point_checks=True,
                          quest_checks=True, weapon_checks=d["weapon_checks"], max_level_check=d["max_level_check"],
                          item_checks=items)
    regions = set(scope.regions)
    endings = db.ending_checks(scope.goal, scope.regions)
    passes = passes_in_scope(scope.regions, late=area_locks == 2) if area_locks else []
    route_keys = keys_in_scope(scope.regions)
    chapter_keys = key_counts(scope.regions)
    tower_keys = tower_keys_in_scope(scope.regions)

    def qx(q):      # meme regle que world._quest_excluded
        return quest_excluded(q, scope.regions) or (bool(passes) and q["region"].startswith("A"))

    cats = {}       # categorie -> [total, jamais d'objet important]

    def add(name, total, excluded=0):
        cats[name] = [total, excluded]

    add("Story chapters", scope.chapters)
    add("Chests", len(scope.chests), sum(1 for i in scope.chests if db.CHESTS[i].get("excluded")))
    add("AP Items", len(scope.pickups), sum(1 for i in scope.pickups if db.PICKUPS[i].get("excluded")))
    add("Access points", len(scope.access_points),
        sum(1 for i in scope.access_points if db.ACCESS_POINTS[i].get("excluded")))
    add("Side quests", len(scope.quests), sum(1 for i in scope.quests if qx(db.QUESTS[i])))
    add("Main endings", len(endings))
    add("Levels", max(0, scope.max_level - 1))
    shops = [(p, k) for p in SHOP_PLACES_ORDER if SHOP_REGION[p] in regions for k in range(d["shop_checks"])]
    add("Shop slots", len(shops), sum(1 for p, _ in shops if shop_missable(p, scope.regions)))
    add("Weapons found", scope.weapon_checks, scope.weapon_checks)
    add("Pod programs found", d["pod_program_checks"], d["pod_program_checks"])
    if items:
        add("Materials (item_checks)", len(MATERIALS), len(MATERIALS))
    if fish:
        add("Fish (fish_checks)", len(FISH), len(FISH))
    if gag:
        n = len(gagendings.letters_in_scope(scope.regions))
        add("Joke endings (gag_ending_checks)", n, n)
    total = sum(t for t, _ in cats.values())
    excluded = sum(e for _, e in cats.values())
    open_locs = total - excluded
    locks = {"Area Passes": len(passes), "Route items": len(route_keys), "Chapter keys": sum(chapter_keys.values()),
             "Tower keys": len(tower_keys)}
    n_locks = sum(locks.values())
    candidates = len(set(WEAPONS) - STARTING_WEAPONS)
    weapons = pool_weapon_count(max(0, open_locs - d["abilities"] - n_locks), total, candidates)
    pool = d["abilities"] + weapons + n_locks
    programs = max(0, min(len(POD_PROGRAMS), (open_locs - pool) // 2))
    rest = total - pool - programs
    return {"regions": len(scope.regions), "cats": cats, "total": total, "excluded": excluded, "open": open_locs,
            "locks": locks, "n_locks": n_locks, "passes": passes,
            "items": {"Weapons": weapons, "Abilities": d["abilities"], "Locks": n_locks, "Pod programs": programs,
                      "Recovery, boosts, money and traps": rest}}


def markdown() -> str:
    res = [(name.split(" ")[0], count(g)) for name, g in GOALS]
    head = "| | " + " | ".join(f"`{n}`" for n, _ in res) + " |\n|---|" + "---:|" * len(res) + "\n"
    out = ["**Checks by kind**\n\n" + head]
    for cat in res[-1][1]["cats"]:
        out.append(f"| {cat} | " + " | ".join(str(r["cats"][cat][0]) for _, r in res) + " |\n")
    out.append("| **Total** | " + " | ".join(f"**{r['total']}**" for _, r in res) + " |\n")
    out.append("| of which never hold an important item | " + " | ".join(str(r["excluded"]) for _, r in res) + " |\n")
    out.append("\n**Progression locks**\n\n" + head)
    for lock in res[-1][1]["locks"]:
        out.append(f"| {lock} | " + " | ".join(str(r["locks"][lock]) for _, r in res) + " |\n")
    out.append("| **Total** | " + " | ".join(f"**{r['n_locks']}**" for _, r in res) + " |\n")
    out.append("\n**Items in the pool**\n\n" + head)
    for item in res[-1][1]["items"]:
        out.append(f"| {item} | " + " | ".join(str(r["items"][item]) for _, r in res) + " |\n")
    out.append("| **Total** (one per check) | " + " | ".join(f"**{r['total']}**" for _, r in res) + " |\n")
    return "".join(out)


if __name__ == "__main__":
    if sys.argv[1:] == ["md"]:
        print(markdown())
    else:
        for name, g in GOALS:
            r = count(g)
            print(f"== {name} : {r['total']} checks ({r['excluded']} never important), {r['n_locks']} locks, "
                  f"{r['regions']} big chapters")
            print("   checks", {k: v[0] for k, v in r["cats"].items()})
            print("   locks ", r["locks"], r["passes"])
            print("   items ", r["items"])
        e = count(db.GOAL_ENDING_E, area_locks=2, fish=True, gag=True, items=True)
        print("== ending_e, area_locks all + fish + joke endings + materials :", e["total"], "checks,", e["n_locks"],
              "locks", {k: v[0] for k, v in e["cats"].items() if "(" in k})
