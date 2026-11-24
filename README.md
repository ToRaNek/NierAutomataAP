# NieR:Automata for Archipelago

Archipelago world (`.apworld`) and client for **NieR:Automata (PC Steam, v1.04)**, route A.
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
- **Story: <place>**: each named story step of route A (Resistance Camp, Pascal's Village, Simone...).
- **Weapon Found #n**: each weapon found (removed from the inventory).
- **Chest #n**, **Level n**: chests opened, levels reached.
- **AP Item: <place> #k**: "AP Item" objects dropped on the ground along your path, 1 to 3 per story step.
- **Shop <place> #k**: "AP Item" entries at the top of the shops (Resistance Camp, Pascal's Village,
  Forest Castle); the description says what's inside and for whom.
- In a multiworld, your checks only contain items for the other players.

## Items received
Weapons, abilities (double jump, air dash, ground evade, pod fire, pod programs, attacks...), recovery items,
money, traps (5/10% damage, 10% money loss, enemy spawn).

## In game
- Notifications: "From X: item", "Check: Resistance Camp" then "For X: item".
- Mail (access point Mail menu): "Archipelago checks" (remaining checks) and "Hint from <player>"
  (hints other players requested on your world).
- Optional DeathLink.

## Known limits
- Steam v1.04 only, route A.
- Mail titles: open an access point for ~10 s the first time after each game launch.
- Don't load another save than the one of the seed.

## Development
- Tests: `python -m pytest`
- Build: `python build.py` (apworld); launcher: `python launcher/build_exe.py`
- Reverse-engineering tools in `tools/`; game data research (routes, endings, quests, chests, positions) in
  `docs/research/`.
