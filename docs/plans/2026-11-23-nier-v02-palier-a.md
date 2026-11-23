# NieR:Automata AP v0.2 Palier A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter les checks "premier ramassage d'objet", plusieurs conditions de victoire, un outil de diff memoire (base du palier B) et la lecture/catalogue des puces.

**Architecture:** Meme decoupage que v0.1 : logique pure dans `nier_automata/game/` testee avec `FakeMemory`/`FakeGame`, monde AP dans `world.py`, outils dans `tools/`. Les puces ne sont pas encore bloquees : on construit d'abord le catalogue en jeu (aucune source publique), le blocage viendra dans un plan suivant.

**Tech Stack:** Python 3.12 stdlib, pytest, Archipelago 0.6.8.

**Spec:** `C:\Users\Administrator\ARCHIPELAGO\NierAutomataAP\docs\2026-11-23-nier-automata-v02-design.md` (Palier A + Conditions de victoire)

## Global Constraints

- Steam v1.04 uniquement ; stdlib uniquement dans l'apworld ; textes sans accents.
- Ne jamais retirer la puce OS.
- Ne jamais placer d'objet de progression sur une location potentiellement inatteignable (`LocationProgressType.EXCLUDED`).
- Commits avec `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, branche `feature/nier-v02`.

## Review Focus

- Objet deja present au moment du premier lien (ex. Broken Key id 540 recu dans le tutoriel) : ne doit pas envoyer de check, seulement les objets apparus apres.
- Objet de remplissage AP qui est aussi un materiau-check : ne doit pas valider le check a la place du ramassage reel.
- Goal "story_progress" avec story_checks atteint pendant un chargement : envoye une seule fois.
- Snapshot memoire pris pendant un chargement (taille lue partielle) : le diff signale l'erreur au lieu de comparer des tailles differentes.
- Table de puces avec la puce OS : jamais listee comme retirable.

---

### Task 1: Checks "premier ramassage d'objet"

**Files:**
- Modify: `nier_automata/data/items_data.py`, `nier_automata/data/tables.py`, `nier_automata/game/state.py`, `nier_automata/game/trackers.py`, `nier_automata/game/loop.py`, `nier_automata/world.py`, `nier_automata/options.py`, `nier_automata/game/game.py`
- Test: `tests/test_trackers.py`, `tests/test_loop.py`, `tests/test_data.py`

**Interfaces:**
- Produces:
  - `items_data.MATERIALS: dict[str, int]` : section MATERIALS du tableur nierhook (Items.csv). `FILLER_ITEMS` ne garde que soins/cures (aucun materiau) -> un materiau n'est jamais donne par AP.
  - `tables.item_location(name: str) -> str` = `f"Item: {name}"`, codes `BASE_CODE + 0x3000 + index` ; inclus dans `location_name_to_id()`.
  - `ClientState.item_baseline: set[int] | None = None`, `ClientState.items_found: set[int]` (JSON).
  - `class ItemTracker: __init__(state, enabled_ids: set[int])`, `scan(owned_item_ids: set[int]) -> list[int]` (IDs nouvellement trouves). Premier appel avec `item_baseline is None` : enregistre la baseline, renvoie `[]`.
  - `game.owned_items() -> set[int]` dans `NierGame` et `FakeGame`.
  - `due_locations(state, story_checks, weapon_checks, item_ids: dict[int, int])` ajoute `item_location` des `items_found` (dict id jeu -> code location).
  - Option `item_checks: Toggle` (defaut on) ; locations `Item: X` creees pour tous les `MATERIALS`, toutes `EXCLUDED`. slot_data `item_checks`.
- [ ] **Step 1: Tests qui echouent** : `test_item_baseline_not_checked` (premier scan `{540}` -> `[]`), `test_new_material_checked_once` (`{540}` puis `{540, 601}` -> `[601]`, puis `[]`), `test_disabled_item_ignored` (id hors `enabled_ids`), `test_filler_never_material` (`not set(FILLER_ITEMS.values()) & set(MATERIALS.values())`), `test_item_location_codes_unique`, `test_tick_sends_item_location` (FakeGame partie liee, ajout id 601 -> location `Item: Iron Ore` dans `r.locations`).
- [ ] **Step 2: `python -m pytest -q` -> FAIL.**
- [ ] **Step 3: Implementer** ; `tick` appelle `ItemTracker.scan(game.owned_items())` apres les armes.
- [ ] **Step 4: `python -m pytest -q` -> PASS ; generation 3 joueurs (`ArchipelagoGenerate.exe --skip_output`) -> `Done.`**
- [ ] **Step 5: Commit** `feat: checks de premier ramassage d'objet`.

### Task 2: Conditions de victoire

**Files:**
- Modify: `nier_automata/options.py`, `nier_automata/world.py`, `nier_automata/game/loop.py`, `nier_automata/client.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Produces:
  - `options.Goal(Choice)` : `option_story_progress = 0` (defaut), `option_ending_a = 1`. slot_data `goal: int`.
  - `loop.goal_reached(state, phase: str, goal: int, story_checks: int, goal_prefix: str) -> bool` : story_progress -> `len(state.story_codes) >= story_checks` ; ending_a -> `phase.startswith(goal_prefix)`.
  - `tick(..., goal: int = 1)` utilise `goal_reached` ; `TickResult.goal` inchange.
  - World : location evenement nommee `"Goal: Story Progress"` ou `"Story: Ending A"` selon l'option.
- [ ] **Step 1: Tests qui echouent** : `test_goal_story_progress_reached_at_count` (story_codes de taille 5, story_checks 5 -> True ; taille 4 -> False), `test_goal_ending_a_needs_phase`.
- [ ] **Step 2: FAIL -> implementer -> PASS.**
- [ ] **Step 3: Generation avec `goal: story_progress` puis `goal: ending_a` -> `Done.` les deux fois.**
- [ ] **Step 4: Commit** `feat: conditions de victoire au choix`.

### Task 3: Outil de diff memoire

**Files:**
- Create: `tools/memdiff.py`, `nier_automata/game/snapshot.py`, `tests/test_snapshot.py`

**Interfaces:**
- Produces:
  - `snapshot.diff_u32(a: bytes, b: bytes, base: int) -> list[tuple[int, int, int]]` : (offset, ancien, nouveau) pour chaque u32 aligne different ; `ValueError` si tailles differentes.
  - `snapshot.filter_small(changes, max_delta: int) -> list` : garde les changements dont |nouveau-ancien| <= max_delta ou un seul bit change.
  - `tools/memdiff.py snap <nom>` : lit la zone donnees du module `[base+0xF00000, base+0x1800000)` par blocs de 64 Ko (blocs illisibles remplis de zeros, liste dans le fichier meta), ecrit `tools/snaps/<nom>.bin` ; `tools/memdiff.py diff <a> <b> [--small] [--exclude <c>]` affiche les offsets changes entre a et b mais pas entre b et c (pour retirer le bruit).
- [ ] **Step 1: Tests qui echouent** : `test_diff_detects_changed_word`, `test_diff_size_mismatch_raises`, `test_filter_small_keeps_single_bit_flag`.
- [ ] **Step 2: FAIL -> implementer -> PASS.**
- [ ] **Step 3: Verification en jeu avec ToRaNek** : `snap avant`, ToRaNek ramasse un objet, `snap apres`, `snap rien` (sans rien faire) ; `diff avant apres --exclude rien` doit contenir l'offset de la table d'objets (`0x148C834 + 12*n`).
- [ ] **Step 4: Commit** `feat: outil de diff memoire`.

### Task 4: Lecture des puces et catalogue

**Files:**
- Create: `nier_automata/game/chips.py`, `tests/test_chips.py`, `tools/chips_dump.py`
- Modify: `tools/probe.py` (affiche le nombre de puces)

**Interfaces:**
- Produces:
  - `CHIP_SLOT_SIZE = 48`, `CHIP_SLOTS = 300`, `OS_CHIP_INDEX` (a determiner au dump : la puce dont `unknown1..3 == 0`).
  - `@dataclass Chip: index: int, raw: bytes, chip_id: int, type_index: int, level: int, cost: int`, `is_os -> bool` (unknown1..3 == 0).
  - `class ChipTable: __init__(mem, start, count=CHIP_SLOTS)`, `read_all() -> list[Chip]`, `add_raw(raw: bytes) -> bool` (premier slot `id == 0xFFFFFFFF`, ecrit les 48 octets, l'id en dernier), `remove(slot_index) -> bool` (refuse si `is_os`).
  - `tools/chips_dump.py` : ajoute chaque puce lue a `nier_automata/data/chip_catalog.json` (`{chip_id: {"type": t, "level": l, "cost": c, "raw": hex}}`).
- [ ] **Step 1: Tests qui echouent** : `test_read_chip_fields` (slot fabrique : id 3007, type 6, level 0, cost 4), `test_remove_os_chip_refused`, `test_add_raw_writes_48_bytes_id_last`, `test_add_raw_full_returns_false`.
- [ ] **Step 2: FAIL -> implementer -> PASS.**
- [ ] **Step 3: Verification en jeu** : `python tools/chips_dump.py` -> liste les puces de depart (dont OS) et remplit le catalogue ; ToRaNek confirme le nombre de puces dans le menu Puces.
- [ ] **Step 4: Commit** `feat: lecture des puces et catalogue`.
