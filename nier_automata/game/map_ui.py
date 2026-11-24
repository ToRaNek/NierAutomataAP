"""Onglet "Map" du client : carte vue de dessus, indices en jaune, checks restants en gris, joueur en rouge.
Molette ou pincement = zoom, glisser = deplacer."""
from __future__ import annotations

import os
from pathlib import Path

from . import worldmap as wm


def _map_file() -> str:
    """La carte est dans l'apworld (zip) : Kivy a besoin d'un vrai fichier."""
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NierAutomataAP"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "map.png"
    data = wm.map_png()
    if not f.exists() or f.stat().st_size != len(data):
        f.write_bytes(data)
    return str(f)


def build_map_tab(ctx):
    from kivy.clock import Clock
    from kivy.graphics import Color, Ellipse, Line
    from kivy.graphics.transformation import Matrix
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.image import Image
    from kivy.uix.label import Label
    from kivy.uix.scatter import Scatter
    from kivy.uix.stencilview import StencilView

    info = wm.load_info()

    class MapScatter(Scatter):
        def on_touch_down(self, touch):
            if touch.is_mouse_scrolling and self.parent.collide_point(*touch.pos):
                factor = 1.15 if touch.button == "scrolldown" else 1 / 1.15
                if 0.3 <= self.scale * factor <= 12:
                    self.apply_transform(Matrix().scale(factor, factor, factor), anchor=touch.pos)
                return True
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
    root.add_widget(legend)
    root.add_widget(view)
    state = {"fitted": False}

    def fit(*_):
        if view.width > 10 and not state["fitted"]:
            s = min(view.width / info.width, view.height / info.height)
            scatter.scale = max(0.3, s)
            scatter.pos = (view.x + (view.width - info.width * scatter.scale) / 2,
                           view.y + (view.height - info.height * scatter.scale) / 2)
            state["fitted"] = True

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
        marks = wm.markers(hints, remaining, player)
        image.canvas.after.clear()
        zoom = max(scatter.scale, 0.3)
        with image.canvas.after:
            for m in marks:
                x, y = to_canvas(m)
                if m.kind == "check":
                    Color(0.75, 0.8, 0.85, 0.75)
                    r = 3.0 / zoom
                elif m.kind == "hint":
                    Color(1.0, 0.85, 0.1, 1.0)
                    r = 7.0 / zoom
                else:
                    Color(1.0, 0.2, 0.2, 1.0)
                    r = 6.0 / zoom
                Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
                if m.kind != "check":
                    Color(0, 0, 0, 1)
                    Line(circle=(x, y, r), width=1.2 / zoom)
        n_h = sum(1 for m in marks if m.kind == "hint")
        n_c = sum(1 for m in marks if m.kind == "check")
        last = next((m.label for m in reversed(marks) if m.kind == "hint"), "")
        legend.text = f"  Hints: {n_h} (yellow)   Remaining checks with a location: {n_c} (grey)   You: red   {last}"

    Clock.schedule_interval(refresh, 1.0)
    return root
