"""Acces memoire : vrai processus (ctypes) ou fausse memoire pour les tests."""
from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from typing import Optional, Protocol


class Memory(Protocol):
    base: int

    def read(self, addr: int, size: int) -> bytes: ...

    def write(self, addr: int, data: bytes) -> None: ...


def read_u32(mem: Memory, offset: int) -> int:
    return struct.unpack("<I", mem.read(mem.base + offset, 4))[0]


def write_u32(mem: Memory, offset: int, value: int) -> None:
    mem.write(mem.base + offset, struct.pack("<I", value & 0xFFFFFFFF))


def read_cstr(mem: Memory, offset: int, maxlen: int = 64) -> str:
    raw = mem.read(mem.base + offset, maxlen)
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


class FakeMemory:
    def __init__(self, size: int = 0x2000000, base: int = 0x140000000):
        self.base = base
        self.buf = bytearray(size)

    def read(self, addr: int, size: int) -> bytes:
        o = addr - self.base
        return bytes(self.buf[o:o + size])

    def write(self, addr: int, data: bytes) -> None:
        o = addr - self.base
        self.buf[o:o + len(data)] = data


# --- Windows ---------------------------------------------------------------

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10
STILL_ACTIVE = 259


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", ctypes.c_wchar * 256), ("szExePath", ctypes.c_wchar * 260)]


def _k32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.WriteProcessMemory.argtypes = k.ReadProcessMemory.argtypes
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    return k


def _find_pid(k, exe_name: str) -> Optional[int]:
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = k.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe_name.lower():
                return entry.th32ProcessID
            ok = k.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return None


def _module_base(k, pid: int, exe_name: str) -> Optional[int]:
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    entry = MODULEENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = k.Module32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szModule.lower() == exe_name.lower():
                return entry.modBaseAddr
            ok = k.Module32NextW(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return None


class ProcessMemory:
    def __init__(self, k, handle, pid: int, base: int, exe_path: str):
        self._k = k
        self.handle = handle
        self.pid = pid
        self.base = base
        self.exe_path = exe_path

    @classmethod
    def attach(cls, exe_name: str = "NieRAutomata.exe") -> Optional["ProcessMemory"]:
        k = _k32()
        pid = _find_pid(k, exe_name)
        if pid is None:
            return None
        base = _module_base(k, pid, exe_name)
        if base is None:
            return None
        access = PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_LIMITED_INFORMATION
        handle = k.OpenProcess(access, False, pid)
        if not handle:
            return None
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        return cls(k, handle, pid, base, buf.value)

    def read(self, addr: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        n = ctypes.c_size_t(0)
        if not self._k.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
            raise OSError(ctypes.get_last_error(), f"ReadProcessMemory 0x{addr:X}")
        return buf.raw[:n.value]

    def write(self, addr: int, data: bytes) -> None:
        n = ctypes.c_size_t(0)
        if not self._k.WriteProcessMemory(self.handle, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n)):
            raise OSError(ctypes.get_last_error(), f"WriteProcessMemory 0x{addr:X}")

    def write_code(self, addr: int, data: bytes) -> None:
        """Ecrit dans le code du jeu (page .text en lecture/execution) : deprotege puis restaure."""
        k = self._k
        k.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        old = wintypes.DWORD()
        if not k.VirtualProtectEx(self.handle, ctypes.c_void_p(addr), len(data), 0x40, ctypes.byref(old)):
            raise OSError(ctypes.get_last_error(), f"VirtualProtectEx 0x{addr:X}")
        try:
            self.write(addr, data)
        finally:
            k.VirtualProtectEx(self.handle, ctypes.c_void_p(addr), len(data), old.value, ctypes.byref(old))

    def is_alive(self) -> bool:
        code = wintypes.DWORD(0)
        if not self._k.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE

    def close(self) -> None:
        if self.handle:
            self._k.CloseHandle(self.handle)
            self.handle = None
