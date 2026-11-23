"""Point d'arret materiel en ecriture sur jusqu'a 4 adresses du jeu (registres DR0-DR3).

    python tools/hwwatch.py <secondes> <adresse_hex> [adresse_hex ...]
Attache un debogueur, arme les DR sur tous les threads, attend une ecriture, affiche RIP et les
adresses de retour trouvees sur la pile (pile d'appels approximative), puis se detache.
"""
import ctypes
import os
import struct
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nier_automata.game.memory import ProcessMemory  # noqa: E402

k = ctypes.WinDLL("kernel32", use_last_error=True)
DBG_CONTINUE, DBG_EXCEPTION_NOT_HANDLED = 0x00010002, 0x80010001
EXCEPTION_DEBUG_EVENT, CREATE_THREAD, EXIT_PROCESS = 1, 2, 5
EXC_SINGLE_STEP, EXC_BREAKPOINT = 0x80000004, 0x80000003
CONTEXT_DEBUG_REGISTERS = 0x00100010
CONTEXT_FULL = 0x0010000B | CONTEXT_DEBUG_REGISTERS


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("code", wintypes.DWORD), ("pid", wintypes.DWORD), ("tid", wintypes.DWORD),
                ("pad", wintypes.DWORD), ("u", ctypes.c_byte * 160)]


def ctx_buf():
    raw = ctypes.create_string_buffer(1232 + 16)
    addr = (ctypes.addressof(raw) + 15) & ~15
    return raw, addr


def thread_ids(pid):
    class TE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("tid", wintypes.DWORD),
                    ("owner", wintypes.DWORD), ("base", ctypes.c_long), ("delta", ctypes.c_long),
                    ("flags", wintypes.DWORD)]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(4, 0)
    te = TE(); te.dwSize = ctypes.sizeof(te); out = []
    ok = k.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.owner == pid: out.append(te.tid)
        ok = k.Thread32Next(snap, ctypes.byref(te))
    k.CloseHandle(snap)
    return out


def set_drs(tid, addrs, enable=True):
    k.OpenThread.restype = wintypes.HANDLE
    h = k.OpenThread(0x001F03FF, False, tid)
    if not h: return
    raw, a = ctx_buf()
    struct.pack_into("<I", raw, a - ctypes.addressof(raw) + 0x30, CONTEXT_DEBUG_REGISTERS)
    k.SuspendThread(h)
    if k.GetThreadContext(h, ctypes.c_void_p(a)):
        o = a - ctypes.addressof(raw)
        dr7 = 0
        for i in range(4):
            v = addrs[i] if enable and i < len(addrs) else 0
            struct.pack_into("<Q", raw, o + 0x48 + 8 * i, v)
            if v:
                if os.environ.get("HW_X"):
                    rw, ln = 0b00, 0b00  # execution
                else:
                    rw, ln = (0b11 if os.environ.get("HW_RW") else 0b01), 0b01
                dr7 |= (1 << (2 * i)) | (rw << (16 + 4 * i)) | (ln << (18 + 4 * i))  # 00=exec 01=ecriture 11=lecture/ecriture
        struct.pack_into("<Q", raw, o + 0x70, dr7)
        struct.pack_into("<Q", raw, o + 0x68, 0)
        k.SetThreadContext(h, ctypes.c_void_p(a))
    k.ResumeThread(h)
    k.CloseHandle(h)


def main():
    secs = float(sys.argv[1]); addrs = [int(x, 16) for x in sys.argv[2:6]]
    m = ProcessMemory.attach(); pid = m.pid; base = m.base
    if not k.DebugActiveProcess(pid):
        sys.exit(f"DebugActiveProcess a echoue ({ctypes.get_last_error()})")
    k.DebugSetProcessKillOnExit(False)
    armed = False; ev = DEBUG_EVENT(); t0 = time.time(); hit = None
    try:
        while time.time() - t0 < secs:
            if not k.WaitForDebugEvent(ctypes.byref(ev), 200):
                if not armed:
                    for tid in thread_ids(pid): set_drs(tid, addrs)
                    armed = True; print("arme sur", [hex(a) for a in addrs], flush=True)
                continue
            status = DBG_CONTINUE
            if ev.code == CREATE_THREAD and armed:
                set_drs(ev.tid, addrs)
            elif ev.code == EXCEPTION_DEBUG_EVENT:
                code = struct.unpack_from("<I", bytes(ev.u), 0)[0]
                if code == EXC_SINGLE_STEP and hit is None:
                    k.OpenThread.restype = wintypes.HANDLE
                    h = k.OpenThread(0x001F03FF, False, ev.tid)
                    raw, a = ctx_buf(); o = a - ctypes.addressof(raw)
                    struct.pack_into("<I", raw, o + 0x30, CONTEXT_FULL)
                    k.GetThreadContext(h, ctypes.c_void_p(a))
                    rip = struct.unpack_from("<Q", raw, o + 0xF8)[0]; rsp = struct.unpack_from("<Q", raw, o + 0x98)[0]
                    dr6 = struct.unpack_from("<Q", raw, o + 0x68)[0]
                    regs = {n: struct.unpack_from("<Q", raw, o + off)[0] for n, off in
                            (("rax", 0x78), ("rcx", 0x80), ("rdx", 0x88), ("rbx", 0x90), ("rsi", 0xA8), ("rdi", 0xB0),
                             ("r8", 0xB8), ("r9", 0xC0), ("r12", 0xD8), ("r13", 0xE0), ("r14", 0xE8), ("r15", 0xF0))}
                    k.CloseHandle(h)
                    stack = m.read(rsp, 0x400)
                    rets = [struct.unpack_from("<Q", stack, i)[0] - base for i in range(0, 0x400, 8)]
                    rets = [r for r in rets if 0x1000 <= r < 0xC1A000]
                    hit = (rip - base, dr6, regs, rets[:24])
                    print("ECRITURE ! RIP RVA", hex(rip - base), "dr6", hex(dr6), flush=True)
                    print(" regs", {n: hex(v) for n, v in regs.items()}, flush=True)
                    print(" pile (RVA):", [hex(r) for r in rets[:24]], flush=True)
                    for tid in thread_ids(pid): set_drs(tid, addrs, enable=False)
                    if os.environ.get("HW_X"):  # reprendre apres le point d'arret d'execution (RF)
                        k.OpenThread.restype = wintypes.HANDLE
                        h = k.OpenThread(0x001F03FF, False, ev.tid)
                        raw, a = ctx_buf(); o = a - ctypes.addressof(raw)
                        struct.pack_into("<I", raw, o + 0x30, CONTEXT_FULL)
                        k.GetThreadContext(h, ctypes.c_void_p(a))
                        ef = struct.unpack_from("<I", raw, o + 0x44)[0]
                        struct.pack_into("<I", raw, o + 0x44, ef | 0x10000)
                        k.SetThreadContext(h, ctypes.c_void_p(a)); k.CloseHandle(h)
                    break
                elif code not in (EXC_BREAKPOINT, EXC_SINGLE_STEP):
                    status = DBG_EXCEPTION_NOT_HANDLED
            elif ev.code == EXIT_PROCESS:
                print("jeu ferme"); return
            k.ContinueDebugEvent(ev.pid, ev.tid, status)
        else:
            print("rien detecte")
    finally:
        for tid in thread_ids(pid): set_drs(tid, addrs, enable=False)
        try: k.ContinueDebugEvent(ev.pid, ev.tid, DBG_CONTINUE)
        except Exception: pass
        k.DebugActiveProcessStop(pid)
        print("detache")


if __name__ == "__main__":
    main()
