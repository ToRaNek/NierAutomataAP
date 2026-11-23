"""NieR:Automata pour Archipelago.

Le monde AP n'est charge que si Archipelago est present (les tests unitaires
importent les sous-modules purs sans Archipelago).
"""
import importlib.util

if importlib.util.find_spec("BaseClasses") is not None:
    from .world import NierAutomataWorld  # noqa: F401
