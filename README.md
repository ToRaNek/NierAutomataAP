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

**The mod (`dinput8.dll`, optional on Windows)**: a small file placed next to `NieRAutomata.exe`. The launcher
copies it there by itself (it looks for the game in your Steam libraries; `--game="folder"` to tell it where,
`--no-mod` to skip it). By hand: copy `dinput8.dll` from the Releases into the game folder. It does two things:
- it draws a striped sign with the name of the missing Pass across the entrance of every locked area, and stops
  you there (see *Area locks*);
- it lets the client talk to the game through a local connection instead of opening the game's process from
  outside, which is what is needed on Linux / Proton.

Without the mod everything else works as before on Windows: a locked area just puts you back where you were.
If another mod already uses `dinput8.dll` in your game folder, the launcher leaves it alone and says so.
The connection only listens on your own machine and asks for a key the mod writes in your user profile at each
game start. To remove the mod, delete `dinput8.dll` from the game folder.

**Linux / Proton (not tested by the author)**: put `dinput8.dll` in the game folder and set the Steam launch
options to `WINEDLLOVERRIDES="dinput8=n,b" %command%`. Then run the Archipelago client natively. The client
looks for the mod's key in the game's Proton prefix under the usual Steam folders; if your library is elsewhere,
set `NIER_AP_MOD_TOKEN_FILE` to `.../compatdata/524220/pfx/drive_c/users/steamuser/AppData/Local/NierAutomataAP/mod_token`.

Requirements: NieR:Automata **Steam v1.04** (the current Steam version: the November 2026 update, Steam
build 26534214, so just let Steam update the game), Archipelago **0.6.8+**. Whoever generates the game also needs the
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
- **Fish: <name>** (`fish_checks`, off by default): the first catch of each of the 41 fish species. Never holds
  an important item.
- **Ending F ... Ending Z** (`gag_ending_checks`, off by default): each joke ending of the routes you play, the
  first time you get it. Never holds an important item. A joke ending only writes its own flag in your save;
  your progress is untouched (checked byte by byte on ending W).
- **Chapters tab** (in the client): every chapter of your game, whether you have reached it, what is missing to
  open it (route item, chapter keys, area Pass), whether its check is sent, and the joke endings you can get
  there with how to get them. **Go** takes you back to a chapter you have already reached and that is not
  locked, like the game's own Chapter Select. It never sends a check you have not earned.
- **Quest: <name>**: finishing a side quest. Most quests close after chapter 7 (checked in game), so they
  never hold an important item; the game still gives its own reward.

## Numbers
All counts are for the **default settings**, one column per `goal`. They come from `python tools/count_checks.py`
(same computation as the generator) and were compared with a real generated game: 484 checks counted for
`ending_e`, 485 locations in the spoiler, the extra one being the goal itself.
The `story_progress` column is its default: route A up to chapter 4 (`story_route`, `story_chapter`).

### How many checks
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Story chapters | 15 | 37 | 74 | 109 | 109 |
| Chests | 54 | 136 | 175 | 182 | 182 |
| AP Items | 32 | 63 | 63 | 75 | 75 |
| Access points | 9 | 17 | 17 | 17 | 17 |
| Side quests | 8 | 39 | 50 | 60 | 60 |
| Main endings | 0 | 0 | 1 | 2 | 4 |
| Levels | 9 | 19 | 19 | 19 | 19 |
| Shop slots | 2 | 6 | 6 | 6 | 6 |
| Weapons found | 8 | 8 | 8 | 8 | 8 |
| Pod programs found | 4 | 4 | 4 | 4 | 4 |
| **Total** | **141** | **329** | **417** | **482** | **484** |
| of which never hold an important item | 31 | 110 | 128 | 162 | 162 |

- **Never hold an important item**: checks you can miss or may never find (see *Goals and logic*). They only
  receive recovery items, boosts, money or traps, so a seed never depends on them.
- **Levels**: one check per level from 2 to `max_level_check` (20 by default); a short goal stops earlier.
- **Shop slots**: `shop_checks` (2 by default) per shop that exists in the chapters you play.
- **Weapons found**, **Pod programs found**: `weapon_checks` (8) and `pod_program_checks` (4).
- **AP Items**: `ap_items_per_area` (3 by default, up to 8) per area.

Optional checks, off by default, all of them "never important":
- `fish_checks`: +41 (one per fish species).
- `gag_ending_checks`: +21 with `ending_e` (the joke endings F to Z of the routes you play).
- `item_checks`: +71 (first pickup of each material).

With everything on and `ending_e`: **617 checks**.

### How many progression locks
A lock is an item you must receive before the game lets you go on.
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Area Passes | 2 | 4 | 4 | 4 | 4 |
| Route items (Route B Access, Route C/D Access) | 0 | 0 | 1 | 2 | 2 |
| Chapter keys (B Chapter Key, C/D Chapter Key) | 0 | 0 | 9 | 15 | 15 |
| Tower keys (Forest, Ocean, Park Access Key) | 0 | 0 | 0 | 3 | 3 |
| **Total** | **2** | **4** | **14** | **24** | **24** |

- **Area Passes**: one per locked area you play before your goal. `area_locks: all` adds Flooded City and
  Abandoned Factory: 26 locks with `ending_e`. `area_locks: off`: none.
- **Route items** (`route_locks`): one to enter route B, one to enter route C/D.
- **Chapter keys** (`chapter_locks`): one more key for each big chapter after the first of its route, 9 on
  route B and 6 on route C/D. Route A has none: its areas are closed by the Passes.
- **Tower keys** (`tower_keys`): the three Access Keys the Tower door asks for.
- Each of the four options can be turned off on its own.

### How many items
There is exactly one item per check.
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Weapons | 37 | 37 | 37 | 37 | 37 |
| Abilities | 3 | 3 | 3 | 3 | 3 |
| Progression locks (table above) | 2 | 4 | 14 | 24 | 24 |
| Pod programs | 16 | 16 | 16 | 16 | 16 |
| Recovery items, boosts, money and traps | 83 | 269 | 347 | 402 | 404 |
| **Total (one per check)** | **141** | **329** | **417** | **482** | **484** |

- **Weapons**: the 37 weapons you do not start with. They are progression items: later chapters expect more of
  them.
- **Abilities**: the ones listed in `randomized_abilities` (Double Jump, Air Dash and Ground Evade by default).
  You cannot use them until they arrive.
- **Pod programs**: the 16 programs other than the starting laser (`pod_programs`).
- **The rest**: recovery items, boosts and money, with `trap_percentage` (20 by default) of them replaced by
  traps. So about one item in five of that last row is a trap.

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
- `area_locks` (`up_to_forest` by default, `all`, `off`): areas are closed until you receive their **Pass**:
  Desert Zone, Amusement Park, Pascal's Village and Forest Zone (with the castle); with `all`, also Flooded City
  and Abandoned Factory (these two come after chapter 7, when side quests are closed, so waiting there leaves
  little to do). Walking in without
  the Pass puts you back a few meters, like an invisible wall, with "Locked: Desert Pass" in the game log
  (with the mod: a sign across the entrance names the Pass and stops you, see *Install*). The
  story needs these areas in order, so it waits for the Pass. Only the areas played before your goal get a Pass
  (two with the default settings: Desert and Park). The prologue is never locked. The Copied City has no Pass
  (the game places you inside, you do not walk in). With this option the route A side quests never hold an
  important item (some of them send you into a closed area).
- `route_locks` (on by default, only used when your goal goes past ending A): route B needs the **Route B
  Access** item and route C/D the **Route C/D Access** item. If you start a route without its item, the client
  takes you back to the start of chapter 7 of the route you just finished (Pascal's Village, open world, side
  quests still open) so you can keep doing checks. When the item arrives, the client takes you to the start of
  the new route by itself. Both moves are chapter jumps, like the game's own Chapter Select.
- `chapter_locks` (on by default, routes B and C/D only): each big chapter after the first one of the route
  needs one more key (**B Chapter Key**, up to 9; **C/D Chapter Key**, up to 6). Without enough keys the client
  takes you back to the start of the last part of the previous chapter; when the key arrives it takes you to the
  start of the chapter you were waiting for. Route A has no chapter keys: its areas are closed by the Passes.
  With ending E as the goal that is 24 locks by default (4 Passes, 2 route items, 15 chapter keys, 3 Tower keys),
  26 with `area_locks: all`.
- `tower_keys` (on by default, only used when your goal reaches the Tower: ending C/D or E): the three Access
  Keys of route C/D (**Forest**, **Ocean**, **Park Access Key**) come from the multiworld. The client takes back
  the ones the game gives you and hands them over when they arrive. Without the three keys the Tower door pushes
  9S away and cannot be hacked.

## Items received
Weapons, the 16 Pod programs other than the starting laser (`pod_programs`), abilities (double jump, air
dash, ground evade, pod fire, attacks...), recovery items and boosts, money, and traps:
- **Damage Trap / Heavy Damage Trap**: `damage_trap_percent` of max HP (5-50, default 20), twice for the
  heavy one. Never kills (1 HP at worst) unless `lethal_traps` is on.
- **Money Trap**: lose 10% of your money.
- **Enemy Trap**: 3 machines of a type already present in the area appear next to you, at the level of
  the area's own machines. `enemy_trap_enemies`:
  `basic` (small machines only) or `random` (small machines plus five medium types tried in game). Bosses
  and big machines are never copied. If the area has no suitable enemy, or already holds about 40 enemies
  (more made the game crash), you take damage instead.
- **System Failure: Light Attack / Heavy Attack / Pod Fire**: that system stops answering for 20 seconds.
- **Self-Destruct Trap** (`self_destruct_trap`: `rare` by default, `normal`, `off`): the game's own self-destruct, short countdown then explosion, leaves you at 1 HP.
- **E-Drug Trap**: the game's E-Drug effect, picture and sound scrambled for 30 seconds.
- **Level Up Trap**: the enemies around you gain 10 levels (damage instead if there is none).
- **Teleport Trap**: you are put back where you were 20 seconds ago (never further than 150 m; waits while you
  are flying or hacking).
- **System Failure: Evade / Double Jump**: that move stops answering for 20 seconds.

Traps that use the game's own effects wait while a menu or a loading screen is up. Every trap except the Money
Trap waits for the end of a cutscene (5 minutes at most). Short scripted camera moves that are not real
cutscenes (a fall into a new area, for example) are not detected.

## In game
- Notifications: "From X: item", "Check: Resistance Camp" then "For X: item".
- Mail (access point Mail menu): "Archipelago checks" (remaining checks, with a count per kind) and "Hint from <player>"
  (hints other players requested on your world).
- Optional DeathLink: a death received from another player is a real death in the game (death screen, respawn at your last save).

## Map
The client has a **Map** tab: a top-down map of the world built from the game's own collision data. Hinted
locations are yellow, your remaining checks that have a precise location are grey, and you are the red dot.
Indoor and underground rooms (caves, factory, shopping center...) are drawn in orange over the open world.
Scroll to zoom, drag to move.

Three buttons at the top of the tab pick the level shown: **All** (everything on one picture), **Surface** (the
open world alone, with its checks) and **Indoor / underground** (the separate maps and what is below ground:
caves, Copied City, factory underground, Tower... with their checks, the open world dimmed as a guide). Without
this, an underground check looks the same as whatever is above it on the surface.

![Map tab](docs/map_tab.png)

## Known limits
- Steam v1.04 only, which is the current Steam version (November 2026 update, build 26534214). The version
  from before that update is not supported: the client says "Unknown NieRAutomata.exe version" and does nothing.
- Tested in game on all three routes with automated chapter jumps and screen captures (`tools/`): story
  checks for every chapter, all 182 chests found at their expected position (interior rooms included), ground AP Items placed on their
  spots, purchases in the three shops, access points, the goals for endings A to E, and quest checks (one side quest played for real: accepted, items delivered,
  reward screen, check sent). A hack-locked chest was opened as 9S by a bot playing the hacking minigame, and its check was sent.
  Chests that only exist during or after a side quest never hold an important item. The forest shop only exists after the missable
  side quest "Camp Development", so its AP Items never hold an important item.
- The Self-Destruct and E-Drug traps were tried on foot as 2B, in a boss fight (both work), in a flying section
  and during a 9S hack (E-Drug shows there; Self-Destruct waits until you are back on foot, and the items
  received after it wait with it).
- Area signs (mod): with a generated game, a server and the real client, at each of the six entrances: the sign
  is drawn across the way and stops the character pushed at 10 m/s (far faster than running), and the Factory
  sign went away when its Pass arrived from the server. The character was moved by the test tools, not with a
  controller. The sign is drawn over the finished picture, so it shows through whatever stands in front of it;
  it fades beyond 60 m. A jump of more than 6 m in one frame gets past it: the client's own wall is still there
  for that. The mod serves one program at a time (the client). Linux / Proton: not tested by the author.
- Area locks: tested in game at the entrance of each of the six areas (the wall holds on repeated tries, and the
  Desert opens as soon as its Pass arrives from the server). If you connect while already standing inside a
  closed area, the client leaves you there. No full playthrough with the locks has been done yet.
- Route locks: tested in game for routes B and C/D (taken back without the item, route started when the item
  arrives from the server, first check of the route sent). The "Locked" message of a route lock has not been
  seen on screen yet. Tested by jumping to the start of each route, not by playing an ending for real.
- Every lock was tried one by one in game with the real client and a server (`tools/locktest.py`, results in
  `tools/locktest_report.json`): the six area walls (character pushed through each entrance at 25 m/s, far faster
  than running), both route locks and the 15 chapter locks (taken back without the item, check not sent while
  locked, chapter started and check sent when the item arrives). These tests jump to chapters; no ending was
  played for real.
- Tower keys: tested in game in front of the Tower with the real client and a server (no key: the door refuses;
  keys taken back when put in the inventory; keys sent by the server: 9S hacks the door and the story goes on).
  The moment the game itself hands a key was played for all three: the Forest key (end of its resource unit),
  the Ocean key (after the boss in the Flooded City unit, fight played by hand: the game shows "Ocean Access
  Key x 1" and the client takes it back within a second) and the Park key (Pod dialogue at the start of chapter
  17). The client checks ten times per second and the keys do not come back. The game also puts the keys back
  when a later chapter loads; the client takes them back as soon as the game is playable.
- New traps (Level Up, Teleport, System Failure: Evade / Double Jump): each one sent by a server to the real
  client and measured in game (levels +10, 78 m back to the position of 20 seconds before, both moves locked for
  20 seconds then released).
- Gag endings: all 21 (F to Z) were reached in game with the real client and a server: the game goes to its
  "Ending_<letter>" phase, the client sees it and the check is sent. They were reached by jumping to the right
  chapter, not by playing a whole run up to them. Four needed a human at the controls (I, N, Y, Z), and for N
  and Y the story state was set by hand first (village layout, Emil's previous quest, all weapons at level 4).
  What was not tested: reaching each one in a normal playthrough from a fresh save.
- Fish checks: the check is sent when the fish enters the inventory (tested by giving a Carp with the game's own
  give function). A real catch was not achieved by the test robot.
- Mail titles: open an access point for ~10 s the first time after each game launch.
- Don't load another save than the one of the seed.

## Development
- Tests: `python -m pytest`
- Build: `python build.py` (apworld); mod: `python mod/build_mod.py` (needs `zig`); launcher:
  `python launcher/build_exe.py` (builds and embeds both)
- Mod sources and its socket protocol: `mod/nier_ap_mod.c`, `mod/overlay.c`; client side:
  `nier_automata/game/modlink.py`
- Reverse-engineering tools in `tools/`; game data research (routes, endings, quests, chests, positions) in
  `docs/research/`.
