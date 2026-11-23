"""Client Archipelago pour NieR:Automata."""
from __future__ import annotations

import asyncio
import urllib.parse

from CommonClient import CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus

from .data.phases import GOAL_PHASE_PREFIX
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
        if cmd == "Connected":
            sd = args.get("slot_data", {})
            seed = getattr(self, "server_seed_name", None) or self.seed_name or "seed"
            path = state_path(seed, self.slot)
            self.state = ClientState.load(path) or new_state(seed, self.slot)
            self.state_file = path
            self.trackers = make_trackers(self.state, sd.get("story_checks", 12), sd.get("weapon_checks", 8),
                                          sd.get("item_checks", False))
            self.goal_prefix = sd.get("goal_phase_prefix", GOAL_PHASE_PREFIX)
            self.goal = sd.get("goal", 1)
            self.death_link_on = bool(sd.get("death_link", False))
            if self.death_link_on:
                asyncio.create_task(self.update_death_link(True))
            logger.info("Connecte. Etat local : %s", path)
            # Renvoyer les checks merites que le serveur n'a pas (coupure pendant un envoi).
            missing = due_locations(self.state, self.trackers.story.max_count,
                                    self.trackers.weapons.max_found) - set(args.get("checked_locations", []))
            if missing:
                asyncio.create_task(self.send_msgs([{"cmd": "LocationChecks", "locations": sorted(missing)}]))

    async def connection_closed(self):
        await super().connection_closed()
        self.state = None
        self.trackers = None

    def on_deathlink(self, data: dict):
        super().on_deathlink(data)
        if self.nier.in_game() and self.nier.kill():
            self.deaths.expect_death()
            logger.info("DeathLink recu de %s : 2B meurt.", data.get("source", "?"))

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


async def game_iteration(ctx: NierContext):
    if ctx.state is None or ctx.trackers is None:
        return
    if not ctx.nier.in_game():
        ctx._status(ctx.nier.error or "En attente d'une partie chargee...")
        return
    if not ctx.backed_up:
        dst = backup_saves()
        if dst:
            logger.info("Sauvegardes copiees dans %s", dst)
        ctx.backed_up = True
    received = [ctx.item_names.lookup_in_game(i.item) for i in ctx.items_received]
    before = ctx.state.to_json()
    result = tick(ctx.nier, ctx.state, received, ctx.trackers, ctx.goal_prefix, ctx.goal)
    if result.refused:
        ctx._status("Sauvegarde deja avancee : commence une NOUVELLE partie pour cette seed.")
        return
    ctx._status(f"Jeu detecte ({ctx.nier.version}), phase {ctx.nier.phase()}")
    if result.locations:
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": result.locations}])
    if result.goal and not ctx.goal_sent:
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
        ctx.goal_sent = True
        logger.info("Objectif atteint : victoire envoyee !")
    if ctx.death_link_on and ctx.deaths.update(ctx.nier.hp()):
        await ctx.send_death(f"{ctx.player_names.get(ctx.slot, '2B')} est mort(e) dans NieR:Automata")
    if ctx.state.to_json() != before:
        ctx.state.save(ctx.state_file)


def launch(*launch_args):
    async def main(args):
        ctx = NierContext(args.connect, args.password)
        ctx.username = getattr(args, "username", None)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_loop(ctx), name="NierGameLoop")
        await ctx.exit_event.wait()
        ctx.server_address = None
        watcher.cancel()
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
