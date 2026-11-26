"""Onglet "Chapters" du client : la liste des chapitres de la partie, ce qu'il faut pour ouvrir chacun, ce qu'on
y valide (check d'histoire, fins gag et comment les obtenir), et un bouton pour rejouer un chapitre deja atteint.

`entries` (sans Kivy) calcule les lignes ; `build_chapters_tab` les affiche."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..data import chapterguide as cg
from ..data import chapterlocks as cl

ROUTE_TITLES = {"A": "Route A (2B)", "B": "Route B (9S)", "C": "Route C / D"}


@dataclass
class Entry:
    kind: str                       # "title", "chapter", "ending", "note"
    text: str
    target: Optional[tuple] = None  # (route, personnage, phase, sous-phase) si le bouton "Go" est propose
    enabled: bool = False
    label: str = ""                 # nom court pour le journal


def _guide(ctx):
    st, scope = getattr(ctx, "state", None), getattr(ctx, "scope", None)
    if st is None or scope is None:
        return None
    try:
        received = [ctx.item_names.lookup_in_game(i.item) for i in ctx.items_received]
    except Exception:
        received = []
    missing = None
    try:
        if getattr(ctx, "missing_locations", None) is not None and getattr(ctx, "server_locations", None):
            missing = {ctx.location_names.lookup_in_game(i) for i in ctx.missing_locations}
    except Exception:
        missing = None
    lock = getattr(ctx, "area_lock", None)
    passes = tuple(getattr(lock, "passes", ()) or ())
    gag = tuple(getattr(scope, "gag_endings", ()) or ())
    rows = cg.rows(chapters=scope.chapters, reached=set(st.chapters), received=received,
                   route_keys=getattr(scope, "route_keys", {}) or {},
                   chapter_keys=getattr(scope, "chapter_keys", {}) or {}, missing=missing, gag_endings=gag,
                   endings_seen=set(st.endings_seen), passes=passes)
    return rows, cg.anywhere(gag, set(st.endings_seen))


def entries(ctx) -> list:
    """Lignes de l'onglet. Une seule note si la partie n'est pas connectee."""
    g = _guide(ctx)
    if g is None:
        return [Entry("note", "Connect to a room to see the chapters of your game.")]
    rows, anywhere = g
    out = [Entry("note", "A chapter you have already reached can be replayed with Go, as long as it is not "
                         "locked. Replaying never sends a check you have not earned.")]
    route = None
    for r in rows:
        if r.route != route:
            route = r.route
            done = sum(1 for x in rows if x.route == route and x.reached)
            total = sum(1 for x in rows if x.route == route)
            out.append(Entry("title", f"{ROUTE_TITLES.get(route, route)}   {done}/{total} chapters reached"))
        if r.can_go:
            state = "reached"
        elif r.reached:
            state = "reached, locked" if r.needs else "reached (no replay point)"
        else:
            state = "not reached"
        check = {True: "check sent", False: "check: reach this chapter", None: ""}[r.check_done]
        text = f"{r.code}  {r.title}   [{state}]"
        if check:
            text += f"   {check}"
        if r.needs:
            text += "   needs: " + ", ".join(r.needs)
        out.append(Entry("chapter", text, cl.STARTS.get(r.index) if r.can_go else None, r.can_go,
                         f"{r.route} {r.code} {r.title}"))
        for e in r.endings:
            ok = r.can_go and e.start is not None and not e.done
            out.append(Entry("ending", f"Ending {e.letter}  [{'done' if e.done else 'to do'}]   {e.how}",
                             e.start if ok else None, ok, f"Ending {e.letter} ({r.route} {r.code})"))
    if anywhere:
        out.append(Entry("title", "Joke endings you can get anywhere"))
        for e in anywhere:
            out.append(Entry("ending", f"Ending {e.letter}  [{'done' if e.done else 'to do'}]   {e.how}"))
    return out


def request(ctx, entry: Entry) -> bool:
    """Demande un saut : la boucle de jeu le lance quand le jeu est pret. False si la ligne n'est pas ouverte."""
    if not entry.enabled or entry.target is None:
        return False
    ctx.chapter_request = (entry.label, tuple(entry.target))
    return True


def build_chapters_tab(ctx):
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    root = BoxLayout(orientation="vertical")
    status = Label(text="", size_hint_y=None, height=30, halign="left", valign="middle", font_size="13sp")
    status.bind(size=lambda w, s: setattr(w, "text_size", s))
    scroll = ScrollView(do_scroll_x=False, bar_width=10, scroll_type=["bars", "content"])
    grid = GridLayout(cols=1, size_hint_y=None, spacing=2, padding=(6, 4))
    grid.bind(minimum_height=grid.setter("height"))
    scroll.add_widget(grid)
    root.add_widget(status)
    root.add_widget(scroll)
    state = {"sig": None}

    def go(entry):
        def on_press(_button):
            if request(ctx, entry):
                status.text = f"  Going to {entry.label} as soon as the game is ready (close any menu)..."
        return on_press

    def refresh(_dt):
        if status.text and getattr(ctx, "chapter_request", None) is None:
            status.text = ""                      # saut fait (ou annule) : le message n'a plus lieu d'etre
        try:
            items = entries(ctx)
        except Exception as e:                    # l'onglet ne doit jamais faire tomber le client
            items = [Entry("note", f"Chapters unavailable: {e!r}")]
        sig = tuple((e.kind, e.text, e.enabled) for e in items)
        if sig == state["sig"]:
            return
        state["sig"] = sig
        grid.clear_widgets()
        for e in items:
            line = BoxLayout(orientation="horizontal", size_hint_y=None, height=38 if e.kind == "title" else 30,
                             spacing=6)
            indent = {"ending": 40, "chapter": 8}.get(e.kind, 0)
            if indent:
                line.add_widget(Label(text="", size_hint_x=None, width=indent))
            lab = Label(text=e.text, halign="left", valign="middle", shorten=True, shorten_from="right",
                        bold=e.kind == "title", font_size="15sp" if e.kind == "title" else "13sp",
                        color=(1, 0.85, 0.3, 1) if e.kind == "title" else
                        (0.75, 0.85, 1, 1) if e.kind == "ending" else (1, 1, 1, 1))
            lab.bind(size=lambda w, s: setattr(w, "text_size", s))
            line.add_widget(lab)
            if e.kind in ("chapter", "ending") and e.target is not None:
                b = Button(text="Go", size_hint_x=None, width=70, disabled=not e.enabled)
                b.bind(on_press=go(e))
                line.add_widget(b)
            grid.add_widget(line)

    Clock.schedule_interval(refresh, 1.0)
    return root
