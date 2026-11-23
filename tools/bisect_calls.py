"""Dichotomie sur les appels a une fonction d'entree (ex. bouton d'esquive 0x49f190).

    python tools/bisect_calls.py apply 0 17     # neutralise les sites [0, 17)
    python tools/bisect_calls.py restore        # remet tout
Neutraliser = remplacer `call rel32` (5 octets) par `xor eax,eax ; nop3` : le bouton lit "non presse".
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nier_automata.game.memory import ProcessMemory  # noqa: E402

EXE = r"C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\NieRAutomata.exe"
DELTA = 0xC00
TARGET = 0x49F190
EXCLUDE = {0x47E453}  # esquive aerienne deja connue
STATE = Path(__file__).with_name("bisect_state.json")
NEUTRAL = bytes.fromhex("31c00f1f00")
# mode flottant : xor eax,eax n'efface pas xmm0 -> xorps xmm0,xmm0 ; nop2
NEUTRAL_FLOAT = bytes.fromhex("0f57c06690")
MODE_FILE = Path(__file__).with_name("bisect_mode.txt")


TARGETS_FILE = Path(__file__).with_name("bisect_targets.json")


def targets() -> set[int]:
    if TARGETS_FILE.exists():
        return {int(t, 16) for t in json.loads(TARGETS_FILE.read_text())}
    return {TARGET}


def sites() -> list[int]:
    d = open(EXE, "rb").read()
    tset = targets()
    out = []
    for m in re.finditer(rb"\xE8", d[0x400:0xC00000]):
        off = m.start() + 0x400
        rel = struct.unpack_from("<i", d, off + 1)[0]
        rva = off + DELTA
        if rva + 5 + rel in tset and rva not in EXCLUDE:
            out.append(rva)
    return out


def restore(mem) -> None:
    if not STATE.exists():
        return
    for rva, orig in json.loads(STATE.read_text()).items():
        mem.write_code(mem.base + int(rva), bytes.fromhex(orig))
    STATE.unlink()


def apply(mem, lo: int, hi: int) -> None:
    restore(mem)
    s = sites()
    saved = {}
    for rva in s[lo:hi]:
        cur = mem.read(mem.base + rva, 5)
        if cur[0] != 0xE8:
            continue
        saved[str(rva)] = cur.hex()
        neutral = NEUTRAL_FLOAT if MODE_FILE.exists() and MODE_FILE.read_text().strip() == "float" else NEUTRAL
        mem.write_code(mem.base + rva, neutral)
    STATE.write_text(json.dumps(saved))
    print(f"{len(s)} sites, neutralises [{lo},{hi}) :", [hex(r) for r in s[lo:hi]])


if __name__ == "__main__":
    m = ProcessMemory.attach()
    if sys.argv[1] == "restore":
        restore(m)
        print("restaure")
    else:
        apply(m, int(sys.argv[2]), int(sys.argv[3]))
