/* NieR:Automata AP mod : dinput8.dll place a cote de NieRAutomata.exe.

   Le jeu charge dinput8.dll pour une seule fonction (DirectInput8Create) : on la transmet a la vraie DLL du
   systeme, et on ouvre dans le jeu une socket locale (127.0.0.1) par laquelle le client Archipelago lit et ecrit
   la memoire du jeu et appelle ses fonctions. Le client n'a plus besoin d'ouvrir le processus du jeu de
   l'exterieur : c'est ce qui ne marche pas sous Linux / Proton.

   Protocole (little-endian), une requete = 1 octet d'operation + champs, une reponse par requete :
     1 INFO                               -> u32 version, u32 pid, u64 base de NieRAutomata.exe
     2 READ   u64 adresse, u32 taille      -> u8 ok, [taille octets si ok]
     3 WRITE  u64 adresse, u32 taille, u8 code, octets -> u8 ok      (code=1 : page de code, protection levee)
     4 QUERY  u64 adresse                  -> u8 ok, u64 base, u64 taille, u32 etat, u32 protection
     5 ALLOC  u64 pres_de (hint), u32 taille      -> u64 adresse (0 = echec) ; pres_de=0 : n'importe ou
     6 FREE   u64 adresse                  -> u8 ok
     7 CALL   u64 fonction, 5 x u64 args, u32 delai_ms -> u8 ok, u64 rax   (appel dans un fil du jeu)

   Compilation : python mod/build_mod.py   (zig cc, cible x86_64-windows-gnu) */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MOD_VERSION 1
#define DEFAULT_PORT 38291
#define MAX_IO (16 * 1024 * 1024)

typedef uint64_t (*fn5)(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
typedef struct { fn5 f; uint64_t a[5]; uint64_t ret; } call_t;

static HMODULE real_dinput8;
static FARPROC real_create;

static int recv_all(SOCKET s, void *buf, int n) {
    char *p = (char *)buf;
    while (n > 0) {
        int r = recv(s, p, n, 0);
        if (r <= 0) return 0;
        p += r; n -= r;
    }
    return 1;
}

static int send_all(SOCKET s, const void *buf, int n) {
    const char *p = (const char *)buf;
    while (n > 0) {
        int r = send(s, p, n, 0);
        if (r <= 0) return 0;
        p += r; n -= r;
    }
    return 1;
}

static DWORD WINAPI call_thread(LPVOID arg) {
    call_t *c = (call_t *)arg;
    c->ret = c->f(c->a[0], c->a[1], c->a[2], c->a[3], c->a[4]);
    return 0;
}

static uint64_t alloc_near(uint64_t hint, uint32_t size) {
    if (!hint) return (uint64_t)VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    /* a moins de 2 Go de `hint` : un saut relatif 32 bits doit pouvoir l'atteindre */
    for (uint64_t d = 0x10000; d < 0x7F000000ULL; d += 0x10000) {
        for (int sign = 0; sign < 2; sign++) {
            uint64_t want = sign ? hint + d : hint - d;
            if (sign == 0 && d > hint) continue;
            void *p = VirtualAlloc((void *)(want & ~0xFFFFULL), size, MEM_COMMIT | MEM_RESERVE,
                                   PAGE_EXECUTE_READWRITE);
            if (p) return (uint64_t)p;
        }
    }
    return 0;
}

static void serve(SOCKET s) {
    HANDLE self = GetCurrentProcess();
    char *buf = (char *)malloc(MAX_IO);
    if (!buf) return;
    for (;;) {
        uint8_t op;
        if (!recv_all(s, &op, 1)) break;
        if (op == 1) {
            struct { uint32_t version, pid; uint64_t base; } r;
            r.version = MOD_VERSION; r.pid = GetCurrentProcessId(); r.base = (uint64_t)GetModuleHandleW(NULL);
            if (!send_all(s, &r, sizeof r)) break;
        } else if (op == 2) {
            uint64_t addr; uint32_t len; SIZE_T got = 0; uint8_t ok;
            if (!recv_all(s, &addr, 8) || !recv_all(s, &len, 4) || len > MAX_IO) break;
            ok = ReadProcessMemory(self, (void *)addr, buf, len, &got) && got == len;
            if (!send_all(s, &ok, 1) || (ok && !send_all(s, buf, (int)len))) break;
        } else if (op == 3) {
            uint64_t addr; uint32_t len; uint8_t code, ok; SIZE_T put = 0; DWORD old = 0;
            if (!recv_all(s, &addr, 8) || !recv_all(s, &len, 4) || !recv_all(s, &code, 1) || len > MAX_IO) break;
            if (!recv_all(s, buf, (int)len)) break;
            if (code && !VirtualProtect((void *)addr, len, PAGE_EXECUTE_READWRITE, &old)) code = 0;
            ok = WriteProcessMemory(self, (void *)addr, buf, len, &put) && put == len;
            if (code) {
                VirtualProtect((void *)addr, len, old, &old);
                FlushInstructionCache(self, (void *)addr, len);
            }
            if (!send_all(s, &ok, 1)) break;
        } else if (op == 4) {
            uint64_t addr; MEMORY_BASIC_INFORMATION mbi;
            struct { uint8_t ok; uint64_t base, size; uint32_t state, protect; } __attribute__((packed)) r;
            if (!recv_all(s, &addr, 8)) break;
            r.ok = VirtualQuery((void *)addr, &mbi, sizeof mbi) != 0;
            r.base = (uint64_t)mbi.BaseAddress; r.size = (uint64_t)mbi.RegionSize;
            r.state = mbi.State; r.protect = mbi.Protect;
            if (!send_all(s, &r, sizeof r)) break;
        } else if (op == 5) {
            uint64_t hint, out; uint32_t size;
            if (!recv_all(s, &hint, 8) || !recv_all(s, &size, 4)) break;
            out = alloc_near(hint, size);
            if (!send_all(s, &out, 8)) break;
        } else if (op == 6) {
            uint64_t addr; uint8_t ok;
            if (!recv_all(s, &addr, 8)) break;
            ok = VirtualFree((void *)addr, 0, MEM_RELEASE) != 0;
            if (!send_all(s, &ok, 1)) break;
        } else if (op == 7) {
            struct { uint64_t f, a[5]; uint32_t timeout; } __attribute__((packed)) q;
            struct { uint8_t ok; uint64_t ret; } __attribute__((packed)) r;
            call_t *c;
            HANDLE t;
            if (!recv_all(s, &q, sizeof q)) break;
            c = (call_t *)calloc(1, sizeof *c);       /* jamais libere si le delai expire : le fil s'en sert */
            r.ok = 0; r.ret = 0;
            if (c) {
                c->f = (fn5)q.f;
                memcpy(c->a, q.a, sizeof c->a);
                t = CreateThread(NULL, 0, call_thread, c, 0, NULL);
                if (t) {
                    if (WaitForSingleObject(t, q.timeout ? q.timeout : 5000) == WAIT_OBJECT_0) {
                        r.ok = 1; r.ret = c->ret;
                        free(c);
                    }
                    CloseHandle(t);
                }
            }
            if (!send_all(s, &r, sizeof r)) break;
        } else {
            break;                                     /* operation inconnue : on ferme */
        }
    }
    free(buf);
}

static DWORD WINAPI server_thread(LPVOID unused) {
    WSADATA w;
    SOCKET ls;
    struct sockaddr_in a;
    char env[16];
    int port = DEFAULT_PORT, yes = 1;
    (void)unused;
    if (GetEnvironmentVariableA("NIER_AP_MOD_PORT", env, sizeof env) > 0 && atoi(env) > 0) port = atoi(env);
    if (WSAStartup(MAKEWORD(2, 2), &w)) return 0;
    ls = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (ls == INVALID_SOCKET) return 0;
    setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, (const char *)&yes, sizeof yes);
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons((u_short)port);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);        /* jamais ouvert au reseau */
    if (bind(ls, (struct sockaddr *)&a, sizeof a) || listen(ls, 2)) { closesocket(ls); return 0; }
    for (;;) {
        SOCKET s = accept(ls, NULL, NULL);
        if (s == INVALID_SOCKET) { Sleep(200); continue; }
        setsockopt(s, IPPROTO_TCP, TCP_NODELAY, (const char *)&yes, sizeof yes);
        serve(s);
        closesocket(s);
    }
}

/* seule fonction que le jeu demande a dinput8.dll : transmise a la vraie */
__declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE inst, DWORD ver, REFIID iid, LPVOID *out,
                                                        void *outer) {
    typedef HRESULT(WINAPI *create_t)(HINSTANCE, DWORD, REFIID, LPVOID *, void *);
    if (!real_create) {
        wchar_t path[MAX_PATH + 16];
        UINT n = GetSystemDirectoryW(path, MAX_PATH);
        if (!n) return E_FAIL;
        lstrcpyW(path + n, L"\\dinput8.dll");
        real_dinput8 = LoadLibraryW(path);
        if (!real_dinput8) return E_FAIL;
        real_create = GetProcAddress(real_dinput8, "DirectInput8Create");
        if (!real_create) return E_FAIL;
    }
    return ((create_t)real_create)(inst, ver, iid, out, outer);
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        HANDLE t;
        DisableThreadLibraryCalls(inst);
        t = CreateThread(NULL, 0, server_thread, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
