"""Facade haut niveau sur le processus NieRAutomata.exe."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..data.items_data import FILLER_ITEMS, FILLER_QUANTITY, FUNDS_ITEMS, POD_PROGRAMS, TRAP_ITEMS
from ..data.offsets import OFFSETS, detect_version
from ..data.phases import MENU_PHASES
from ..data.weapons import WEAPONS
import struct

from .deathlink import HP_OFFSET, MAX_HP_COPY_OFFSET, add_funds
from .traps import CutsceneHold, damage_after_trap, damage_percent, funds_after_trap, trap_kills
from .inventory import item_table, weapon_table
from .memory import ProcessMemory, read_cstr, read_u32


# Niveau du joueur dans l'entite (verifie en jeu v1.04 : niveau 4).
LEVEL_OFFSET = 0x14BC


def save_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents" / "My Games" / "NieR_Automata"


def backup_saves(src: Optional[Path] = None, dst_root: Optional[Path] = None) -> Optional[Path]:
    src = src or save_dir()
    files = list(src.glob("SlotData_*.dat")) + list(src.glob("GameData.dat"))
    if not files:
        return None
    root = dst_root or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NierAutomataAP" / "backups"
    dst = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dst / f.name)
    return dst


ACCESS_POINT_BITS_RVA = 0x14957E0
SCENE_STATES_RVA = 0xFC2718       # {pointeur, nombre} des etats de scene actifs (entrees de 0x20 o)
PHASE_ID_RVA = 0xF64B18           # descripteur {u32 phase, u32 hachage, nom} ; le nom est en +8
CHEST_VTABLE_RVA = 0xC7D708      # objet coffre (ba2014/15/16)
CHEST_OPEN_OFFSET = 0xA8C         # != 0 une fois ouvert


def decode_bits(raw: bytes) -> set[int]:
    """Bit n = dword[n >> 5] & (0x80000000 >> (n & 31))."""
    out = set()
    for w in range(len(raw) // 4):
        v = int.from_bytes(raw[w * 4:w * 4 + 4], "little")
        out.update(w * 32 + b for b in range(32) if v & (0x80000000 >> b))
    return out


class NierGame:
    def __init__(self):
        self.mem: Optional[ProcessMemory] = None
        self.version: Optional[str] = None
        self.error: Optional[str] = None
        from .traps import Jams
        self.jams = Jams()
        self.cutscene_hold = CutsceneHold()
        self.lethal_traps = False
        self.enemy_trap_basic = True
        self.damage_trap_percent = 20       # options de la partie (slot_data)

    def attach(self) -> bool:
        if self.mem is not None and self.mem.is_alive():
            return True
        if self.mem is not None:
            self.mem.close()
        self.mem, self.version = ProcessMemory.attach(), None
        if self.mem is None:
            self.error = "Game not running"
            return False
        self.version = detect_version(self.mem.exe_path)
        if self.version is None:
            self.error = "Unknown NieRAutomata.exe version: only Steam v1.04 is supported"
            self.mem.close()
            self.mem = None
            return False
        self.error = None
        o = OFFSETS[self.version]
        self._off = o
        self._items = item_table(self.mem, o["itemTableStart"])
        self._weapons = weapon_table(self.mem, o["weaponTableStart"])
        return True

    def in_game(self) -> bool:
        try:
            if not self.attach():
                return False
            phase = self.phase()
            return (phase not in MENU_PHASES and bool(phase)
                    and read_u32(self.mem, self._off["isLoading"]) == 0
                    and read_u32(self.mem, self._off["isWorldLoaded"]) != 0)
        except OSError:
            self.mem = None
            return False

    def phase(self) -> str:
        return read_cstr(self.mem, self._off["currentPhase"])

    ground = None  # GroundWatch (objets au sol), fourni par le client

    def ground_pickup(self, pos) -> bool:
        """Un objet au sol vient-il d'etre ramasse a cote de `pos` ?"""
        try:
            return bool(self.ground and self.ground.picked_near(pos))
        except OSError:
            return False

    def access_point_bits(self) -> set[int]:
        """Points d'acces actives (bit n du tableau global, voir docs/research/access_points_resolved.json)."""
        try:
            return decode_bits(self.mem.read(self.mem.base + ACCESS_POINT_BITS_RVA, 16))
        except OSError:
            return set()

    def quests_done(self) -> set[int]:
        """Quetes annexes terminees (tableau de statuts du bloc de sauvegarde)."""
        import struct
        from ..data import worlddb as db
        try:
            raw = self.mem.read(self.mem.base + db.QUEST_STATUS_RVA, 4 * db.QUEST_STATUS_COUNT)
        except OSError:
            return set()
        return db.quests_done(list(struct.unpack(f"<{db.QUEST_STATUS_COUNT}i", raw)))

    def opened_chests(self) -> list:
        """Positions des objets coffre ouverts actuellement charges (vtable et drapeau verifies en jeu)."""
        import struct
        from .spawner import entity_region
        try:
            region = entity_region(self.mem)
            if not region:
                return []
            base, size = region
            data = self.mem.read(base, size)
        except OSError:
            return []
        vt = struct.pack("<Q", self.mem.base + CHEST_VTABLE_RVA)
        out, i = [], data.find(vt)
        while i != -1:
            if i % 8 == 0 and i + CHEST_OPEN_OFFSET + 4 <= len(data)                     and struct.unpack_from("<I", data, i + CHEST_OPEN_OFFSET)[0]:
                out.append(struct.unpack_from("<3f", data, i + 0x50))
            i = data.find(vt, i + 8)
        return out

    def phase_id(self):
        """Numero de la phase (0x100 = p100, 0x200 = p200...), a cote de son nom."""
        try:
            return int.from_bytes(self.mem.read(self.mem.base + PHASE_ID_RVA, 4), "little")
        except OSError:
            return None

    def scene_states(self, wanted) -> set:
        """Etats de scene actifs parmi `wanted` (tableau trie par crc32, docs/research/runtime_state.md)."""
        import struct
        import zlib
        want = {zlib.crc32(n.encode()): n for n in wanted}
        try:
            ptr, n = struct.unpack("<QQ", self.mem.read(self.mem.base + SCENE_STATES_RVA, 16))
            if not ptr or not 0 < n < 5000:
                return set()
            table = self.mem.read(ptr, n * 0x20)
            out = set()
            for i in range(n):
                rec = struct.unpack_from("<Q", table, i * 0x20 + 0x10)[0]
                h = struct.unpack("<I", self.mem.read(rec + 0x20, 4))[0]
                if h in want:
                    out.add(want[h])
            return out
        except OSError:
            return set()

    def endings(self) -> set:
        from ..data import worlddb as db
        return self.scene_states(db.ENDING_STATES)

    def chest_counter(self) -> int:
        return read_u32(self.mem, self._off["chestCounter"])

    def position(self) -> tuple[float, float, float]:
        return struct.unpack("<3f", self.mem.read(self.mem.base + self._off["playerLocation"], 12))

    def owned_items(self) -> set[int]:
        return {s.item_id for s in self._items.read_all()}

    def owned_weapons(self) -> set[int]:
        return {s.item_id for s in self._weapons.read_all()}

    def give(self, name: str) -> bool:
        if name in WEAPONS:
            return self._weapons.add(WEAPONS[name], 1)
        if name in POD_PROGRAMS:
            from .inventory import add_pod_program
            try:
                return add_pod_program(self.mem, POD_PROGRAMS[name])
            except OSError:
                return False
        if name in TRAP_ITEMS:
            return self.apply_trap(*TRAP_ITEMS[name])
        if name in FUNDS_ITEMS:
            add_funds(self.mem, self._off["funds"], FUNDS_ITEMS[name])
            return True
        if name in FILLER_ITEMS:
            # ajout discret : la notification "De X : <objet>" du client remplace le message du jeu
            return self._items.add(FILLER_ITEMS[name], FILLER_QUANTITY.get(name, 1))
        return True  # objet inconnu : ignore plutot que bloquer la file

    SET_ACTION_RVA = 0x433C70      # setAction(joueur, action, 0, 0, 0) ; 0x38 = explosion d'autodestruction
    DEATH_ACTION = 0x35            # action de mort du joueur (suivie de 0x36 puis de l'ecran "Body Report")
    EDRUG_RVA = 0x52D160           # effet de l'objet E-Drug sur le joueur
    ACTION_OFFSET = 0x670
    WORLD_LOADED_RVA = 0xF6E3C0
    MENU_RVA = 0x11EAC2C           # 1 = aucun menu ouvert
    CUTSCENE_RVA = 0x11EAC4C       # 2 pendant une cinematique jouee dans le monde, 0 sinon (verifie en jeu)

    def in_cutscene(self) -> bool:
        try:
            return struct.unpack("<I", self.mem.read(self.mem.base + self.CUTSCENE_RVA, 4))[0] != 0
        except (OSError, AttributeError):
            return False

    def _game_effect(self, kind: str) -> bool:
        """Lance un effet du jeu par sa propre fonction. False = pas maintenant (menu, chargement...)."""
        from .spawner import remote_call
        from .traps import effect_allowed
        p = self.entity()
        if p is None:
            return False
        try:
            loaded, = struct.unpack("<I", self.mem.read(self.mem.base + self.WORLD_LOADED_RVA, 4))
            menu, = struct.unpack("<I", self.mem.read(self.mem.base + self.MENU_RVA, 4))
            action, = struct.unpack("<I", self.mem.read(p + self.ACTION_OFFSET, 4))
            hp, = struct.unpack("<I", self.mem.read(p + HP_OFFSET, 4))
            if not effect_allowed(loaded != 0, menu == 1, action, hp, kind):      # cinematique : apply_trap
                return False
            if kind == "edrug":
                remote_call(self.mem, self.mem.base + self.EDRUG_RVA, p)
                return True
            import time
            from .traps import self_destruct_clear
            reads = []
            for _ in range(4):                 # 0,45 s : couvre le passage a 0 pendant un piratage
                time.sleep(0.15)
                reads.append(struct.unpack("<I", self.mem.read(p + self.ACTION_OFFSET, 4))[0])
            if not self_destruct_clear(reads):
                return False
            remote_call(self.mem, self.mem.base + self.SET_ACTION_RVA, p, 0x38, 0, 0, e=0)
        except OSError:
            return False
        return True                        # l'explosion du jeu laisse 1 PV, comme une vraie autodestruction

    def jammed(self) -> set:
        import time
        return self.jams.active(time.monotonic())

    def owned_programs(self) -> set:
        from .inventory import read_pod_programs
        try:
            return read_pod_programs(self.mem)
        except OSError:
            return set()

    def remove_program(self, program_id: int) -> bool:
        from .inventory import remove_pod_program
        try:
            return remove_pod_program(self.mem, program_id)
        except OSError:
            return False

    def remove_weapon(self, weapon_id: int) -> bool:
        return self._weapons.remove(weapon_id)

    def entity(self) -> Optional[int]:
        try:
            p = struct.unpack("<Q", self.mem.read(self.mem.base + self._off["playerEntity"], 8))[0]
        except (OSError, AttributeError):
            return None
        return p if 0x10000 < p < 0x7FFFFFFFFFFF else None

    def hp(self) -> Optional[int]:
        p = self.entity()
        if p is None:
            return None
        try:
            return struct.unpack("<I", self.mem.read(p + HP_OFFSET, 4))[0]
        except OSError:
            return None

    def kill(self) -> bool:
        p = self.entity()
        if p is None:
            return False
        # Ecrire 0 PV ne suffit pas (le jeu remet 1 PV, verifie en jeu) : il faut aussi l'action de mort que le
        # jeu pose lui-meme quand un ennemi tue le joueur (0x35 puis 0x36, releve en jeu).
        from .spawner import remote_call
        try:
            self.mem.write(p + HP_OFFSET, struct.pack("<I", 0))
            remote_call(self.mem, self.mem.base + self.SET_ACTION_RVA, p, self.DEATH_ACTION, 0, 0, e=0)
        except OSError:
            return False
        return True

    GIVE_ITEM_RVA = 0x8006F0  # donne 1 objet ET affiche "Objet obtenu" (verifie en jeu)

    def give_with_popup(self, item_id: int) -> bool:
        """Donne 1 exemplaire via la fonction du jeu, avec son message. False si l'appel echoue."""
        from .spawner import remote_call
        try:
            return remote_call(self.mem, self.mem.base + self.GIVE_ITEM_RVA, item_id, 1, 1, 1, e=1) & 0xFF == 1
        except OSError:
            return False

    def apply_trap(self, kind: str, percent: int) -> bool:
        """False = pas applicable maintenant (pas d'entite, cinematique) : le client reessaie au tour suivant."""
        import time
        if kind != "money" and self.cutscene_hold.hold(self.in_cutscene(), time.monotonic()):
            return False
        if kind != "money" and not self.hp():          # joueur mort ou absent : on attend (vu en jeu : le piege
            return False                                # faisait encore apparaitre des ennemis sur l'ecran de mort)
        if kind.startswith("jam:"):
            self.jams.start(kind[4:], percent, time.monotonic())
            return True
        if kind in ("selfdestruct", "edrug"):
            return self._game_effect(kind)
        if kind == "spawn":
            from .spawner import spawn_enemies
            pos = struct.unpack("<3f", self.mem.read(self.mem.base + self._off["playerLocation"], 12))
            try:
                if spawn_enemies(self.mem, pos, count=percent, basic_only=self.enemy_trap_basic):
                    return True
            except OSError:
                return False
            kind, percent = "damage", 1  # aucun ennemi charge dans la zone : degats a la place
        if kind == "money":
            funds = read_u32(self.mem, self._off["funds"])
            self.mem.write(self.mem.base + self._off["funds"], struct.pack("<I", funds_after_trap(funds, percent)))
            return True
        p = self.entity()
        if p is None:
            return False
        try:
            hp, = struct.unpack("<I", self.mem.read(p + HP_OFFSET, 4))
            max_hp, = struct.unpack("<I", self.mem.read(p + MAX_HP_COPY_OFFSET, 4))
            if hp == 0 or max_hp == 0:
                return False
            pct = damage_percent(percent, self.damage_trap_percent)
            if trap_kills(hp, max_hp, pct, self.lethal_traps):
                return self.kill()
            self.mem.write(p + HP_OFFSET, struct.pack("<I", damage_after_trap(hp, max_hp, pct)))
        except OSError:
            return False
        return True

    def grounded(self) -> Optional[bool]:
        """2B au sol = compteur de sauts (+0x14A8) a 0. None si illisible."""
        p = self.entity()
        if p is None:
            return None
        try:
            return struct.unpack("<I", self.mem.read(p + 0x14A8, 4))[0] == 0
        except OSError:
            return None

    def level(self) -> Optional[int]:
        p = self.entity()
        if p is None:
            return None
        try:
            return struct.unpack("<I", self.mem.read(p + LEVEL_OFFSET, 4))[0]
        except OSError:
            return None
