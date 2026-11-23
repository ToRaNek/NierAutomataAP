"""Limites de fonctions (.pdata) et references (call/jmp rel32, lea rip, pointeurs absolus)."""
import bisect, re, struct
EXE = r"C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\NieRAutomata.exe"
D = open(EXE, "rb").read()
IMG = 0x140000000
_pe = struct.unpack_from("<I", D, 0x3C)[0]; _opt = struct.unpack_from("<H", D, _pe + 20)[0]
_n = struct.unpack_from("<H", D, _pe + 6)[0]
SECS = [struct.unpack_from("<IIII", D, _pe + 24 + _opt + i * 40 + 8) for i in range(_n)]
def rva2off(r):
    for vsz, va, rsz, raw in SECS:
        if va <= r < va + rsz: return raw + r - va
def off2rva(o):
    for vsz, va, rsz, raw in SECS:
        if raw <= o < raw + rsz: return va + o - raw
# .pdata : data directory 3 (exception)
_dd = _pe + 24 + 0x70 + 3 * 8
_pr, _ps = struct.unpack_from("<II", D, _dd)
FUNCS = []
for i in range(_ps // 12):
    b, e, u = struct.unpack_from("<III", D, rva2off(_pr) + i * 12)
    FUNCS.append((b, e))
FUNCS.sort(); _starts = [b for b, _ in FUNCS]
def func_of(rva):
    i = bisect.bisect_right(_starts, rva) - 1
    if i >= 0 and FUNCS[i][0] <= rva < FUNCS[i][1]: return FUNCS[i]
_TEXT_RAW = SECS[0][3]; _TEXT_VA = SECS[0][1]; _TEXT = D[_TEXT_RAW:_TEXT_RAW + SECS[0][2]]
def refs(t):
    out = []
    for m in re.finditer(rb"[\xE8\xE9]", _TEXT):
        i = m.start()
        if i + 5 <= len(_TEXT) and _TEXT_VA + i + 5 + struct.unpack_from("<i", _TEXT, i + 1)[0] == t:
            out.append(("call" if _TEXT[i] == 0xE8 else "jmp", _TEXT_VA + i))
    for m in re.finditer(rb"[\x48\x4C]\x8D[\x05\x0D\x15\x1D\x25\x2D\x35\x3D]", _TEXT):
        i = m.start()
        if _TEXT_VA + i + 7 + struct.unpack_from("<i", _TEXT, i + 3)[0] == t: out.append(("lea", _TEXT_VA + i))
    for m in re.finditer(re.escape(struct.pack("<Q", IMG + t)), D):
        out.append(("ptr", off2rva(m.start())))
    return out
