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
- **Quest: <name>**: side quests (experimental, off by default).

## Goals and logic
- `goal`: `story_progress` (reach N chapters, short game), `ending_a`, `ending_b`, `ending_cd`, `ending_e`.
  The goal sets how much of the game has checks.
- Chapters are logic regions in story order. Weapons are progression items: later chapters expect more of
  them, so the weapons you need arrive before the harder areas. Level checks follow the level the game
  expects in each chapter.
- Checks that can be missed (Bunker, Pascal's Village, late-route areas, timed quests) never hold an
  important item.

## Items received
Weapons, abilities (double jump, air dash, ground evade, pod fire, pod programs, attacks...), recovery items,
money, traps (5/10% damage, 10% money loss, enemy spawn).

## In game
- Notifications: "From X: item", "Check: Resistance Camp" then "For X: item".
- Mail (access point Mail menu): "Archipelago checks" (remaining checks) and "Hint from <player>"
  (hints other players requested on your world).
- Optional DeathLink.

## Known limits
- Steam v1.04 only.
- Tested in game on all three routes with automated chapter jumps (`tools/campaign.py`): story checks for
  every chapter, 129 of 187 chests found at their expected position, ground AP Items placed on their spots.
  Chests that could not be confirmed (mostly inside separately loaded interiors) never hold an important
  item. Not tested in game yet: the shops of Pascal's Village and the Forest Castle, quest checks, endings.
- Mail titles: open an access point for ~10 s the first time after each game launch.
- Don't load another save than the one of the seed.

## Development
- Tests: `python -m pytest`
- Build: `python build.py` (apworld); launcher: `python launcher/build_exe.py`
- Reverse-engineering tools in `tools/`; game data research (routes, endings, quests, chests, positions) in
  `docs/research/`.
