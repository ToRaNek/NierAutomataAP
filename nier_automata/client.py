"""Client Archipelago pour NieR:Automata."""
from __future__ import annotations

import asyncio
import struct
import urllib.parse

from CommonClient import CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from .data.phases import GOAL_PHASE_PREFIX, abilities_allowed
from .game import ap_items as apit
from .game import notify
from .data.tables import SHOP_PLACES_ORDER, ap_item_location as apit_loc, location_name_to_id, shop_location
from .game import shop as shopm

LOC_IDS = location_name_to_id()
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
        if cmd == "LocationInfo":
            for it in args.get("locations", []):
                get = (lambda k, it=it: it[k]) if isinstance(it, dict) else (lambda k, it=it: getattr(it, k))
                rec = get("player")
                self.ap_contents[get("location")] = (rec, self.item_names.lookup_in_slot(get("item"), rec))
                self.ap_flags[get("location")] = get("flags")
        if cmd == "PrintJSON" and args.get("type") in ("ItemSend", "ItemCheat") and self.slot is not None:
            try:
                it = args["item"]
                get = (lambda k: it[k]) if isinstance(it, dict) else (lambda k: getattr(it, k))
                sender, receiver = get("player"), args["receiving"]
                if sender == self.slot and get("location") in getattr(self, "ap_ground_ids", set()):
                    raise StopIteration  # deja affiche par le message de ramassage de l'AP Item
                name = self.item_names.lookup_in_slot(get("item"), receiver)
                loc_name = self.location_names.lookup_in_slot(get("location"), sender)
                msgs = notify.messages_for_item_send(self.slot, sender, receiver, name,
                                                     self.player_names.get(sender, "?"),
                                                     self.player_names.get(receiver, "?"), loc_name)
                logger.info("notification en file : %s", msgs)
                self.notes.extend(msgs)
            except StopIteration:
                pass
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
            self.ap_contents = {}
            self.ap_flags = {}
            self.ap_prepared = None
            self.pickup_note = None
            self.shop_checks = int(sd.get("shop_checks", 0))
            self.shop_price = int(sd.get("shop_price", 300))
            self.shop = None
            self.shop_pid = None
            self.shop_applied = None
            self.shop_described = None
            self.ap_item_count = int(sd.get("ap_item_count", 0))
            ground = [LOC_IDS[apit_loc(i + 1)] for i in range(self.ap_item_count)] if self.ap_items_on else []
            self.ap_ground_ids = set(ground)
            shops = [LOC_IDS[shop_location(p, k)] for p in SHOP_PLACES_ORDER for k in range(1, self.shop_checks + 1)]
            ids = [i for i in ground + shops if i in self.server_locations]
            if ids:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationScouts", "locations": ids, "create_as_hint": 0}]))
            self.spots = apit.SpotTracker(self.state, self.state.ap_dynamic_spots)
            self.ap_discover_at = 0.0
            self.ap_discovering = False
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
            if getattr(ctx, "ap_prepared", None) is not None:
                continue
            mem = ctx.nier.mem
            if ctx.note_pid != mem.pid:
                ctx.note_slot = await asyncio.to_thread(notify.Notifier, mem)
                ctx.note_pid = mem.pid
            if not ctx.note_slot.ok:
                logger.info("notifications impossibles : textes introuvables")
                ctx.notes.clear()
                continue
            prefix, item = ctx.notes.pop(0)
            shown = await asyncio.to_thread(ctx.note_slot.show, prefix, item)
            logger.info("notification affichee (%s) : %s%s", shown, prefix, item)
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


async def ground_step(ctx: NierContext):
    """Instantane des objets au sol toutes les 3 s (distingue un ramassage d'un coffre)."""
    import time
    mem = ctx.nier.mem
    if getattr(ctx, "ground_pid", None) != mem.pid:
        ctx.nier.ground = apit.GroundWatch(mem)
        ctx.ground_pid, ctx.ground_next, ctx.ground_busy = mem.pid, 0.0, False
    if ctx.ground_busy or time.monotonic() < ctx.ground_next:
        return
    ctx.ground_busy = True

    async def run():
        try:
            await asyncio.to_thread(ctx.nier.ground.refresh)
        except OSError:
            pass
        finally:
            ctx.ground_next = time.monotonic() + 3.0
            ctx.ground_busy = False
    asyncio.create_task(run())


async def discover_spots(ctx: NierContext, mem, phase: str):
    """Releve les objets poses par le jeu autour du joueur et en fait de nouveaux emplacements d'AP Items."""
    try:
        found = await asyncio.to_thread(apit.find_game_items, mem)
        new = apit.extend_spots(ctx.state.ap_dynamic_spots, found, phase, ctx.ap_item_count)
        if new:
            ctx.state.ap_dynamic_spots.extend(new)
            logger.info("AP Items : %d nouvel(s) emplacement(s) (%d/%d)", len(new),
                        len(ctx.state.ap_dynamic_spots), ctx.ap_item_count)
    except OSError:
        pass
    finally:
        ctx.ap_discovering = False


async def ap_items_step(ctx: NierContext):
    """Pose les AP Items de la zone, prepare leur message quand le joueur approche, detecte le ramassage.
    Les objets sont suivis eux-memes (vraie position, disparition au ramassage)."""
    if not getattr(ctx, "ap_items_on", False) or not ctx.ap_item_count:
        return
    spots = ctx.state.ap_dynamic_spots
    mem = ctx.nier.mem
    if ctx.ap_pid != mem.pid:
        ok = await asyncio.to_thread(apit.install, mem)
        ctx.ap_pid = mem.pid
        logger.info("AP Items : %s", "deviation installee" if ok else "version non supportee")
        if not ok:
            ctx.ap_items_on = False
            return
        ctx.spots.set_game_process(mem.pid)
        ctx.pickup_note = await asyncio.to_thread(notify.Notifier, mem, apit.PICKUP_CARRIER_KEY, apit.PICKUP_CARRIER)
        found = await asyncio.to_thread(apit.find_marked_objects, mem)
        ctx.ap_tracked = apit.match_objects_to_spots(found, spots, ctx.state.ap_spots_collected, 50.0)
        for i in ctx.ap_tracked.values():
            ctx.spots.mark_spawned(i)
    phase = ctx.nier.phase()
    import time
    if phase != ctx.ap_phase:
        if ctx.ap_phase is not None:
            ctx.spots.reset_session(); ctx.ap_tracked.clear()
        ctx.ap_phase = phase
        ctx.ap_discover_at = time.monotonic() + 5.0   # laisser la zone se charger
    if (len(spots) < ctx.ap_item_count and not ctx.ap_discovering and time.monotonic() >= ctx.ap_discover_at):
        ctx.ap_discovering = True
        ctx.ap_discover_at = time.monotonic() + 60.0
        asyncio.create_task(discover_spots(ctx, mem, phase))
    ent = ctx.nier.entity()
    if ent is None:
        return
    pos = struct.unpack("<3f", mem.read(ent + 0x50, 12))
    for i in ctx.spots.to_spawn(phase, pos):
        _, x, y, z = spots[i]
        obj = await asyncio.to_thread(apit.spawn_ap_item, mem, (x, y, z))
        ctx.spots.mark_spawned(i)
        if obj:
            ctx.ap_tracked[obj] = i

    def pos_of(o):
        if not apit.object_alive(mem, o):
            return None
        return struct.unpack("<3f", mem.read(o + 0x50, 12))

    # message de ramassage prepare quand le joueur est a cote d'un AP Item
    near_obj = apit.nearest_object(ctx.ap_tracked, pos_of, pos, 4.0)
    near = ctx.ap_tracked.get(near_obj) if near_obj else None
    if near != ctx.ap_prepared and ctx.pickup_note and ctx.pickup_note.ok:
        if near is None:
            ctx.pickup_note.restore()
        else:
            rec, name = ctx.ap_contents.get(LOC_IDS[apit_loc(near + 1)], (None, None))
            prefix, item = apit.pickup_text(ctx.slot, rec, name, ctx.player_names.get(rec, "?") if rec else None)
            ctx.pickup_note.prepare(prefix, item)
        ctx.ap_prepared = near

    # ramassage : objet detruit + porteur arrive dans l'inventaire
    marker = ctx.nier._items.find(apit.PICKUP_CARRIER) is not None
    gone = [o for o in ctx.ap_tracked if not apit.object_alive(mem, o)]
    for o in gone:
        i = ctx.ap_tracked.pop(o)
        if marker:
            ctx.spots.collected(i)
            logger.info("AP Item #%d ramasse !", i + 1)
        else:
            ctx.state.ap_spawned_spots.discard(i)  # decharge sans ramassage : a reposer plus tard
    if marker:
        ctx.nier._items.remove(apit.PICKUP_CARRIER)


async def shop_step(ctx: NierContext) -> list[int]:
    """AP Items en tete des magasins ; description = contenu ; achat -> check (porteur retire)."""
    if not getattr(ctx, "shop_checks", 0):
        return []
    from pathlib import Path
    mem = ctx.nier.mem
    if ctx.shop_pid != mem.pid:
        orig = Path(ctx.state_file).parent / f"shop_table_{mem.pid}.bin"
        ctx.shop = await asyncio.to_thread(shopm.ShopSession, mem, orig, ctx.shop_price)
        ctx.shop_pid, ctx.shop_applied, ctx.shop_described = mem.pid, None, None
        logger.info("Magasins : %s", "AP Items installes" if ctx.shop.ok else "table introuvable")
    if not ctx.shop.ok:
        return []
    done = set(ctx.checked_locations) | ctx.state.sent_locations
    active = {p: shopm.active_slots(p, ctx.shop_checks, done, lambda p, k: LOC_IDS[shop_location(p, k)])
              for p in SHOP_PLACES_ORDER}
    key = repr(active)
    if key != ctx.shop_applied:
        ctx.shop.apply(active)
        ctx.shop_applied = key
    place = ctx.shop.current_place()
    if place is None:
        return []
    mapping = shopm.carrier_map(active[place], shopm.CARRIER_IDS)
    texts = {}
    for k in active[place]:
        lid = LOC_IDS[shop_location(place, k)]
        rec, name = ctx.ap_contents.get(lid, (None, None))
        texts[k] = shopm.description(ctx.slot, rec, name, ctx.player_names.get(rec, "?") if rec else None,
                                     bool(ctx.ap_flags.get(lid, 0) & 1))
    sig = repr((place, sorted(texts.items())))
    if sig != ctx.shop_described:
        ctx.shop.describe(mapping, texts)
        ctx.shop_described = sig
    sent = []
    for cid, k in mapping.items():
        if ctx.nier._items.find(cid) is not None:
            ctx.nier._items.remove(cid)
            sent.append(LOC_IDS[shop_location(place, k)])
            logger.info("AP Item achete : %s", shop_location(place, k))
    return sent


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
    await ground_step(ctx)
    await ap_items_step(ctx)
    bought = await shop_step(ctx)
    extra = sorted((due_locations(ctx.state, 0, 0) | set(bought)) - ctx.state.sent_locations)
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
