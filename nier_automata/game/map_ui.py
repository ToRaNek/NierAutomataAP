"""Onglet "Map" du client : carte vue de dessus, indices en jaune, checks restants en gris, joueur en rouge.
Molette ou pincement = zoom, glisser = deplacer."""
from __future__ import annotations

import os
from pathlib import Path

from . import worldmap as wm


LAYER_LABELS = {"all": "All", "surface": "Surface", "indoor": "Indoor / underground"}


def _map_file(layer: str = "all") -> str:
    """La carte est dans l'apworld (zip) : Kivy a besoin d'un vrai fichier."""
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NierAutomataAP"
    d.mkdir(parents=True, exist_ok=True)
    f = d / wm.MAP_FILES[layer]
    data = wm.map_png(layer)
    if not f.exists() or f.read_bytes() != data:      # contenu, pas taille : la carte change entre versions
        f.write_bytes(data)
    return str(f)


def build_map_tab(ctx):
    from kivy.clock import Clock
    from kivy.graphics import Color, Ellipse, Point
    from kivy.graphics.transformation import Matrix
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.image import Image
    from kivy.uix.label import Label
    from kivy.uix.scatter import Scatter
    from kivy.uix.stencilview import StencilView
    from kivy.uix.togglebutton import ToggleButton

    info = wm.load_info()

    class MapScatter(Scatter):
        def on_touch_down(self, touch):
            if touch.is_mouse_scrolling and self.parent.collide_point(*touch.pos):
                factor = 1.15 if touch.button == "scrolldown" else 1 / 1.15
                state["touched"] = True
                if 0.3 <= self.scale * factor <= 12:
                    self.apply_transform(Matrix().scale(factor, factor, factor), anchor=touch.pos)
                return True
            if not self.parent.collide_point(*touch.pos):
                return False          # hors de la vue : la carte (plus grande que sa vue) ne prend pas le clic
            state["touched"] = True
            return super().on_touch_down(touch)

    class MapView(StencilView):
        pass

    root = BoxLayout(orientation="vertical")
    legend = Label(text="", size_hint_y=None, height=44, halign="left", valign="middle", font_size="13sp")
    legend.bind(size=lambda w, s: setattr(w, "text_size", s))
    view = MapView()
    scatter = MapScatter(do_rotation=False, size_hint=(None, None), size=(info.width, info.height),
                         scale_min=0.3, scale_max=12)
    image = Image(source=_map_file(), size=(info.width, info.height), size_hint=(None, None),
                  allow_stretch=True, keep_ratio=False)
    scatter.add_widget(image)
    view.add_widget(scatter)
    state = {"touched": False, "layer": "all"}
    files = {layer: _map_file(layer) for layer in wm.MAP_FILES}

    def pick(layer):
        def on_press(button):
            button.state = "down"                 # un niveau reste toujours choisi
            if state["layer"] != layer:
                state["layer"] = layer
                image.source = files[layer]
                state["sig"] = None               # redessine les points pour ce niveau
        return on_press

    # niveaux : en surface et sous terre au meme endroit, les checks se superposaient sur une seule image
    bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=34, spacing=4)
    for layer, text in LAYER_LABELS.items():
        b = ToggleButton(text=text, group="nier_map_layer", state="down" if layer == "all" else "normal",
                         size_hint_x=None, width=190)
        b.bind(on_press=pick(layer))
        bar.add_widget(b)
    bar.add_widget(Label(text=""))
    root.add_widget(bar)
    root.add_widget(legend)
    root.add_widget(view)

    def fit(*_):
        """Cadre la carte dans la vue tant que l'utilisateur n'a ni zoome ni deplace (la vue change de taille
        apres sa creation : un cadrage unique laissait la carte minuscule dans un coin, vu sur capture)."""
        if view.width > 50 and view.height > 50 and not state["touched"]:
            s = max(0.3, min(view.width / info.width, view.height / info.height))
            scatter.scale = s
            scatter.pos = (view.x + (view.width - info.width * s) / 2,
                           view.y + (view.height - info.height * s) / 2)

    view.bind(size=fit, pos=fit)

    def to_canvas(m):
        px, py = info.to_pixel(m.x, m.z)
        return px, info.height - py           # Kivy : origine en bas a gauche

    def refresh(_dt):
        fit()
        st = getattr(ctx, "state", None)
        hints = list(st.hints) if st else []
        missing = getattr(ctx, "missing_locations", set()) or set()
        names = getattr(ctx, "location_names", None)
        try:
            remaining = {names.lookup_in_slot(i) for i in missing} if names else set()
        except Exception:
            remaining = set()
        player = None
        try:
            if ctx.nier.in_game():
                player = ctx.nier.position()
        except Exception:
            player = None
        marks = wm.markers(hints, remaining, player, state["layer"])
        zoom = max(scatter.scale, 0.3)
        # On ne redessine que si quelque chose a change (270 cercles recrees chaque seconde faisaient ramer la
        # molette) ; les checks sont UN seul lot de points au lieu d'un cercle de 180 segments chacun.
        sig = (state["layer"], round(zoom, 1), len(remaining), len(hints),
               None if player is None else (round(player[0]), round(player[2])))
        if sig == state.get("sig"):
            return
        state["sig"] = sig
        image.canvas.after.clear()
        with image.canvas.after:
            pts = []
            for m in marks:
                if m.kind == "check":
                    pts.extend(to_canvas(m))
            Color(0.75, 0.8, 0.85, 0.8)
            for i in range(0, len(pts), 2000):          # un lot = 1000 points au plus
                Point(points=pts[i:i + 2000], pointsize=2.5 / zoom)
            for m in marks:
                if m.kind == "check":
                    continue
                x, y = to_canvas(m)
                r = (7.0 if m.kind == "hint" else 6.0) / zoom
                Color(0, 0, 0, 1)
                Ellipse(pos=(x - r * 1.25, y - r * 1.25), size=(2.5 * r, 2.5 * r), segments=16)
                Color(*((1.0, 0.85, 0.1, 1.0) if m.kind == "hint" else (1.0, 0.2, 0.2, 1.0)))
                Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r), segments=16)
        n_h = sum(1 for m in marks if m.kind == "hint")
        n_c = sum(1 for m in marks if m.kind == "check")
        last = next((m.label for m in reversed(marks) if m.kind == "hint"), "")
        legend.text = (f"  {LAYER_LABELS[state['layer']]}   Hints: {n_h} (yellow)   Remaining checks with a location: "
                       f"{n_c} (grey)   You: red   Indoor / underground rooms: orange   {last}")

    Clock.schedule_interval(refresh, 0.5)
    return root
