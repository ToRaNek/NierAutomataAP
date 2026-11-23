"""Client Archipelago pour NieR:Automata."""
from __future__ import annotations

import asyncio
import math
import struct
import urllib.parse

from CommonClient import CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from .data.phases import GOAL_PHASE_PREFIX, abilities_allowed, ap_phase_indices
from .game import ap_items as apit
from .game import notify
from .data.tables import SHOP_PLACES_ORDER, ap_item_location as apit_loc, location_name_to_id, shop_location, spot_location
from .game import shop as shopm
from .game import mail as mailm

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
        if cmd == "PrintJSON" and args.get("type") == "Hint" and self.slot is not None and self.state is not None:
            try:
                it = args["item"]
                get = (lambda k: it[k]) if isinstance(it, dict) else (lambda k: getattr(it, k))
                receiver = args["receiving"]
                if get("player") == self.slot and receiver != self.slot and not args.get("found"):
                    hint = (self.item_names.lookup_in_slot(get("item"), receiver),
                            self.player_names.get(receiver, "?"),
                            self.location_names.lookup_in_slot(get("location"), self.slot))
                    if hint not in self.state.hints:
                        self.state.hints.append(hint)
                        self.mail_hint_new = True
                        self.mail_hint_unread = True
                        logger.info("Indice pour %s : %s -> %s", hint[1], hint[0], hint[2])
            except Exception as e:
                logger.info("indice ignore : %r", e)
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
            self.mailer = None
            self.mail_pid = None
            self.mail_checks_sig = None
            self.mail_hint_new = bool(self.state.hints)
            self.mail_hint_unread = False
            self.mail_busy = False
            self.shop_checks = int(sd.get("shop_checks", 0))
            self.shop_price = int(sd.get("shop_price", 300))
            self.shop = None
            self.shop_pid = None
            self.shop_applied = None
            self.shop_pay = shopm.PaymentWatch()
            self.ap_per_phase = int(sd.get("ap_items_per_phase", 0))
            self.ap_phase_count = int(sd.get("ap_phase_count", 0))
            ground = [LOC_IDS[apit_loc(i, k)] for i in ap_phase_indices(self.ap_phase_count)
                      for k in range(1, self.ap_per_phase + 1)] if self.ap_items_on else []
            self.ap_ground_ids = set(ground)
            shops = [LOC_IDS[shop_location(p, k)] for p in SHOP_PLACES_ORDER for k in range(1, self.shop_checks + 1)]
            ids = [i for i in ground + shops if i in self.server_locations]
            if ids:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationScouts", "locations": ids, "create_as_hint": 0}]))
            self.spots = apit.SpotTracker(self.state, self.state.ap_dynamic_spots)
            self.ap_discover_at = 0.0
            self.ap_phase_since = 0.0
            self.ap_path = {}   # phase -> positions au sol du joueur (trajet reel)
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
            mailer = getattr(ctx, "mailer", None)
            if mailer is not None and mailer.mem is ctx.nier.mem:
                mailer.check_titles()   # titres des mails : reecrits des que le terminal recharge son fichier
        except Exception:
            pass
        try:
            if not ctx.randomized_abilities or ctx.state is None or ctx.nier.mem is None:
                continue
            if ctx.ability_lock is None or ctx.ability_lock.mem is not ctx.nier.mem:
                ctx.ability_lock = AbilityLock(ctx.nier.mem, ctx.randomized_abilities)
            ctx.ability_lock.sync(ctx.received_names, ctx.nier.grounded(),
                                  allowed=abilities_allowed(ctx.nier.phase()))
        except Exception:
            pass


async def mail_step(ctx: NierContext):
    """Mails Archipelago : liste des checks restants (n 31) et indices demandes par les autres (n 32)."""
    if ctx.mail_busy:
        return
    mem = ctx.nier.mem
    ctx.mail_busy = True
    try:
        if ctx.mail_pid != mem.pid:
            ctx.mailer = mailm.Mailer(mem)
            await asyncio.to_thread(ctx.mailer.ensure_mail, mailm.CHECKS_MAIL, "Archipelago")
            ctx.mailer.set_title(mailm.CHECKS_MAIL, "Checks Archipelago")
            ctx.mail_pid, ctx.mail_checks_sig = mem.pid, None
            ctx.mail_hint_new = bool(ctx.state.hints)
        mailer = ctx.mailer
        remaining = sorted(ctx.location_names.lookup_in_slot(i, ctx.slot) for i in ctx.missing_locations)
        if repr(remaining) != ctx.mail_checks_sig:
            total = len(ctx.missing_locations) + len(ctx.checked_locations)
            if await asyncio.to_thread(mailer.set_body, mailm.CHECKS_MAIL, mailm.checks_body(remaining, total)):
                await asyncio.to_thread(mailer.send, mailm.CHECKS_MAIL)
                ctx.mail_checks_sig = repr(remaining)
        if ctx.mail_hint_new and ctx.state.hints:
            who = ctx.state.hints[-1][1]
            await asyncio.to_thread(mailer.ensure_mail, mailm.HINTS_MAIL, who)
            mailer.set_sender(mailm.HINTS_MAIL, who)
            mailer.set_title(mailm.HINTS_MAIL, f"Indice de {who}")
            if await asyncio.to_thread(mailer.set_body, mailm.HINTS_MAIL, mailm.hints_body(ctx.state.hints)):
                await asyncio.to_thread(mailer.send, mailm.HINTS_MAIL)
                if ctx.mail_hint_unread:
                    mailer.mark_unread(mailm.HINTS_MAIL)
                ctx.mail_hint_new = ctx.mail_hint_unread = False
                logger.info("Messagerie : indice de %s ajoute", who)
        await asyncio.to_thread(mailer.locate_titles)
    except (OSError, StopIteration) as e:
        logger.info("Messagerie indisponible : %r", e)
    finally:
        ctx.mail_busy = False


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
    import time
    try:
        found = await asyncio.to_thread(apit.find_game_items, mem)
        spots = ctx.state.ap_dynamic_spots
        new = apit.extend_spots(spots, found, phase, ctx.ap_per_phase, ctx.ap_phase_count,
                                path=ctx.ap_path.get(phase, []))
        if new:
            spots.extend(new)
            logger.info("AP Items : %s", ", ".join(spot_location(spots, len(spots) - len(new) + j)
                                                   for j in range(len(new))))
    except OSError:
        pass
    finally:
        ctx.ap_discovering = False


async def ap_items_step(ctx: NierContext):
    """Pose les AP Items de la zone, prepare leur message quand le joueur approche, detecte le ramassage.
    Les objets sont suivis eux-memes (vraie position, disparition au ramassage)."""
    if not getattr(ctx, "ap_items_on", False) or not ctx.ap_per_phase:
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
            # un changement d'etape ne decharge pas forcement la zone : on garde les objets encore au sol
            ctx.ap_tracked = {o: i for o, i in ctx.ap_tracked.items() if apit.object_alive(mem, o)}
            ctx.spots.reset_session()
            for i in ctx.ap_tracked.values():
                ctx.spots.mark_spawned(i)
            # fin de l'etape precedente : places restantes sur son trajet (chaque check reste faisable)
            filled = apit.fill_from_path(spots, ctx.ap_phase, ctx.ap_path.get(ctx.ap_phase, []),
                                         ctx.ap_per_phase, ctx.ap_phase_count)
            if filled:
                spots.extend(filled)
                logger.info("AP Items : %s", ", ".join(spot_location(spots, len(spots) - len(filled) + j)
                                                       for j in range(len(filled))))
        ctx.ap_phase = phase
        ctx.ap_discover_at = time.monotonic() + 5.0   # laisser la zone se charger
        ctx.ap_phase_since = time.monotonic()
    if (not ctx.ap_discovering and time.monotonic() >= ctx.ap_discover_at
            and apit.fallback_spot(spots, phase, (0.0, 0.0, 0.0), ctx.ap_per_phase, ctx.ap_phase_count)):
        ctx.ap_discovering = True
        ctx.ap_discover_at = time.monotonic() + 60.0
        asyncio.create_task(discover_spots(ctx, mem, phase))
    ent = ctx.nier.entity()
    if ent is None:
        return
    pos = struct.unpack("<3f", mem.read(ent + 0x50, 12))
    if ctx.nier.grounded():
        walk = ctx.ap_path.setdefault(phase, [])
        if not walk or math.dist(walk[-1], pos) >= 5.0:
            walk.append(pos)
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
            rec, name = ctx.ap_contents.get(LOC_IDS[spot_location(spots, near)], (None, None))
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
    """AP Items en tete des magasins ; un porteur par emplacement ; achat -> check (porteur retire)."""
    if not getattr(ctx, "shop_checks", 0):
        return []
    from pathlib import Path
    mem = ctx.nier.mem
    slots = [(p, k) for p in SHOP_PLACES_ORDER for k in range(1, ctx.shop_checks + 1)]
    if ctx.shop_pid != mem.pid:
        orig = Path(ctx.state_file).parent / f"shop_table_{mem.pid}.bin"
        owned = {c for c in shopm.CARRIER_POOL if ctx.nier._items.find(c) is not None}
        ctx.shop = await asyncio.to_thread(shopm.ShopSession, mem, orig, ctx.shop_price, slots, owned)
        ctx.shop_pid, ctx.shop_applied = mem.pid, None
        logger.info("Magasins : %s", f"AP Items installes ({len(ctx.shop.carriers)} emplacements)"
                    if ctx.shop.ok else "table introuvable")
    if not ctx.shop.ok:
        return []
    done = set(ctx.checked_locations) | ctx.state.sent_locations
    active = {p: shopm.active_slots(p, ctx.shop_checks, done, lambda p, k: LOC_IDS[shop_location(p, k)])
              for p in SHOP_PLACES_ORDER}
    key = repr(active)
    if key != ctx.shop_applied:
        ctx.shop.apply(active)
        ctx.shop_applied = key
    texts = {}
    for place, k in slots:
        lid = LOC_IDS[shop_location(place, k)]
        rec, name = ctx.ap_contents.get(lid, (None, None))
        texts[(place, k)] = shopm.description(ctx.slot, rec, name, ctx.player_names.get(rec, "?") if rec else None,
                                              bool(ctx.ap_flags.get(lid, 0) & 1))
    await asyncio.to_thread(ctx.shop.describe, texts)
    import time
    now = time.monotonic()
    ctx.shop_pay.update(struct.unpack("<I", mem.read(mem.base + 0x148C830, 4))[0], now)
    sent = []
    for cid, (place, k) in ctx.shop.carriers.items():
        if ctx.nier._items.find(cid) is None:
            continue
        lid = LOC_IDS[shop_location(place, k)]
        if lid in done:
            ctx.nier._items.remove(cid)   # deja valide : on nettoie
        elif ctx.shop_price <= 0 or ctx.shop_pay.consume(ctx.shop_price, now):
            ctx.nier._items.remove(cid)
            sent.append(lid)
            logger.info("AP Item achete : %s", shop_location(place, k))
        # sinon : porteur apparu SANS paiement (chargement...) -> pas de check, on attend
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
    if not ctx.mail_busy:
        asyncio.create_task(mail_step(ctx))
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
