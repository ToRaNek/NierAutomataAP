# NieR:Automata Archipelago Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un apworld `nier_automata.apworld` + un client Python qui detecte les checks (phases route A, armes trouvees) et injecte les objets recus dans NieR:Automata Steam v1.04.

**Architecture:** Package Python `nier_automata/` zippe en `.apworld`. La logique pure (parsing des tables memoire, trackers, etat JSON) est isolee de tout import Archipelago et testee avec une fausse memoire. Une couche `memory.py` (ctypes) parle au vrai processus. Le client herite de `CommonClient` d'Archipelago et est enregistre comme composant du launcher.

**Tech Stack:** Python 3.12 (stdlib uniquement dans l'apworld : ctypes, hashlib, json), pytest pour les tests, Archipelago 0.6.8 installe dans `C:\ProgramData\Archipelago`.

**Spec:** `C:\Users\Administrator\ARCHIPELAGO\NierAutomataAP\docs\2026-11-23-nier-automata-archipelago-design.md`

## Global Constraints

- Archipelago cible : 0.6.8 ; nom du jeu : `NieR:Automata`.
- Version du jeu : Steam v1.04 uniquement (offsets v1.03/v1.04 d'AutomataSpeedrunMod) ; refuser toute ecriture si le hash de l'exe est inconnu.
- Aucune dependance pip dans l'apworld (stdlib seulement).
- Windows uniquement ; processus `NieRAutomata.exe`.
- Sauvegarder `SlotData_*.dat` avant la premiere ecriture memoire d'une session.
- Code et fichiers sans accents ; textes affiches a l'utilisateur en francais sans accents.
- Racine du projet : `C:\Users\Administrator\ARCHIPELAGO\NierAutomataAP\` (repo git, commits avec `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).

## Review Focus

- Jeu lance mais au menu titre (phase `START`) ou en chargement : le client ne lit/ecrit rien et n'envoie aucun check.
- Inventaire plein (aucun slot `0xFFFFFFFF`) au moment de donner un objet : l'objet reste en file d'attente, pas de crash, pas d'ecrasement.
- Rechargement d'une sauvegarde plus ancienne : armes AP reinjectees si absentes, jamais de check renvoye en double, compteur d'armes non incremente par la reinjection.
- Jeu ferme / relance pendant que le client tourne : reconnexion automatique, aucune ecriture vers un ancien handle.
- Slot de sauvegarde different de celui lie a la seed : le client refuse et l'affiche.

---

## Structure des fichiers

```
NierAutomataAP/
  nier_automata/
    __init__.py          # World AP + enregistrement composant launcher
    archipelago.json     # manifeste apworld (game, version 0.1.0)
    items.py             # table d'objets (armes, consommables, materiaux, G)
    locations.py         # table de locations (phases + "Weapon Found #n")
    options.py           # options YAML
    data/
      weapons.py         # WEAPONS: dict[str, int]  nom -> ID jeu
      phases.py          # STORY_PHASES: list[tuple[str, str]]  (nom location, prefixe phase)
      offsets.py         # VERSIONS, OFFSETS
    game/
      memory.py          # ProcessMemory (ctypes) + FakeMemory (tests)
      inventory.py       # parse/ecrit les tables de slots
      game.py            # NierGame : facade haut niveau
      trackers.py        # WeaponTracker, PhaseTracker
      state.py           # ClientState (JSON)
    client.py            # NierContext(CommonContext) + boucle
  tools/
    probe.py             # sonde : version, phase, inventaire, log
  tests/                 # pytest, logique pure uniquement
  build.py               # zippe nier_automata/ -> dist/nier_automata.apworld
```

---

### Task 1: Couche memoire + detection de version

**Files:**
- Create: `nier_automata/game/memory.py`, `nier_automata/data/offsets.py`, `nier_automata/__init__.py` (vide pour l'instant), `tests/test_memory.py`, `.gitignore`, `pytest.ini` (`pythonpath = .`)

**Interfaces:**
- Produces:
  - `class Memory(Protocol)`: `read(addr: int, size: int) -> bytes`, `write(addr: int, data: bytes) -> None`, `base: int`
  - `read_u32(mem: Memory, offset: int) -> int`, `write_u32(mem, offset, value) -> None`, `read_cstr(mem, offset, maxlen=64) -> str` (offset relatif a `mem.base`)
  - `class FakeMemory(Memory)`: `__init__(size: int = 0x2000000, base: int = 0x140000000)`, bytearray interne
  - `class ProcessMemory(Memory)`: `attach(exe_name="NieRAutomata.exe") -> ProcessMemory | None` (classmethod), `exe_path: str`, `is_alive() -> bool`, `close()`
  - `offsets.py`: `VERSIONS: dict[str, str]` (sha256 hex -> "v1.04"...), `OFFSETS: dict[str, dict[str, int]]`, `detect_version(exe_path: str) -> str | None`

- [ ] **Step 1: git init du dossier, `.gitignore` (`__pycache__/`, `dist/`, `*.log`), `pytest.ini`.**
- [ ] **Step 2: Tests qui echouent** dans `tests/test_memory.py` :
  - `test_u32_roundtrip` : `write_u32(m, 0x100, 0xDEADBEEF)` puis `read_u32(m, 0x100) == 0xDEADBEEF`, et `m.read(m.base+0x100, 4) == b"\xef\xbe\xad\xde"`.
  - `test_read_cstr_stops_at_nul` : octets `b"58_AB_BossArea_Fall\x00zz"` a 0x200 -> `"58_AB_BossArea_Fall"`.
  - `test_detect_version_unknown` : fichier temporaire quelconque -> `None`.
  - `test_offsets_v104_values` : `OFFSETS["v1.04"]["currentPhase"] == 0xF64B20`, `["itemTableStart"] == 0x148C834`, `["chipTableStart"] == 0x148E780`, `["isLoading"] == 0x13ECEB8`, `["isWorldLoaded"] == 0xF6E3C0`, `["weaponTableStart"] == 0x148E034`.
- [ ] **Step 3: `pytest tests/test_memory.py -v` -> FAIL (module absent).**
- [ ] **Step 4: Implementer.** `ProcessMemory` via `kernel32.OpenProcess(PROCESS_VM_READ|PROCESS_VM_WRITE|PROCESS_VM_OPERATION|PROCESS_QUERY_INFORMATION)`, base = module principal via `CreateToolhelp32Snapshot(TH32CS_SNAPMODULE)`, chemin exe via `QueryFullProcessImageNameW`. `OFFSETS["v1.04"]` = valeurs v1.03 du speedrun mod (meme binaire), `weaponTableStart = 0x148E034` (hypothese +0x370 vs v1.02 `0x148DCC4`, commentee). `VERSIONS` : copier les hashes v1.03/v1.04 de `src/infra/HashCheck.cpp` d'AutomataSpeedrunMod, les deux mappes vers `"v1.04"`.
- [ ] **Step 5: `pytest -v` -> PASS.**
- [ ] **Step 6: Commit** `feat: couche memoire et detection de version`.

### Task 2: Sonde (validation sur le vrai jeu)

**Files:**
- Create: `tools/probe.py`

**Interfaces:**
- Consumes: `ProcessMemory.attach`, `detect_version`, `OFFSETS`, `read_cstr`, `read_u32` (Task 1).
- Produces: `tools/phases_seen.log` (une ligne `horodatage<TAB>phase` a chaque changement) ; sortie console utilisee pour valider les offsets.

- [ ] **Step 1: Ecrire `probe.py`** : attache le processus, affiche version detectee (ou hash brut si inconnu), puis toutes les 500 ms : phase courante, `isLoading`, `isWorldLoaded`, et les 20 premiers slots non vides de la table d'objets et d'armes (format slot : `id u32, statut u32, quantite u32`, stride 12, vide = `0xFFFFFFFF`). Option `--dump-weapons-around` : dumpe `0x148DC00..0x148E400` pour localiser la table d'armes si l'hypothese est fausse.
- [ ] **Step 2: Verification manuelle avec ToRaNek (jeu lance, partie chargee)** : `python tools/probe.py`. Attendu : version `v1.04`, phase = chaine lisible (pas `START` en jeu), au moins une arme connue (Type-40 Sword `0x41A`) visible dans la table d'armes. Si le hash est inconnu : ajouter le hash affiche a `VERSIONS` apres avoir confirme les offsets.
- [ ] **Step 3: Si la table d'armes n'est pas a `0x148E034`** : localiser via le dump (chercher `1A 04 00 00`), corriger `OFFSETS["v1.04"]["weaponTableStart"]` et le test de Task 1.
- [ ] **Step 4: Commit** `feat: sonde de validation des offsets`.

### Task 3: Inventaire (lecture/ecriture des slots)

**Files:**
- Create: `nier_automata/game/inventory.py`, `tests/test_inventory.py`

**Interfaces:**
- Consumes: `Memory`, `read_u32`, `write_u32`, `FakeMemory` (Task 1).
- Produces:
  - `EMPTY = 0xFFFFFFFF`, `SLOT_SIZE = 12`
  - `@dataclass Slot: index: int, item_id: int, status: int, quantity: int`
  - `class SlotTable: __init__(mem: Memory, start: int, count: int)`, `read_all() -> list[Slot]` (non vides), `find(item_id) -> Slot | None`, `add(item_id: int, quantity: int, status: int) -> bool` (False si plein ; si l'objet existe deja et `stackable`, ajoute a la quantite, plafond 99), `remove(item_id) -> bool`
  - Constantes : `ITEM_SLOTS = (0x148CE18 - 0x148C4C4) // 12 + 1` (bornes nierhook v1.02, meme taille en v1.04), `WEAPON_SLOTS = (0x148DFBC - 0x148DCC4) // WEAPON_SLOT_SIZE + 1` avec `WEAPON_SLOT_SIZE` lu dans `addWeapon` de nierhook puis confirme en Task 2, `ACTIVE_STATUS = 0x00070000`.

- [ ] **Step 1: Tests qui echouent** :
  - `test_add_to_empty_table` : table vide -> `add(1, 5, ACTIVE_STATUS)` True, `find(1).quantity == 5`.
  - `test_add_stacks_existing` : objet 1 qty 5 -> `add(1, 3)` -> qty 8 dans le meme slot.
  - `test_add_caps_at_99`.
  - `test_add_when_full_returns_false_and_writes_nothing` (Review Focus : inventaire plein) : toutes les cases remplies -> False, octets inchanges.
  - `test_remove_clears_slot_to_empty`.
  - `test_read_all_skips_empty`.
- [ ] **Step 2: `pytest tests/test_inventory.py -v` -> FAIL.**
- [ ] **Step 3: Implementer `SlotTable`** (les armes utilisent la meme classe avec leur propre stride si different : parametre `slot_size`).
- [ ] **Step 4: `pytest -v` -> PASS.**
- [ ] **Step 5: Verification manuelle** : script ponctuel `python -c` avec `ProcessMemory` -> `SlotTable(items).add(0, 1, ACTIVE_STATUS)` (Small Recovery) ; ToRaNek confirme en jeu (menu inventaire) que l'objet est apparu. Idem `remove` sur une arme de test. Sauvegarde copiee avant.
- [ ] **Step 6: Commit** `feat: lecture/ecriture inventaire`.

### Task 4: Etat client + trackers

**Files:**
- Create: `nier_automata/game/state.py`, `nier_automata/game/trackers.py`, `tests/test_state.py`, `tests/test_trackers.py`

**Interfaces:**
- Produces:
  - `@dataclass ClientState: seed: str, slot: int, save_slot: int | None, next_item_index: int = 0, sent_locations: set[int], weapons_found: int = 0, ap_weapons: set[int]` (IDs jeu des armes recues via AP) ; `load(path) -> ClientState | None`, `save(path)` (ecriture atomique via fichier temporaire + `os.replace`) ; `state_path(seed, slot) -> Path` dans `%LOCALAPPDATA%\NierAutomataAP\`.
  - `class WeaponTracker: __init__(state: ClientState, max_found: int)`, `scan(owned_weapon_ids: set[int]) -> tuple[list[int], int | None]` -> (IDs a retirer, nouvel index "Weapon Found #n" ou None). Une arme detenue et absente de `state.ap_weapons` = trouvee naturellement : retirer, incrementer `weapons_found` (sans depasser `max_found`), renvoyer le numero.
  - `class PhaseTracker: __init__(phases: list[tuple[str, str]])`, `check(phase: str) -> list[str]` -> noms de locations dont le prefixe correspond (`phase.startswith(prefixe)`), une seule fois chacun ; `is_goal(phase) -> bool`.
- [ ] **Step 1: Tests qui echouent** :
  - `test_state_roundtrip` (sets conserves), `test_state_save_is_atomic` (pas de fichier partiel si exception pendant l'ecriture simulee).
  - `test_natural_weapon_counted_and_removed` : owned `{0x41A}`, ap vide -> retire `[0x41A]`, n=1.
  - `test_ap_weapon_not_counted` : owned `{0x41A}`, `ap_weapons={0x41A}` -> `([], None)`.
  - `test_reinjected_weapon_after_reload_not_counted` (Review Focus : rechargement).
  - `test_counter_capped_at_max_found` : au-dela de max -> arme quand meme retiree, n=None.
  - `test_phase_check_once` : meme phase deux fois -> la 2e renvoie `[]`.
  - `test_menu_phase_ignored` : `check("START") == []` (Review Focus : menu titre).
- [ ] **Step 2: `pytest -v` -> FAIL.**
- [ ] **Step 3: Implementer.**
- [ ] **Step 4: `pytest -v` -> PASS.**
- [ ] **Step 5: Commit** `feat: etat client et trackers`.

### Task 5: Donnees + apworld

**Files:**
- Create: `nier_automata/data/weapons.py`, `nier_automata/data/phases.py`, `nier_automata/items.py`, `nier_automata/locations.py`, `nier_automata/options.py`, `nier_automata/archipelago.json`, `build.py`, `tests/test_data.py`
- Modify: `nier_automata/__init__.py`

**Interfaces:**
- Consumes: `tools/phases_seen.log` (Task 2) pour choisir les prefixes de phases.
- Produces:
  - `WEAPONS: dict[str, int]` : armes obtenables en route A (source : tableur nierhook, export CSV `.../export?format=csv`), IDs verifies sur 1 ou 2 armes via la sonde.
  - `STORY_PHASES: list[tuple[str, str]]` : au minimum les boss route A connus (Engels, Adam & Eve, Pascal's village..., Fin A) ; derniere entree = goal, nom `"Story: Ending A"`.
  - `ITEM_TABLE: dict[str, ItemData(code: int, game_id: int, kind: Literal["weapon","item","funds"], classification)]`, base code `0x4E41_0000`.
  - `LOCATION_TABLE: dict[str, int]` : `"Story: <nom>"` + `"Weapon Found #1".."#N"` avec `N = round(0.8 * len(WEAPONS))`.
  - Options : `weapon_found_percentage: Range(50..100, defaut 80)`, `funds_filler_amount: Range(500..20000, defaut 3000)`.
  - World : un seul region "Menu", toutes locations accessibles, completion = `has("Victory")` via evenement locke sur `"Story: Ending A"`. Pool = une de chaque arme + filler (consommables/materiaux/`"<n> G"`) jusqu'au nombre de locations.
  - `build.py` : zippe `nier_automata/` en `dist/nier_automata.apworld` (dossier racine `nier_automata/` dans le zip, sans `__pycache__`).
- [ ] **Step 1: Tests qui echouent** (`tests/test_data.py`, sans importer AP) : codes uniques, noms uniques, `len(locations) >= len(armes)` impossible a violer (pool ne depasse pas les locations), derniere phase = goal.
- [ ] **Step 2: `pytest -v` -> FAIL.**
- [ ] **Step 3: Remplir les donnees et le World** (imports AP uniquement dans `__init__.py`).
- [ ] **Step 4: `pytest -v` -> PASS.**
- [ ] **Step 5: Generation reelle** : `python build.py`, copier dans `C:\ProgramData\Archipelago\custom_worlds\`, YAML de test `name: TestNier / game: NieR:Automata` + `ToRaNek.yaml` (Minecraft) dans un dossier temporaire, `ArchipelagoGenerate.exe --player_files_path <tmp> --skip_output`. Attendu : `Done.` sans exception, ligne `NieR:Automata : v0.1.0`.
- [ ] **Step 6: Commit** `feat: apworld NieR:Automata`.

### Task 6: Client

**Files:**
- Create: `nier_automata/client.py`, `nier_automata/game/game.py`
- Modify: `nier_automata/__init__.py` (composant launcher `"NieR:Automata Client"`, `Type.CLIENT`, `launch_subprocess`)

**Interfaces:**
- Consumes: Tasks 1, 3, 4, 5.
- Produces:
  - `class NierGame: attach() -> bool`, `in_game() -> bool` (version ok, phase != `START`, `isLoading == 0`, `isWorldLoaded != 0`), `phase() -> str`, `owned_weapons() -> set[int]`, `give(item: ItemData, qty) -> bool`, `remove_weapon(game_id) -> bool`, `backup_saves() -> Path` (copie `Documents\My Games\NieR_Automata\SlotData_*.dat` dans `%LOCALAPPDATA%\NierAutomataAP\backups\<horodatage>\`).
  - `NierContext(CommonContext)` : `game = "NieR:Automata"`, `items_handling = 0b111`, boucle `game_loop()` toutes les 500 ms :
    1. pas attache / process mort -> retente `attach()` (Review Focus : jeu relance).
    2. `in_game()` faux -> ne rien faire.
    3. premiere fois par session -> `backup_saves()` ; si `state.save_slot` defini et different du slot charge -> message `"Mauvaise sauvegarde : charge le slot X"` et pause (Review Focus).
    4. appliquer `items_received[state.next_item_index:]` via `give` ; si `give` echoue (plein) -> arreter et reessayer au tour suivant ; armes ajoutees a `state.ap_weapons`.
    5. reinjecter les `ap_weapons` absentes.
    6. `WeaponTracker.scan` + `PhaseTracker.check` -> `LocationChecks` pour les nouvelles ; goal -> `StatusUpdate CLIENT_GOAL`.
    7. `state.save()` apres chaque changement.
- [ ] **Step 1: Tests de la boucle avec `FakeMemory`** (`tests/test_loop.py`) en injectant une fausse `NierGame` : `test_items_applied_once`, `test_full_inventory_retries`, `test_no_action_in_menu`, `test_goal_sent_on_ending_phase`. La logique d'un tour est extraite dans `tick(game, state, received, trackers) -> TickResult(locations: list[int], goal: bool)` sans dependance AP.
- [ ] **Step 2: FAIL -> implementer `tick` + `NierGame` -> PASS.**
- [ ] **Step 3: Brancher `tick` dans `NierContext`.**
- [ ] **Step 4: Test bout en bout manuel** : generer une seed solo NieR, `ArchipelagoServer.exe` en local, lancer le client depuis le launcher, se connecter. Attendu : un objet `/send TestNier Small Recovery` apparait en jeu ; ramasser une arme -> elle disparait et `Weapon Found #1` est coche cote serveur ; relancer le jeu -> le client se rattache.
- [ ] **Step 5: Commit** `feat: client NieR:Automata`.

### Task 7: Livraison

**Files:**
- Create: `README.md` (installation pour le pote : apworld dans `custom_worlds`, lancer le client, nouvelle partie obligatoire, version Steam 1.04)
- Create: `dist/NieR Automata.yaml` (modele genere via `Generate Template Options`)

- [ ] **Step 1: `python build.py`, regenerer le modele YAML, copier les deux dans `dist/`.**
- [ ] **Step 2: Generation test avec tous les YAML du groupe (ToRaNek Minecraft, Niicotine LoL, TestNier) -> `Done.`**
- [ ] **Step 3: Commit** `docs: README et modele YAML`.
