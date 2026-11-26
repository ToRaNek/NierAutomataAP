"""Onglet "Chapters" du client, sur le modele de l'onglet Maps du client Portal 2 : a gauche les grands chapitres
avec leur compteur, au milieu les sous-chapitres et les fins gag du chapitre choisi, a droite la fiche de la ligne
choisie (objets requis, ce qu'il faut faire pour valider, bouton pour y aller).

`menu` (sans Kivy) calcule le contenu ; `build_chapters_tab` l'affiche. Trois petites listes au lieu d'une longue :
la premiere version affichait ~150 lignes d'un coup et faisait ramer le client."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..data import chapterguide as cg
from ..data import chapterlocks as cl

ROUTE_TITLES = {"A": "Route A", "B": "Route B", "C": "Route C/D"}
ANYWHERE = "Anywhere"


@dataclass
class Item:
    title: str                      # ligne de la colonne du milieu
    kind: str                       # "chapter" ou "ending"
    done: int                       # checks faits / a faire de cette ligne
    total: int
    required: list = field(default_factory=list)    # objets qui manquent
    validate: list = field(default_factory=list)    # ce qu'il faut faire pour valider
    target: Optional[tuple] = None  # (route, personnage, phase, sous-phase) du saut
    playable: bool = False
    why: str = ""                   # pourquoi le bouton est grise
    label: str = ""                 # nom pour le journal


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


def menu(ctx) -> dict:
    """{grand chapitre: [Item]} dans l'ordre de l'histoire ; {} si la partie n'est pas connectee."""
    g = _guide(ctx)
    if g is None:
        return {}
    rows, anywhere = g
    out: dict[str, list] = {}
    for r in rows:
        group = f"{ROUTE_TITLES.get(r.route, r.route)} - Chapter {r.code.split('-')[0]}"
        items = out.setdefault(group, [])
        if r.can_go:
            why = ""
        elif r.needs:
            why = "Locked"
        elif not r.reached:
            why = "Not reached yet"
        else:
            why = "No replay point"
        items.append(Item(
            title=f"{r.code} {r.title}", kind="chapter", done=1 if r.check_done else 0, total=1,
            required=list(r.needs),
            validate=["Check sent." if r.check_done else "Reach this chapter in the story to send its check."],
            target=cl.STARTS.get(r.index) if r.can_go else None, playable=r.can_go, why=why,
            label=f"{r.route} {r.code} {r.title}"))
        for e in r.endings:
            ok = r.can_go and e.start is not None
            items.append(Item(
                title=f"Ending {e.letter}", kind="ending", done=1 if e.done else 0, total=1,
                required=list(r.needs), validate=[e.how] + (["Already done."] if e.done else []),
                target=e.start if ok else None, playable=ok, why="" if ok else why or "No replay point",
                label=f"Ending {e.letter} ({r.route} {r.code})"))
    if anywhere:
        out[ANYWHERE] = [Item(title=f"Ending {e.letter}", kind="ending", done=1 if e.done else 0, total=1,
                              validate=[e.how] + (["Already done."] if e.done else []),
                              why="Can be done in any chapter", label=f"Ending {e.letter}") for e in anywhere]
    return out


def count(items) -> str:
    return f"{sum(i.done for i in items)}/{sum(i.total for i in items)}"


def request(ctx, item: Item) -> bool:
    """Demande un saut : la boucle de jeu le lance quand le jeu est pret. False si la ligne n'est pas ouverte."""
    if not item.playable or item.target is None:
        return False
    ctx.chapter_request = (item.label, tuple(item.target))
    return True


def build_chapters_tab(ctx):
    from kivy.clock import Clock
    from kivy.metrics import dp
    from kivy.uix.behaviors import ButtonBehavior
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.button import MDButton, MDButtonText
    from kivymd.uix.gridlayout import MDGridLayout
    from kivymd.uix.label import MDLabel
    from kvui import ScrollBox

    class Selectable(ButtonBehavior, MDBoxLayout):
        def __init__(self, name, count_text, on_release, width):
            super().__init__(orientation="horizontal", padding=[dp(12), dp(8)], spacing=dp(8), size_hint_y=None,
                             height=dp(40), width=dp(width), size_hint_x=None, md_bg_color=[1, 1, 1, 0.12],
                             radius=dp(6))
            self.name = name
            self.add_widget(MDLabel(text=name, halign="left", shorten=True, shorten_from="right"))
            self.count_label = MDLabel(text=count_text, halign="right", width=dp(44), size_hint_x=None)
            self.add_widget(self.count_label)
            self.bind(on_release=on_release)

        def mark(self, on):
            self.md_bg_color = [1, 1, 1, 0.3 if on else 0.12]

    def column(width):
        box = ScrollBox()
        box.layout.orientation = "vertical"
        box.layout.spacing = dp(3)
        box.scroll_type = ["bars"]
        box.do_scroll_x = False
        box.size_hint_x = None
        box.width = dp(width)
        return box

    root = MDGridLayout(rows=1, cols=3, padding=[dp(20), dp(10)], spacing=dp(10))
    left, middle = column(240), column(290)
    info = MDBoxLayout(orientation="vertical", padding=[dp(12), dp(8)], spacing=dp(8),
                       md_bg_color=[1, 1, 1, 0.12], radius=dp(6))
    root.add_widget(left)
    root.add_widget(middle)
    root.add_widget(info)
    ui = {"data": {}, "sig": None, "group": None, "item": None, "gbtn": {}, "ibtn": {}, "note": ""}

    def text(s, **kw):
        lab = MDLabel(text=s, **kw)
        lab.bind(width=lambda w, x: setattr(w, "text_size", (x, None)))
        return lab

    def show_info():
        info.clear_widgets()
        items = ui["data"].get(ui["group"], [])
        it = next((i for i in items if i.title == ui["item"]), None)
        if it is None:
            hint = "Pick a chapter on the left." if ui["data"] else "Connect to a room to see your chapters."
            info.add_widget(text(hint, halign="center"))
            return
        info.add_widget(text(it.title, halign="center", size_hint_y=None, height=dp(40), bold=True))
        info.add_widget(text("Required items:\n" + (", ".join(it.required) if it.required
                                                    else "All required items acquired")))
        info.add_widget(text("To validate:\n" + "\n".join(it.validate)))
        if ui["note"]:
            info.add_widget(text(ui["note"]))
        label = ("Play chapter" if it.kind == "chapter" else "Go there") if it.playable else it.why
        b = MDButton(MDButtonText(text=label), disabled=not it.playable)

        def go(_b, it=it):
            if request(ctx, it):
                ui["note"] = f"Going to {it.label} as soon as the game is ready (close any menu)."
                show_info()
        b.bind(on_release=go)
        info.add_widget(b)

    def pick_item(title):
        ui["item"], ui["note"] = title, ""
        for name, b in ui["ibtn"].items():
            b.mark(name == title)
        show_info()

    def show_items():
        middle.layout.clear_widgets()
        ui["ibtn"] = {}
        for it in ui["data"].get(ui["group"], []):
            b = Selectable(it.title, f"{it.done}/{it.total}", lambda _b, t=it.title: pick_item(t), 280)
            b.mark(it.title == ui["item"])
            ui["ibtn"][it.title] = b
            middle.layout.add_widget(b)

    def pick_group(name):
        ui["group"], ui["item"], ui["note"] = name, None, ""
        for g, b in ui["gbtn"].items():
            b.mark(g == name)
        show_items()
        show_info()

    def refresh(_dt):
        try:
            data = menu(ctx)
        except Exception:                         # l'onglet ne doit jamais faire tomber le client
            data = {}
        if ui["note"] and getattr(ctx, "chapter_request", None) is None:
            ui["note"] = ""
        sig = tuple((g, tuple((i.title, i.done, i.playable, tuple(i.required)) for i in items))
                    for g, items in data.items())
        if sig == ui["sig"]:
            return
        groups_changed = list(data) != list(ui["data"])
        ui["data"], ui["sig"] = data, sig
        if groups_changed:
            left.layout.clear_widgets()
            ui["gbtn"] = {}
            for g, items in data.items():
                b = Selectable(g, count(items), lambda _b, n=g: pick_group(n), 230)
                ui["gbtn"][g] = b
                left.layout.add_widget(b)
            if ui["group"] not in data:
                ui["group"], ui["item"] = None, None
        for g, b in ui["gbtn"].items():
            b.count_label.text = count(data[g])
            b.mark(g == ui["group"])
        show_items()
        show_info()

    show_info()
    Clock.schedule_interval(refresh, 1.0)
    return root
