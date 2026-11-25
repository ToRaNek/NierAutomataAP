# NieR:Automata for Archipelago

Archipelago world (`.apworld`) and client for **NieR:Automata (PC Steam, v1.04)**, all routes.
The client reads and edits the running game's memory (no game file is modified). In-game texts follow the
game language (English by default, French supported). [Version francaise](README.fr.md)

## Install
**With the launcher**: download `NierAutomataAP.exe` from the Releases and run it. It finds Archipelago,
installs/updates the `.apworld` in `custom_worlds`, then opens the NieR:Automata client.
You can pass it an `archipelago://name@server:port` link.

**Manually**: copy `nier_automata.apworld` into `<Archipelago>/custom_worlds`, then
Archipelago Launcher -> *NieR:Automata Client*.

Requirements: NieR:Automata **Steam v1.04**, Archipelago **0.6.8+**. Whoever generates the game also needs the
`.apworld`. Settings template: `NieR Automata.yaml`.

## Playing
1. Start the game and begin a **new game** (one per seed).
2. Start the client and connect. Saves are backed up to `%LOCALAPPDATA%\NierAutomataAP\backups`.
3. Keep the client window open: Archipelago commands (`!hint`, `!remaining`, chat...) are typed there.

## Checks
Everything is named after where it is, so a hint tells you where to go.
- **Story A 02-01: Landing at the City Ruins**: one check per story chapter (109 over routes A, B and C/D).
- **Chest: City Ruins #12**: every chest, named after its area. Hack-locked chests need 9S (route B on).
- **AP Item: Desert Zone: Housing Complex #2**: "AP Item" objects placed on the game's own collection points,
  1 to 8 per area; picking one up shows what it contains and for whom.
- **Access Point: Desert: Camp**: first activation of each access point.
- **Shop <place> #k**: "AP Item" entries at the top of the shops (Resistance Camp, Pascal's Village,
  Forest Castle); the description says what's inside and for whom.
- **Level n**, **Weapon Found #n**: levels reached, weapons found (removed from the inventory).
- **Pod Program Found #n**: Pod programs obtained in the game itself (shop, quest, pickup); like weapons they
  are taken back, you keep the ones the multiworld sends (`pod_program_checks`, 0 = leave them alone).
- **Ending A / B / C / D**: each main ending reached before the goal (`ending_checks`). The goal ending is
  not a check; joke endings are never checks.
- **Quest: <name>**: finishing a side quest. Most quests close after chapter 7 (checked in game), so they
  never hold an important item; the game still gives its own reward.

## Goals and logic
- `goal`: `story_progress` (finish chapter N of a route, short game), `ending_a`, `ending_b`, `ending_cd`, `ending_e`.
  The goal sets how much of the game has checks.
- Chapters are logic regions in story order. Weapons are progression items: later chapters expect more of
  them, so the weapons you need arrive before the harder areas. Level checks follow the level the game
  expects in each chapter.
- Checks that can be missed or that many players never find (Bunker, Pascal's Village, the Abandoned
  Factory underground, the desert Oil Field and its far edges, late-route areas, timed quests) never hold
  an important item.
- `starter_kit` (on by default): a few recovery items and one attack and one defense boost at the start,
  then a supply drop once when you enter the two hard sections you cannot come back from (the boss rush at
  the end of route A, and the start of route C/D).

## Items received
Weapons, the 16 Pod programs other than the starting laser (`pod_programs`), abilities (double jump, air
dash, ground evade, pod fire, attacks...), recovery items and boosts, money, and traps:
- **Damage Trap / Heavy Damage Trap**: `damage_trap_percent` of max HP (5-50, default 20), twice for the
  heavy one. Never kills unless `lethal_traps` is on.
- **Money Trap**: lose 10% of your money.
- **Enemy Trap**: 3 enemies appear next to you (`enemy_trap_enemies`: `basic` small machines or `random`).
- **System Failure: Light Attack / Heavy Attack / Pod Fire**: that system stops answering for 20 seconds.
- **Self-Destruct Trap**: the game's own self-destruct, short countdown then explosion, leaves you at 1 HP.
- **E-Drug Trap**: the game's E-Drug effect, picture and sound scrambled for 30 seconds.

Traps that use the game's own effects wait while a menu, a loading screen, a cutscene or a dialogue is up.

## In game
- Notifications: "From X: item", "Check: Resistance Camp" then "For X: item".
- Mail (access point Mail menu): "Archipelago checks" (remaining checks, with a count per kind) and "Hint from <player>"
  (hints other players requested on your world).
- Optional DeathLink.

## Map
The client has a **Map** tab: a top-down map of the world built from the game's own collision data. Hinted
locations are yellow, your remaining checks that have a precise location are grey, and you are the red dot.
Indoor and underground rooms (caves, factory, shopping center...) are drawn in orange over the open world.
Scroll to zoom, drag to move.

![Map tab](docs/map_tab.png)

## Known limits
- Steam v1.04 only.
- Tested in game on all three routes with automated chapter jumps and screen captures (`tools/`): story
  checks for every chapter, all 182 chests found at their expected position (interior rooms included), ground AP Items placed on their
  spots, purchases in the three shops, access points, the goals for endings A to E, and quest checks (one side quest played for real: accepted, items delivered,
  reward screen, check sent). A hack-locked chest was opened as 9S by a bot playing the hacking minigame, and its check was sent.
  Chests that only exist during or after a side quest never hold an important item. The forest shop only exists after the missable
  side quest "Camp Development", so its AP Items never hold an important item.
- The Self-Destruct and E-Drug traps were tried on foot as 2B, in a flying section and during a 9S hack (E-Drug
  shows there; Self-Destruct waits until you are back on foot, and the items received after it wait with
  it), not during boss fights. `lethal_traps` and the `random` enemy trap mode are covered by automated tests only.
- Mail titles: open an access point for ~10 s the first time after each game launch.
- Don't load another save than the one of the seed.

## Development
- Tests: `python -m pytest`
- Build: `python build.py` (apworld); launcher: `python launcher/build_exe.py`
- Reverse-engineering tools in `tools/`; game data research (routes, endings, quests, chests, positions) in
  `docs/research/`.
