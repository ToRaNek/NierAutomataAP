/* NieR:Automata AP mod : dinput8.dll place a cote de NieRAutomata.exe.

   Le jeu charge dinput8.dll pour une seule fonction (DirectInput8Create) : on la transmet a la vraie DLL du
   systeme, et on ouvre dans le jeu une socket locale (127.0.0.1) par laquelle le client Archipelago lit et ecrit
   la memoire du jeu et appelle ses fonctions. Le client n'a plus besoin d'ouvrir le processus du jeu de
   l'exterieur : c'est ce qui ne marche pas sous Linux / Proton.

   Securite : la socket n'ecoute que sur 127.0.0.1 et exige une cle. A chaque lancement le mod tire 16 octets au
   hasard et les ecrit dans %LOCALAPPDATA%\NierAutomataAP\mod_token (profil de l'utilisateur). Le client doit
   envoyer ces 16 octets en premier ; sinon la connexion est fermee sans rien executer.

   Protocole (little-endian), apres la cle : une requete = 1 octet d'operation + champs, une reponse par requete :
     1 INFO                               -> u32 version, u32 pid, u64 base de NieRAutomata.exe
     2 READ   u64 adresse, u32 taille      -> u8 ok, [taille octets si ok]
     3 WRITE  u64 adresse, u32 taille, u8 code, octets -> u8 ok      (code=1 : page de code, protection levee)
     4 QUERY  u64 adresse                  -> u8 ok, u64 base, u64 taille, u32 etat, u32 protection
     5 ALLOC  u64 adresse (0 = n'importe ou), u32 taille, u32 protection -> u64 adresse (0 = echec)
     6 FREE   u64 adresse                  -> u8 ok
     7 CALL   u64 fonction, 5 x u64 args, u32 delai_ms -> u8 ok, u64 rax   (appel dans un fil du jeu)
     8 WALLS  u64 camera_position, u64 camera_cible, u64 camera_angle, u64 pointeur_joueur, u32 nombre, nombre x mur (84 octets :
              6 floats x1 y z1 x2 z2 hauteur + 64 octets de texte) -> u8 ok       (nombre = 0 : plus de murs)
    10 NOTE   u32 couleur 0xRRGGBB, u32 duree_ms, 160 octets de texte UTF-8 -> u8 ok   (message a l'ecran)
     9 WALLSTATE                          -> i32 : 1 murs dessines, 0 pas encore, -1 echec de l'affichage
    11 SCAN   u16 taille (1..1024), u16 alignement, u32 maximum (<= 4096), motif -> u32 nombre, nombre x u64
              (recherche du motif dans les regions lecture/ecriture du jeu, faite ici : le client n'a plus a
              rapatrier 2 Go par la socket a chaque recherche, ce qui prenait 16 s et gelait son demarrage)

   Compilation : python mod/build_mod.py   (zig cc, cible x86_64-windows-gnu) */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "overlay.h"

#define MOD_VERSION 8
#define DEFAULT_PORT 38291
#define MAX_IO (16 * 1024 * 1024)

typedef uint64_t (*fn5)(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
typedef struct { fn5 f; uint64_t a[5]; uint64_t ret; } call_t;

BOOLEAN NTAPI SystemFunction036(PVOID buf, ULONG len);      /* RtlGenRandom (advapi32) */

static uint8_t token[16];
static int token_ready;
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

/* tire la cle et l'ecrit dans le profil de l'utilisateur ; 0 si impossible (alors le mod n'ecoute pas) */
static int make_token(void) {
    char dir[MAX_PATH], path[MAX_PATH + 32];
    HANDLE f;
    DWORD put = 0;
    DWORD n = GetEnvironmentVariableA("LOCALAPPDATA", dir, sizeof dir);
    if (!n || n >= sizeof dir - 32) return 0;
    if (!SystemFunction036(token, sizeof token)) return 0;
    lstrcatA(dir, "\\NierAutomataAP");
    CreateDirectoryA(dir, NULL);
    lstrcpyA(path, dir);
    lstrcatA(path, "\\mod_token");
    f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) return 0;
    WriteFile(f, token, sizeof token, &put, NULL);
    CloseHandle(f);
    return put == sizeof token;
}

#define SCAN_MAX_PATTERN 1024
#define SCAN_MAX_RESULTS 4096

/* Adresses ou le motif apparait dans les regions lecture/ecriture engagees (memes regions que la recherche du
   client). Les regions de notre tampon de lecture et de notre pile sont sautees : elles contiennent le motif. */
static uint32_t scan_memory(HANDLE self, char *buf, const uint8_t *pat, uint32_t len, uint32_t align,
                            uint64_t *out, uint32_t max) {
    MEMORY_BASIC_INFORMATION mbi, own;
    uint64_t addr = 0, skip_buf = 0, skip_stack = 0;
    uint32_t n = 0;
    if (VirtualQuery(buf, &own, sizeof own)) skip_buf = (uint64_t)own.AllocationBase;
    if (VirtualQuery(pat, &own, sizeof own)) skip_stack = (uint64_t)own.AllocationBase;
    while (n < max && addr < 0x7FFFFFFF0000ULL && VirtualQuery((void *)addr, &mbi, sizeof mbi)) {
        uint64_t base = (uint64_t)mbi.BaseAddress, size = (uint64_t)mbi.RegionSize, off = 0;
        uint64_t owner = (uint64_t)mbi.AllocationBase;
        if (!size) break;
        if (mbi.State == MEM_COMMIT && (mbi.Protect == PAGE_READWRITE || mbi.Protect == PAGE_EXECUTE_READWRITE)
                && size < 0x40000000ULL && owner != skip_buf && owner != skip_stack) {
            while (off < size && n < max) {
                uint64_t want = size - off, i = 0;
                SIZE_T got = 0;
                if (want > MAX_IO) want = MAX_IO;
                if (!ReadProcessMemory(self, (void *)(base + off), buf, (SIZE_T)want, &got) || got < len) break;
                while (i + len <= got && n < max) {
                    const uint8_t *p = (const uint8_t *)memchr(buf + i, pat[0], (size_t)(got - len + 1 - i));
                    if (!p) break;
                    i = (uint64_t)(p - (const uint8_t *)buf);
                    if (!memcmp(p, pat, len) && (base + off + i) % align == 0) out[n++] = base + off + i;
                    i++;
                }
                if (got < want || off + want >= size) break;
                off += want - (len - 1);               /* chevauchement : motif a cheval sur deux morceaux */
            }
        }
        addr = base + size;
    }
    return n;
}

static void serve(SOCKET s) {
    HANDLE self = GetCurrentProcess();
    uint8_t got[sizeof token], diff = 0;
    char *buf;
    DWORD wait = 500, start = GetTickCount();
    size_t i, have = 0;
    /* la cle doit arriver en entier en 3 secondes au total : une connexion muette ne bloque pas le mod plus */
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char *)&wait, sizeof wait);
    while (have < sizeof got) {
        int r;
        if (GetTickCount() - start > 3000) return;
        r = recv(s, (char *)got + have, (int)(sizeof got - have), 0);
        if (r > 0) have += (size_t)r;
        else if (r == 0 || WSAGetLastError() != WSAETIMEDOUT) return;
    }
    for (i = 0; i < sizeof token; i++) diff |= got[i] ^ token[i];      /* comparaison a temps constant */
    if (diff) return;
    wait = 0;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char *)&wait, sizeof wait);
    buf = (char *)malloc(MAX_IO);
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
            uint64_t at, out; uint32_t size, protect;
            if (!recv_all(s, &at, 8) || !recv_all(s, &size, 4) || !recv_all(s, &protect, 4)) break;
            out = (uint64_t)VirtualAlloc((void *)at, size, MEM_COMMIT | MEM_RESERVE, protect);
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
        } else if (op == 8) {
            struct { uint64_t eye, target, fov, player; uint32_t count; } __attribute__((packed)) q;
            static overlay_wall_t w[OVERLAY_MAX_WALLS];
            uint8_t ok = 1;
            if (!recv_all(s, &q, sizeof q) || q.count > OVERLAY_MAX_WALLS) break;
            if (q.count && !recv_all(s, w, (int)(sizeof(overlay_wall_t) * q.count))) break;
            for (uint32_t i = 0; i < q.count; i++) w[i].text[sizeof w[i].text - 1] = 0;
            overlay_set(w, (int)q.count, q.eye, q.target, q.fov, q.player);
            if (!send_all(s, &ok, 1)) break;
        } else if (op == 9) {
            int32_t st = overlay_status();
            if (!send_all(s, &st, 4)) break;
        } else if (op == 10) {
            struct { uint32_t rgb, ms; char text[160]; } __attribute__((packed)) q;
            uint8_t ok = 1;
            if (!recv_all(s, &q, sizeof q)) break;
            q.text[sizeof q.text - 1] = 0;
            overlay_note(q.text, q.rgb, q.ms);
            if (!send_all(s, &ok, 1)) break;
        } else if (op == 11) {
            struct { uint16_t len, align; uint32_t max; } __attribute__((packed)) q;
            uint8_t pat[SCAN_MAX_PATTERN];
            uint64_t *found;
            uint32_t count;
            int sent;
            if (!recv_all(s, &q, sizeof q) || !q.len || q.len > sizeof pat || !q.max || q.max > SCAN_MAX_RESULTS) break;
            if (!recv_all(s, pat, q.len)) break;
            found = (uint64_t *)malloc(sizeof(uint64_t) * q.max);
            if (!found) break;
            count = scan_memory(self, buf, pat, q.len, q.align ? q.align : 1, found, q.max);
            sent = send_all(s, &count, 4) && (!count || send_all(s, found, (int)(count * 8)));
            free(found);
            if (!sent) break;
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
    /* port reserve : un autre programme ne peut pas s'y installer a notre place pour recevoir la cle */
    setsockopt(ls, SOL_SOCKET, SO_EXCLUSIVEADDRUSE, (const char *)&yes, sizeof yes);
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons((u_short)port);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);        /* jamais ouvert au reseau */
    if (bind(ls, (struct sockaddr *)&a, sizeof a) || listen(ls, 2)) { closesocket(ls); return 0; }
    /* La cle n'est ecrite qu'une fois le port obtenu : si un autre programme occupe le port, aucune nouvelle cle
       n'existe et celle du lancement precedent ne lui sert a rien. */
    token_ready = make_token();
    if (!token_ready) { closesocket(ls); return 0; }   /* pas de cle : on n'ecoute pas */
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
        overlay_start();
        t = CreateThread(NULL, 0, server_thread, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
