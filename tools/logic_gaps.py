"""Lacunes de logique restantes (peche, fins W/E/B/C/D, objets cles, ennemis non places).

Lecture seule (exe + CPK via le cache de extract_research). Chaque partie est un module separe
(tools/logic_gaps_<partie>.py, fonction run() -> dict) lance l'un apres l'autre pour limiter la RAM.

    python tools/logic_gaps.py [fishing|endings|keyitems|enemies ...] [--out docs/research]

Sortie : docs/research/logic_gaps_resolved.json (les parties non relancees sont conservees).
"""
import gc, importlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PARTS = ["fishing", "endings", "keyitems", "enemies"]


def main():
    args = sys.argv[1:]
    out = ROOT.parent / "docs" / "research"
    if "--out" in args:
        i = args.index("--out"); out = Path(args[i + 1]); del args[i:i + 2]
    parts = [a for a in args if a in PARTS] or PARTS
    dst = out / "logic_gaps_resolved.json"
    res = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else {}
    res["_source"] = "tools/logic_gaps.py (+ tools/logic_gaps_<partie>.py), lecture statique NieRAutomata.exe v1.04 + CPK"
    for p in parts:
        mod = importlib.import_module(f"logic_gaps_{p}")
        print(f"[{p}] ...", flush=True)
        res[p] = mod.run()
        del mod; sys.modules.pop(f"logic_gaps_{p}", None); gc.collect()
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", dst)


if __name__ == "__main__":
    main()
