"""Enregistre (horodatage, phase, x, y, z) de 2B toutes les 10 s dans tools/path_log.tsv."""
import struct, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.memory import ProcessMemory, read_cstr
LOG = Path(__file__).with_name("path_log.tsv")
while True:
    m = ProcessMemory.attach()
    if m is None:
        time.sleep(10); continue
    try:
        while m.is_alive():
            p = struct.unpack("<Q", m.read(m.base + 0x1020C88, 8))[0]
            if p:
                x, y, z = struct.unpack("<3f", m.read(p + 0x50, 12))
                ph = read_cstr(m, 0xF64B20)
                with LOG.open("a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{ph}\t{x:.1f}\t{y:.1f}\t{z:.1f}\n")
            time.sleep(10)
    except OSError:
        time.sleep(5)
