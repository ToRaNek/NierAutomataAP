"""Photos et comparaisons de la memoire de NieR:Automata.

    python tools/memdiff.py snap avant        # photo
    python tools/memdiff.py diff avant apres [--small] [--exclude rien]
Methode : snap avant, faire UNE action en jeu (ouvrir un coffre...), snap apres,
attendre sans rien faire, snap rien ; diff avant apres --exclude rien --small.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nier_automata.game.memory import ProcessMemory  # noqa: E402
from nier_automata.game.snapshot import diff_u32, exclude_offsets, filter_small  # noqa: E402

START, END, BLOCK = 0xF00000, 0x1800000, 0x10000
SNAPS = Path(__file__).with_name("snaps")


def snap(name: str) -> None:
    mem = ProcessMemory.attach()
    if mem is None:
        sys.exit("Jeu non lance.")
    data, bad = bytearray(), []
    for off in range(START, END, BLOCK):
        try:
            chunk = mem.read(mem.base + off, BLOCK)
        except OSError:
            chunk, _ = b"", bad.append(off)
        data += chunk.ljust(BLOCK, b"\x00")
    SNAPS.mkdir(exist_ok=True)
    (SNAPS / f"{name}.bin").write_bytes(bytes(data))
    print(f"{name}: {len(data)} octets, {len(bad)} blocs illisibles")


def diff(a: str, b: str, small: bool, exclude: str | None) -> None:
    ra, rb = (SNAPS / f"{a}.bin").read_bytes(), (SNAPS / f"{b}.bin").read_bytes()
    changes = diff_u32(ra, rb, START)
    if exclude:
        rc = (SNAPS / f"{exclude}.bin").read_bytes()
        changes = exclude_offsets(changes, {o for o, _, _ in diff_u32(rb, rc, START)})
    if small:
        changes = filter_small(changes, max_delta=2)
    for off, old, new in changes[:300]:
        print(f"0x{off:07X}: 0x{old:08X} -> 0x{new:08X}")
    print(f"{len(changes)} changements")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snap"); s.add_argument("name")
    d = sub.add_parser("diff"); d.add_argument("a"); d.add_argument("b")
    d.add_argument("--small", action="store_true"); d.add_argument("--exclude")
    args = ap.parse_args()
    snap(args.name) if args.cmd == "snap" else diff(args.a, args.b, args.small, args.exclude)


if __name__ == "__main__":
    main()
