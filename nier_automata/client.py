"""Client Archipelago pour NieR:Automata."""
from __future__ import annotations

import asyncio
import struct
import urllib.parse

from CommonClient import CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from .data.phases import GOAL_PHASE_PREFIX, abilities_allowed
from .data.ap_spots import AP_SPOTS
from .game import ap_items as apit
from .game import notify
from .data.items_data import FILLER_ITEMS
from .game.abilities import AbilityLock
from .game.deathlink import DeathTracker
from .game.game import NierGame, backup_saves
from .game.loop import due_locations, make_trackers, new_state, tick
from .game.state import ClientState, state_path

GAME = "NieR:Automata"


class NierContext(CommonContext):
    game = GAME
    items_handling = 0b111

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.nier = NierGame()
        self.state: ClientState | None = None
        self.trackers = None
        self.goal_prefix = GOAL_PHASE_PREFIX
        self.goal = 1
        self.deaths = DeathTracker()
        self.saved_json = ""
        self.received_names: set[str] = set()
        self.notes: list[str] = []
        self.note_slot = None
        self.note_pid = None
        self.randomized_abilities: set[str] = set()
        self.ability_lock = None
        self.death_link_on = False
        self.backed_up = False
        self.goal_sent = False
        self.last_status = ""

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        if cmd == "PrintJSON" and args.get("type") in ("ItemSend", "ItemCheat") and self.slot is not None:
            try:
                it = args["item"]
                get = (lambda k: it[k]) if isinstance(it, dict) else (lambda k: getattr(it, k))
                sender, receiver = get("player"), args["receiving"]
                name = self.item_names.lookup_in_slot(get("item"), receiver)
                msgs = notify.messages_for_item_send(self.slot, sender, receiver, name,
                                                     self.player_names.get(sender, "?"),
                                                     self.player_names.get(receiver, "?"))
                self.notes.extend(msgs)
            except Exception as e:
                logger.info("notification ignoree : %r", e)
        if cmd == "Connected":
            sd = args.get("slot_data", {})
            seed = getattr(self, "server_seed_name", None) or self.seed_name or "seed"
            path = state_path(seed, self.slot)
            self.state = ClientState.load(path) or new_state(seed, self.slot)
            self.state_file = path
            self.saved_json = ""
            self.goal_sent = False
            self.deaths = DeathTracker()
            self.trackers = make_trackers(self.state, sd.get("story_checks", 12), sd.get("weapon_checks", 8),
                                          sd.get("item_checks", False), sd.get("chest_checks", 0),
                                          sd.get("max_level_check", 0))
            self.goal_prefix = sd.get("goal_phase_prefix", GOAL_PHASE_PREFIX)
            self.goal = sd.get("goal", 1)
            self.death_link_on = bool(sd.get("death_link", False))
            self.randomized_abilities = set(sd.get("randomized_abilities", []))
            self.ap_items_on = bool(sd.get("ap_items", False))
            self.spots = apit.SpotTracker(self.state, AP_SPOTS)
            self.ap_tracked = {}
            self.ap_pid = None
            self.ap_phase = None
            self.ability_lock = None
            if self.death_link_on:
                asyncio.create_task(self.update_death_link(True))
            logger.info("Connecte. Etat local : %s", path)
            # Renvoyer les checks merites que le serveur n'a pas (coupure pendant un envoi).
            missing = due_locations(self.state, self.trackers.story.max_count,
                                    self.trackers.weapons.max_found,
                                    self.trackers.chests.max_count,
                                    self.trackers.max_level_check) - set(args.get("checked_locations", []))
            if missing:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationChecks", "locations": sorted(missing)}]))

    def release_abilities(self):
        lock = getattr(self, "ability_lock", None)
        if lock is not None:
            try:
                lock.unlock_all()
            except Exception:
                pass
        self.ability_lock = None

    async def connection_closed(self):
        self.release_abilities()
        await super().connection_closed()
        self.state = None
        self.trackers = None

    def on_deathlink(self, data: dict):
        super().on_deathlink(data)
        try:
            if self.nier.in_game() and self.nier.kill():
                self.deaths.expect_death()
                logger.info("DeathLink recu de %s : 2B meurt.", data.get("source", "?"))
            else:
                logger.info("DeathLink recu de %s ignore : pas en jeu.", data.get("source", "?"))
        except Exception as e:
            logger.warning("DeathLink recu mais impossible d'agir (%s)", e)

    def run_gui(self):
        from kvui import GameManager

        class NierManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago NieR:Automata Client"

        self.ui = NierManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    def _status(self, msg: str):
        if msg != self.last_status:
            logger.info(msg)
            self.last_status = msg


async def game_loop(ctx: NierContext):
    while not ctx.exit_event.is_set():
        await asyncio.sleep(0.5)
        try:
            await game_iteration(ctx)
        except Exception as e:  # la boucle ne doit jamais mourir
            logger.warning("Erreur pendant le tour de jeu (%s), nouvel essai...", e)


async def notify_loop(ctx: NierContext):
    """Affiche les notifications une par une (message "Objet recupere" du porteur)."""
    while not ctx.exit_event.is_set():
        await asyncio.sleep(2.5)
        try:
            if not ctx.notes or ctx.state is None or not ctx.nier.in_game():
                continue
            mem = ctx.nier.mem
            if ctx.note_pid != mem.pid:
                ctx.note_slot = await asyncio.to_thread(notify.Notifier, mem)
                ctx.note_pid = mem.pid
            if not ctx.note_slot.ok:
                ctx.notes.clear()
                continue
            prefix, item = ctx.notes.pop(0)
            await asyncio.to_thread(ctx.note_slot.show, prefix, item)
            await asyncio.sleep(1.5)
            ctx.note_slot.restore()
            ctx.nier._items.remove(notify.CARRIER_ITEM)
        except Exception as e:
            logger.info("notification echouee : %r", e)


async def ability_loop(ctx: NierContext):
    """Boucle rapide (15 ms) : les capacites conditionnelles (esquive au sol) suivent l'etat de 2B."""
    while not ctx.exit_event.is_set():
        await asyncio.sleep(0.015)
        try:
            if not ctx.randomized_abilities or ctx.state is None or ctx.nier.mem is None:
                continue
            if ctx.ability_lock is None or ctx.ability_lock.mem is not ctx.nier.mem:
                ctx.ability_lock = AbilityLock(ctx.nier.mem, ctx.randomized_abilities)
            ctx.ability_lock.sync(ctx.received_names, ctx.nier.grounded(),
                                  allowed=abilities_allowed(ctx.nier.phase()))
        except Exception:
            pass


async def ap_items_step(ctx: NierContext):
    """Pose les AP Items de la zone et detecte leur ramassage."""
    if not getattr(ctx, "ap_items_on", False) or not AP_SPOTS:
        return
    mem = ctx.nier.mem
    if ctx.ap_pid != mem.pid:
        ok = await asyncio.to_thread(apit.install, mem)
        ctx.ap_pid = mem.pid
        ctx.spots.reset_session(); ctx.ap_tracked.clear()
        logger.info("AP Items : %s", "deviation installee" if ok else "version non supportee")
        if not ok:
            ctx.ap_items_on = False
            return
    phase = ctx.nier.phase()
    if phase != ctx.ap_phase:
        ctx.spots.reset_session(); ctx.ap_tracked.clear(); ctx.ap_phase = phase
    ent = ctx.nier.entity()
    if ent is None:
        return
    pos = struct.unpack("<3f", mem.read(ent + 0x50, 12))
    for i in ctx.spots.to_spawn(phase, pos):
        _, x, y, z = AP_SPOTS[i]
        work = await asyncio.to_thread(apit.spawn_ap_item, mem, (x, y, z))
        ctx.spots.mark_spawned(i)
        if work:
            ctx.ap_tracked[work] = i
    marker = ctx.nier._items.find(apit.AP_MARKER_ITEM) is not None
    def obj_of(w):
        return struct.unpack("<Q", mem.read(w + 0x60, 8))[0]
    for i in apit.resolve_pickups(ctx.ap_tracked, obj_of, marker):
        ctx.spots.collected(i)
        logger.info("AP Item #%d ramasse !", i + 1)
    ctx.ap_tracked = {w: i for w, i in ctx.ap_tracked.items() if i not in ctx.state.ap_spots_collected}
    if marker:
        ctx.nier._items.remove(apit.AP_MARKER_ITEM)


async def game_iteration(ctx: NierContext):
    if ctx.state is None or ctx.trackers is None:
        return
    if not ctx.nier.in_game():
        ctx.deaths.reset()
        ctx._status(ctx.nier.error or "En attente d'une partie chargee...")
        return
    if not ctx.backed_up:
        dst = backup_saves()
        if dst:
            logger.info("Sauvegardes copiees dans %s", dst)
        ctx.backed_up = True
    received = [ctx.item_names.lookup_in_game(i.item) for i in ctx.items_received]
    result = tick(ctx.nier, ctx.state, received, ctx.trackers, ctx.goal_prefix, ctx.goal)
    if result.refused:
        ctx._status("Sauvegarde deja avancee : commence une NOUVELLE partie pour cette seed.")
        return
    ctx._status(f"Jeu detecte ({ctx.nier.version}), phase {ctx.nier.phase()}")
    await ap_items_step(ctx)
    extra = sorted(due_locations(ctx.state, 0, 0) - ctx.state.sent_locations)
    if extra:
        ctx.state.sent_locations.update(extra)
        result.locations = sorted(set(result.locations) | set(extra))
    if result.locations:
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": result.locations}])
    if result.goal and not ctx.goal_sent:
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
        ctx.goal_sent = True
        logger.info("Objectif atteint : victoire envoyee !")
    current = ctx.state.to_json()
    if current != ctx.saved_json:  # compare au dernier etat ECRIT : une erreur ne bloque pas la sauvegarde
        ctx.state.save(ctx.state_file)
        ctx.saved_json = current
    ctx.received_names = set(received)
    if ctx.death_link_on and ctx.deaths.update(ctx.nier.hp(), ctx.nier.entity()):
        await ctx.send_death(f"{ctx.player_names.get(ctx.slot, '2B')} est mort(e) dans NieR:Automata")


def launch(*launch_args):
    async def main(args):
        ctx = NierContext(args.connect, args.password)
        ctx.username = getattr(args, "username", None)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_loop(ctx), name="NierGameLoop")
        abilities = asyncio.create_task(ability_loop(ctx), name="NierAbilityLoop")
        notes = asyncio.create_task(notify_loop(ctx), name="NierNotifyLoop")
        await ctx.exit_event.wait()
        ctx.server_address = None
        watcher.cancel()
        abilities.cancel()
        notes.cancel()
        ctx.release_abilities()
        await ctx.shutdown()

    import colorama

    parser = get_base_parser(description="NieR:Automata Client")
    parser.add_argument("url", nargs="?", help="Archipelago connection URL")
    args, _ = parser.parse_known_args(launch_args if launch_args else None)
    if args.url:
        url = urllib.parse.urlparse(args.url)
        args.connect = f"{url.hostname}:{url.port}" if url.port else url.hostname
        if url.username:
            args.username = urllib.parse.unquote(url.username)
        if url.password:
            args.password = urllib.parse.unquote(url.password)
    colorama.init()
    asyncio.run(main(args))
    colorama.deinit()
