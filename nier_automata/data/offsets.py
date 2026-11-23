"""Versions connues de NieRAutomata.exe et offsets memoire (relatifs a la base du module).

Source : AutomataSpeedrunMod (jackalstomper), DLLMain.cpp / src/infra/HashCheck.cpp.
v1.04 = memes offsets que v1.03 (seul le binaire a grossi de 11 ko).
"""
from __future__ import annotations

import hashlib
from typing import Optional

VERSIONS: dict[str, str] = {
    "f814b0341d5d0eddb6a7e3266d1971609f889b7a80059c2fc7858cd239404c2e": "v1.04",  # v1.03
    "09854c2d45d9a72e66357e72f50cee379bb2eafe35b3d64e5e88f4eddc8613fa": "v1.04",  # v1.04
}

OFFSETS: dict[str, dict[str, int]] = {
    "v1.04": {
        "currentPhase": 0xF64B20,
        "isWorldLoaded": 0xF6E3C0,
        "playerSetName": 0x124E1CC,
        "isLoading": 0x13ECEB8,
        "itemTableStart": 0x148C834,
        "chipTableStart": 0x148E780,
        "playerLocation": 0x1774F00,
        "unitData": 0x1494838,
        # Hypothese : nierhook v1.02 weapons_first=0x148DCC4, bloc inventaire decale de +0x370
        # en v1.03 (items 0x148C4C4 -> 0x148C834). A confirmer avec tools/probe.py.
        "weaponTableStart": 0x148E034,
        # Trouves en jeu le 2026-11-23 (1720 G et 512/1058 PV confirmes par ToRaNek).
        "funds": 0x148C830,
        "playerEntity": 0x1020C88,
    },
}


def detect_version(exe_path: str) -> Optional[str]:
    h = hashlib.sha256()
    with open(exe_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return VERSIONS.get(h.hexdigest())
