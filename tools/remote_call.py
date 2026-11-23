"""Appel d'une fonction du jeu (convention x64 Windows) avec jusqu'a 4 parametres entiers.

Ecrit un petit bout de code dans le jeu :
    sub rsp,0x28 ; mov rcx,a ; mov rdx,b ; mov r8,c ; mov r9,d ; mov rax,f ; call rax ;
    mov [resultat],rax ; add rsp,0x28 ; ret
puis l'execute dans un nouveau fil (CreateRemoteThread) et renvoie rax.
"""
from __future__ import annotations

import ctypes
import struct
import sys
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MEM_COMMIT_RESERVE = 0x3000
PAGE_EXECUTE_READWRITE = 0x40
MEM_RELEASE = 0x8000


def remote_call(mem, func: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, timeout_ms: int = 5000) -> int:
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    k.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    k.CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                     ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    k.CreateRemoteThread.restype = wintypes.HANDLE
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    page = k.VirtualAllocEx(h, None, 0x1000, MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE)
    if not page:
        raise OSError("VirtualAllocEx")
    result = page + 0x800
    code = (b"\x48\x83\xEC\x28"
            + b"\x48\xB9" + struct.pack("<Q", a)
            + b"\x48\xBA" + struct.pack("<Q", b)
            + b"\x49\xB8" + struct.pack("<Q", c)
            + b"\x49\xB9" + struct.pack("<Q", d)
            + b"\x48\xB8" + struct.pack("<Q", func)
            + b"\xFF\xD0"
            + b"\x48\xA3" + struct.pack("<Q", result)
            + b"\x48\x83\xC4\x28\xC3")
    mem.write(page, code)
    t = k.CreateRemoteThread(h, None, 0, ctypes.c_void_p(page), None, 0, None)
    if not t:
        k.VirtualFreeEx(h, ctypes.c_void_p(page), 0, MEM_RELEASE)
        raise OSError("CreateRemoteThread")
    k.WaitForSingleObject(t, timeout_ms)
    ret = struct.unpack("<Q", mem.read(result, 8))[0]
    k.VirtualFreeEx(h, ctypes.c_void_p(page), 0, MEM_RELEASE)
    return ret
