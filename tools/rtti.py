"""Outils RTTI/heap : vtable d'une classe par son nom MSVC et instances en memoire."""
import ctypes, re, struct, sys
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
EXE = r"C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\NieRAutomata.exe"
D = open(EXE, "rb").read()
_pe = struct.unpack_from("<I", D, 0x3C)[0]
_n = struct.unpack_from("<H", D, _pe + 6)[0]
_opt = struct.unpack_from("<H", D, _pe + 20)[0]
SECS = [struct.unpack_from("<IIII", D, _pe + 24 + _opt + i * 40 + 8) for i in range(_n)]

def off2rva(o):
    for vsz, va, rsz, raw in SECS:
        if raw <= o < raw + rsz: return va + o - raw

def vtables(cls: bytes):
    td = off2rva(D.find(cls) - 0x10); out = []
    for m in re.finditer(re.escape(struct.pack("<I", td)), D):
        col = m.start() - 12
        sig, offs, cd, tdr, chd, selfr = struct.unpack_from("<IIIIII", D, col)
        if sig == 1 and selfr == off2rva(col):
            for v in re.finditer(re.escape(struct.pack("<Q", 0x140000000 + selfr)), D):
                out.append((off2rva(v.start()) + 8, offs))
    return out

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD),
                ("PartitionId", wintypes.WORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]

def instances(mem, vt_rva):
    k = mem._k
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    target = struct.pack("<Q", mem.base + vt_rva); addr = 0; found = []
    while addr < 0x7FFFFFFFFFFF:
        mbi = MBI()
        if not k.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)): break
        base = mbi.BaseAddress or 0; size = mbi.RegionSize
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40) and size < 0x40000000:
            try:
                data = mem.read(base, size); i = data.find(target)
                while i != -1:
                    if i % 8 == 0: found.append(base + i)
                    i = data.find(target, i + 1)
            except OSError: pass
        addr = base + size
    return found
