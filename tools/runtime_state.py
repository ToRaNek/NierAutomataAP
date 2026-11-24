"""Etats d'execution lisibles par simple lecture memoire (NieR:Automata v1.04 Steam) -> runtime_state.json.

Usage :
    python tools/runtime_state.py [--out docs/research] [--save SlotData_N.dat] [--snap tools/snaps/x.bin]

Analyse STATIQUE uniquement (exe + data en lecture seule, jamais le processus). Regenere
docs/research/runtime_state.json :
  - SceneStateSystem (RVA 0xFC2680) : disposition du conteneur, hachage (crc32 zlib du nom complet), registre des
    1185 etats declares (core_hap.pak) avec leur hachage ;
  - tableau d'etat par quete de la sauvegarde (RVA 0x14946D0) + etat de fin de chaque quete (scripts mruby, hap,
    MailTable, MsgQueInfo) ;
  - bits des points d'acces (0x14957E0), drapeaux de fins (0x14957D8), route / personnage.
Chaque adresse codee ici est re-verifiee dans l'exe (octets / desassemblage) : une autre version fait echouer
`verify_exe()` au lieu de produire un JSON faux.
Options de controle hors ligne : --save (fichier SlotData : section texte 'SceneState' + tableaux) et --snap
(photo memoire tools/memdiff.py, RVA 0xF00000..0x1800000).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402

import bxm  # noqa: E402
import cpk  # noqa: E402
import extract_research as er  # noqa: E402
import mruby  # noqa: E402
import resolve_quests as rq  # noqa: E402
from xref import D, func_of, refs, rva2off  # noqa: E402

MD = Cs(CS_ARCH_X86, CS_MODE_64)
ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------------------------------- RVA
SSS = 0xFC2680             # hap::scene_state::SceneStateSystem (objet global, construit par 0xB06F0)
SSS_REG_PTR, SSS_REG_CNT = SSS + 0x68, SSS + 0x70      # registre des etats declares (DynamicArray<SceneState>)
SSS_ACT_PTR, SSS_ACT_CNT = SSS + 0x98, SSS + 0xA0      # etats ACTIFS, tries par crc32 croissant
ENTRY_SIZE = 0x20          # SceneState : +0 groupe*, +8 nom*, +0x10 nom complet*, +0x18 u32 ordre dans le groupe
STR_HASH, STR_CHARS, STR_REF, STR_INLINE = 0x20, 0x28, 0x30, 0x38   # enregistrement de chaine internee
FN_HAS_HASH = 0x495A70     # (sss, u32 crc) -> bool   (310 sites)
FN_HAS_PATH = 0x760A30     # (sss, SceneStateName*) -> bool
FN_HAS = 0x33DFA0          # SceneStateSystem.has
FN_SET = 0x354B20          # SceneStateSystem.set
FN_INSERT = 0x356800       # insertion (exclusivite du groupe + qXXX_DONE automatique)
FN_RESET = 0x34F8E0        # SceneStateSystem.reset
FN_CLEAR = 0x321DC0        # SceneStateSystem.clear
FN_CLEAR_GROUP = 0x321DF0  # SceneStateSystem.clearGroup
FN_FORWARD = 0x328380      # forward_scene_state (etat suivant du groupe)
FN_AFTER_SET = 0x3F1C60    # apres chaque set : mise a jour du tableau d'etat des quetes
FN_STATUS_CODE = 0x3F5D30  # suffixe d'etat -> code (CLR 1, DONE 2, END 3, FIN 4, RUN_n 100+n, FAIL_n 200+n)
FN_STATUS_GET = 0x3F5EC0   # (indice) -> code ; lu par le menu Quetes 0x8FB710
FN_QUEST_CATEGORY = 0x3F5EE0
FN_DONE_IS_FINAL = 0x3F24E0
FN_INTERN = 0x150E70       # (table 0xF8C4E0, crc, chars, len) -> enregistrement de chaine
FN_CRC = 0x28ECC0          # crc32 (zlib) ; 0x28EE00 = strlen + crc, 0x28EE30 = (ptr, len)
FN_PATH_CTOR = 0x354980    # SceneStateName(chaine) : coupe au premier '/'

SAVE_BLOCK, SAVE_SIZE = 0x145C2D0, 0x399C0   # bloc de l'emplacement de sauvegarde en memoire (fichier = +0xC)
SAVE_HAP_TEXT, SAVE_HAP_SIZE = 0x145C340, 0x30000   # document texte hap (ecrit seulement a la sauvegarde)
FN_SAVE_SERIALIZE = 0x9CC290
QUEST_TABLE, QUEST_REC, QUEST_N = 0xC4D820, 0x34, 0x44   # table exe des quetes
SUBQUEST_TABLE, SUBQUEST_REC, SUBQUEST_N = 0xC4E5F0, 0x14, 0x1C
QUEST_STATUS = 0x14946D0   # i32[66] (indice < 0x42)
QUEST_STATUS_HI = 0x149483C  # + indice*4 pour indice >= 0x42 (q085 -> 0x1494944, q095 -> 0x1494948)
QUEST_SPLIT = 0x42
SUBQUEST_STATUS = 0x14948D0  # i32[28]

AP_BITS = 0x14957E0        # u32[2], bit n = dword[n>>5] & (0x80000000 >> (n&31))
FN_AP_BIT_INDEX, FN_AP_TEST, FN_AP_SET = 0x7E43C0, 0x7F82D0, 0x818040
CLEAR_FLAGS = 0x14957D8    # u32[2], meme convention de bits ; fins F..Z = bits 9..29
FN_FLAG_SET, FN_FLAG_TEST, FN_FLAG_CLEAR = 0x9CBD90, 0x9CAE50, 0x9CBD60
SYSTEM_FLAGS = 0x1495E20   # drapeaux globaux (hors emplacement) : bits 0/1/2 = A/B/C-D termines
FN_PF30_ENDING = 0x85FF90  # sous-phase 'Ending_X' -> [this+0x144] indice de bit, [this+0x148] indice de titre
FN_ENDING_MASK = 0x9CD320  # masque de fins du resume de sauvegarde
PLAYER_OBJ = 0x11E1F84     # u32 : 0x10000 = 2B, 0x10100 = A2, 0x10200 = 9S
FN_PLAYER_SELECT = 0x7C7B00
PHASE = 0xF64AA0           # {u32 phase (0x100 = p100), u32 key_hash(sous-phase), char nom[0x20]}

STATUS_CODES = {"CLR": 1, "DONE": 2, "END": 3, "FIN": 4}
SCRIPT_FNS = ("set_scene_state", "forward_scene_state", "reset_scene_state", "getReWard")


def state_hash(name: str) -> int:
    """Hachage d'un etat = crc32 (zlib, polynome 0xEDB88320) du nom COMPLET ('q170/DONE'), casse conservee,
    sans masque. (Different de mcd key_hash : pas de minuscules, pas de & 0x7fffffff.)"""
    return zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF


def split_state(name: str):
    """(groupe, nom) comme 0x354980 : coupe au PREMIER '/' ; sans '/', groupe vide."""
    g, sep, n = name.partition("/")
    return (g, n) if sep else ("", name)


# --------------------------------------------------------------------------------- desassemblage
def dis(a, b=None, n=None):
    if b is None:
        f = func_of(a)
        b = f[1] if f else a + 0x400
    out = []
    for i in MD.disasm(D[rva2off(a):rva2off(b)], a):
        out.append(i)
        if n and len(out) >= n:
            break
    return out


def rip_target(ins):
    m = re.search(r"rip ([+-]) 0x([0-9a-f]+)", ins.op_str)
    if m:
        return ins.address + ins.size + int(m.group(2), 16) * (1 if m.group(1) == "+" else -1)


def cstr(rva, n=96):
    o = rva2off(rva)
    if o is None:
        return None
    s = D[o:D.index(b"\0", o)]
    if 1 <= len(s) < n and all(32 <= c < 127 for c in s):
        return s.decode()


def has(fn_ins, mnem, op=None, target=None):
    for i in fn_ins:
        if i.mnemonic == mnem and (op is None or i.op_str == op) and (target is None or rip_target(i) == target):
            return True
    return False


def verify_exe():
    """Controle des faits utilises (leve AssertionError si l'exe n'est pas la v1.04 analysee)."""
    ev = []

    def ok(cond, text):
        assert cond, text
        ev.append(text)

    # test par chemin : tableau [sss+0x98], compte [sss+0xa0], entrees 0x20, cle = [[entree+0x10]+0x20]
    f = dis(FN_HAS_PATH)
    ok(has(f, "mov", "r8, qword ptr [rcx + 0xa0]") and has(f, "mov", "r9, qword ptr [rcx + 0x98]")
       and has(f, "shl", "rbp, 5") and has(f, "mov", "rdx, qword ptr [rax + r9 + 0x10]")
       and has(f, "mov", "edx, dword ptr [rdx + 0x20]") and has(f, "cmp", "edx, dword ptr [r10 + 0x20]"),
       "0x760A30 : recherche dichotomique dans [sss+0x98] (n = [sss+0xa0], pas 0x20), cle u32 [[e+0x10]+0x20]")
    f = dis(FN_HAS_HASH)
    ok(has(f, "mov", "r10d, edx") and has(f, "cmp", "edx, r10d") and has(f, "shl", "rdi, 5"),
       "0x495A70 : meme recherche avec le crc en edx")
    # chaine internee : +0x20 crc, +0x28 chars (= rec+0x38), +0x30 compteur
    f = dis(FN_INTERN)
    ok(has(f, "mov", "dword ptr [rsi + 0x20], ebp") and has(f, "mov", "qword ptr [rsi + 0x28], rdi")
       and has(f, "lea", "rdi, [rsi + 0x38]") and has(f, "mov", "qword ptr [rsi + 0x30], 1"),
       "0x150E70 : chaine internee {+0x20 crc32, +0x28 char*, +0x30 refs, +0x38 caracteres}")
    f = dis(FN_PATH_CTOR)
    ok(has(f, "mov", "dl, 0x2f") and any(i.mnemonic == "call" and i.op_str == hex(FN_CRC + 0x170) for i in f),
       "0x354980 : coupe au '/' (strchr 0x28F080), hachage 0x28EE30 -> crc32 0x28ECC0")
    f = dis(0x28EE30, 0x28EE3C)
    ok(f[1].mnemonic == "jne" and f[1].op_str == hex(FN_CRC), "0x28EE30 -> 0x28ECC0 (crc32, table 0xD81190)")
    t = struct.unpack_from("<4I", D, rva2off(0xD81190))
    ok(t == (0, 0x77073096, 0xEE0E612C, 0x990951BA), "0xD81190 = table crc32 zlib standard")
    # set : exclusivite du groupe et qXXX_DONE
    f = dis(FN_INSERT)
    ok(any(i.mnemonic == "cmp" and i.op_str == "dword ptr [rax + 0x20], 0x26b80d1f" for i in f)
       and state_hash("DONE") == 0x26B80D1F and any(cstr(rip_target(i) or 0) == "%s_DONE" for i in f)
       and any(i.mnemonic == "call" and i.op_str == hex(FN_CLEAR_GROUP) for i in f),
       "0x356800 : groupe non vide -> 0x321DF0 (retire les autres etats du groupe) ; nom == crc32('DONE') "
       "0x26B80D1F et groupe 'qXXX' -> met aussi '%s_DONE'")
    f = dis(FN_SET)
    ok(any(i.mnemonic == "call" and i.op_str == hex(FN_INSERT) for i in f)
       and any(i.mnemonic == "call" and i.op_str == hex(FN_AFTER_SET) for i in f),
       "0x354B20 (set) -> 0x356800 puis 0x3F1C60")
    # liaisons des commandes hap
    for init, name, fn in ((0xB2160, "SceneStateSystem.has", FN_HAS), (0xB21E0, "SceneStateSystem.set", FN_SET),
                           (0xB2260, "SceneStateSystem.reset", FN_RESET),
                           (0xB22E0, "SceneStateSystem.clear", FN_CLEAR),
                           (0xB2360, "SceneStateSystem.clearGroup", FN_CLEAR_GROUP)):
        f = dis(init, n=12)
        ok(any(rip_target(i) == fn for i in f) and any(cstr(rip_target(i) or 0) == name for i in f),
           f"{name} -> {fn:#x}")
    # code d'etat de quete et tableaux
    f = dis(FN_STATUS_CODE)
    strs = [s for s in (cstr(rip_target(i) or 0) for i in f if i.mnemonic == "lea") if s]
    ok(strs[:6] == ["CLR", "DONE", "END", "FIN", "RUN_", "FAIL_"]
       and has(f, "mov", "dword ptr [rsi], 1") and has(f, "mov", "dword ptr [rsi], 2")
       and has(f, "mov", "dword ptr [rsi], 3") and has(f, "mov", "dword ptr [r14], 0x64")
       and has(f, "mov", "dword ptr [r14], 0xc8"),
       "0x3F5D30 : CLR 1, DONE 2, END 3, FIN 4, RUN_n 100+n, FAIL_n 200+n, sinon -1")
    f = dis(FN_STATUS_GET, 0x3F5EDF)
    ok(rip_target(f[2]) == SAVE_BLOCK and f[4].op_str == "eax, dword ptr [rcx + rax*4 + 0x38400]"
       and f[6].op_str == "eax, dword ptr [rcx + rax*4 + 0x3856c]" and f[1].op_str == "ecx, -0x42"
       and SAVE_BLOCK + 0x38400 == QUEST_STATUS and SAVE_BLOCK + 0x3856C == QUEST_STATUS_HI,
       "0x3F5EC0 : etat = i32 [0x145C2D0 + 0x38400 + 4*i] (i < 0x42) sinon [0x145C2D0 + 0x3856C + 4*i]")
    blob = D[rva2off(FN_AFTER_SET):rva2off(func_of(FN_AFTER_SET)[1])]
    ok(all(struct.pack("<I", a) in blob for a in (QUEST_STATUS, QUEST_STATUS_HI, SUBQUEST_STATUS)),
       "0x3F1C60 ecrit 0x14946D0 / 0x149483C / 0x14948D0 (seul ecrivain avec l'initialisation 0x9C4C90 = -1)")
    ok(any(i.mnemonic == "call" and i.op_str == hex(FN_STATUS_GET) for i in dis(0x8FB710)),
       "menu Quetes 0x8FB710 lit l'etat par 0x3F5EC0")
    # bloc de sauvegarde
    f = dis(0x9C3A20)
    ok(any(i.mnemonic == "mov" and i.op_str == "r8d, 0x399c0" for i in f)
       and any(rip_target(i) == SAVE_BLOCK for i in f) and any(rip_target(i) == SAVE_HAP_TEXT for i in f)
       and any(i.op_str == "r8d, 0x30000" for i in f),
       "0x9C3A20 : bloc d'emplacement 0x145C2D0 (0x399C0 o), texte hap 0x145C340 (0x30000 o)")
    f = dis(FN_SAVE_SERIALIZE)
    sec = {"Scene", "Values", "SceneState", "version", "Flags"}
    imm = {int(i.op_str.split(", ")[1], 16) for i in f if i.mnemonic == "cmp" and i.op_str.startswith("eax, 0x")}
    ok({state_hash(s) for s in sec} <= imm,
       "0x9CC290 (serialisation) compare les sections par crc32 : " +
       ", ".join(f"{s}={state_hash(s):#010x}" for s in sorted(sec)))
    # bits
    for fn, base, txt in ((FN_AP_TEST, AP_BITS, "0x7F82D0 teste"), (FN_AP_SET, AP_BITS, "0x818040 met"),
                          (FN_FLAG_SET, CLEAR_FLAGS, "0x9CBD90 met"), (FN_FLAG_TEST, CLEAR_FLAGS, "0x9CAE50 teste")):
        f = dis(fn, fn + 0xB0)
        ok(any(rip_target(i) == base for i in f) and any("0x80000000" in i.op_str for i in f)
           and any(i.mnemonic == "shr" and i.op_str.endswith(", cl") for i in f),
           f"{txt} le bit n de {base:#x} : dword[n>>5] & (0x80000000 >> (n&31))")
    f = dis(FN_PLAYER_SELECT)
    ok(all(any(i.op_str.endswith(v) for i in f) for v in ("0x10100", "0x10200", "0x10000"))
       and any(rip_target(i) == PLAYER_OBJ and i.mnemonic == "mov" for i in f),
       "0x7C7B00 ecrit [0x11E1F84] = 0x10000 / 0x10100 / 0x10200 selon les etats PL/*")
    return ev


def hardcoded_hashes(names_by_hash):
    """`mov edx, imm32` juste avant `call 0x495A70` : hachages d'etat codes en dur dans l'exe."""
    out = []
    for kind, a in refs(FN_HAS_HASH):
        if kind != "call":
            continue
        best = None
        for st in range(40, 4, -1):
            ins = list(MD.disasm(D[rva2off(a - st):rva2off(a)], a - st))
            if ins and ins[-1].address + ins[-1].size == a:
                for i in ins[-4:]:
                    if i.mnemonic == "mov" and i.op_str.startswith("edx, 0x"):
                        best = (i.address, int(i.op_str.split(", ")[1], 16))
                if best:
                    break
        if best:
            out.append({"mov_rva": f"{best[0]:#x}", "hash": f"{best[1]:#010x}", "state": names_by_hash.get(best[1])})
    return out


# ---------------------------------------------------------------------------------------- donnees
K_NAME, K_ENTRY, K_VALUE, K_LABEL, K_ARGS = 0x0389B783, 0x22B35429, None, 0x0EA750E8, 0x161B2EA2


def registry():
    """core/corehap.dat:core_hap.pak, arbres 'SceneState' : liste ordonnee [(table, nom)]."""
    trees = cpk.pak_yax(cpk.dat_files(er.game_file("core/corehap.dat"))["core_hap.pak"])
    out = []
    for t in trees:
        if not any(tag == 0x5E237E06 and v == "SceneState" for ind, tag, v in t[:6]):
            continue
        table = None
        for k, (ind, tag, v) in enumerate(t):
            if v.startswith("Scene_State_"):
                table = v
            if tag == K_ENTRY and k + 1 < len(t) and t[k + 1][1] == K_NAME and t[k + 1][0] == ind + 1:
                out.append((table, t[k + 1][2]))
    return out


def exe_quest_table():
    o = rva2off(QUEST_TABLE)
    rows = []
    for i in range(QUEST_N):
        rec = D[o + i * QUEST_REC:o + (i + 1) * QUEST_REC]
        qid = struct.unpack_from("<I", rec, 0)[0]
        name = rec[4:9].split(b"\0")[0].decode()
        npc = rec[9:0x1C].split(b"\0")[0].decode()
        f = struct.unpack_from("<6I", rec, 0x1C)
        rows.append(dict(index=i, quest=qid, name=name, npc=npc, skipped=bool(f[5]), dlc=bool(f[4]), raw=list(f)))
    sub = []
    o = rva2off(SUBQUEST_TABLE)
    for i in range(SUBQUEST_N):
        rec = D[o + i * SUBQUEST_REC:o + (i + 1) * SUBQUEST_REC]
        sub.append(dict(index=i, name=rec[:12].split(b"\0")[0].decode(), quest=struct.unpack_from("<I", rec, 12)[0],
                        a=rec[16], b=rec[17]))
    return rows, sub


def scan_scripts():
    toc = er._toc_index()
    found = []
    for name in sorted(toc):
        if not name.startswith(rq.SCRIPT_DIRS) or not name.endswith(".dat"):
            continue
        if int(toc[name][1]["ExtractSize"]) > rq.MAX_DAT:
            continue
        files = cpk.dat_files(er.game_file(name))
        for member, data in files.items():
            if member.endswith("_scp.bin"):
                try:
                    root = mruby.parse(data)
                except Exception:  # noqa: BLE001
                    continue
                mn = rq.method_names(root)
                for fn in SCRIPT_FNS:
                    for r, k, a, c, args in mruby.calls(root, fn):
                        arg = args[0] if args and isinstance(args[0], str) else None
                        found.append(dict(src="script", file=name, member=member, method=mn.get(id(r)),
                                          irep=r.offset, k=k, call=fn, arg=arg))
            elif member.endswith(".pak"):
                try:
                    trees = cpk.pak_yax(data)
                except Exception:  # noqa: BLE001
                    continue
                for t in trees:
                    for i, (ind, tag, val) in enumerate(t):
                        if tag == K_LABEL and val in ("SceneStateSystem.set", "SceneStateSystem.reset",
                                                      "SceneStateSystem.clearGroup"):
                            arg = next((t[j][2] for j in range(i + 1, min(i + 5, len(t))) if t[j][1] == K_ARGS),
                                       None)
                            found.append(dict(src="hap", file=name, member=member, call=val, arg=arg))
        del files
    return found


def coregm_tables():
    gm = cpk.dat_files(er.game_file("core/coregm.dat"))
    msg = {}
    tree, _ = bxm.parse(gm["MsgQueInfo.bxm"])
    for qn in tree["children"]:
        qid, states = None, []
        for c in qn["children"]:
            if c["name"] == "QuestId":
                qid = int(c["value"])
            elif c["children"]:
                d = {x["name"]: x["value"] for x in c["children"]}
                states.append((int(d["State"]), d["StateId"]))
        msg[qid] = states
    mails = []
    tree, _ = bxm.parse(gm["MailTable.bxm"])
    for m in tree["children"]:
        d = {c["name"]: c["value"] for c in m["children"]}
        if d.get("StateBefore") or d.get("StateAfter"):
            mails.append(d)
    return msg, mails


def pf30_endings():
    """0x85FF90 : 'Ending_X' -> (indice de bit dans 0x14957D8, indice de titre CREDIT_END_TITLE_%02d - 1)."""
    out, cur = {}, None
    for i in dis(FN_PF30_ENDING):
        s = cstr(rip_target(i) or 0) if i.mnemonic == "lea" else None
        if s and s.startswith("Ending_"):
            cur = s[-1]
        m = re.match(r"dword ptr \[rbx \+ 0x(144|148)\], (\w+)", i.op_str)
        if m and i.mnemonic == "mov" and cur:
            out.setdefault(cur, {})["bit" if m.group(1) == "144" else "title_index"] = int(m.group(2), 0)
    return out


# ------------------------------------------------------------------------------------------ quetes
def build_quests(reg, calls, msg, mails, qtable):
    quests_json = json.loads((ROOT / "docs/research/quests.json").read_text("utf-8"))["quests"]
    rewards_json = json.loads((ROOT / "docs/research/quest_rewards.json").read_text("utf-8"))["quests"]
    reg_names = [n for _, n in reg]
    reg_set = set(reg_names)
    by_group = defaultdict(list)
    for n in reg_names:
        g, s = split_state(n)
        if g:
            by_group[g].append(n)
    setters = defaultdict(list)
    for c in calls:
        if c["arg"] and c["call"] in ("set_scene_state", "forward_scene_state", "SceneStateSystem.set"):
            where = f'{c["file"]}:{c["method"]}' if c["src"] == "script" else f'{c["file"]}:{c["member"]} (hap)'
            if where not in setters[c["arg"]]:
                setters[c["arg"]].append(where)
    for m in mails:
        if m.get("StateAfter"):
            setters[m["StateAfter"]].append(f'MailTable mail {m["MailNo"]} lu (StateBefore {m.get("StateBefore")})')
    idx = {r["quest"]: r for r in qtable if not r["skipped"]}
    named = sorted(q for q, v in quests_json.items() if v.get("english_name"))
    ids = sorted(set(named) | {r["name"] for r in qtable})
    out = {}
    for q in ids:
        num = int(q[1:])
        group = by_group.get(q, [])
        e = {"id": num, "english_name": quests_json.get(q, {}).get("english_name")}
        row = idx.get(num)
        if row:
            i = row["index"]
            e["status_index"] = i
            e["status_rva"] = f"{(QUEST_STATUS if i < QUEST_SPLIT else QUEST_STATUS_HI) + 4 * i:#x}"
        else:
            e["status_index"] = None
            e["status_rva"] = None
            skipped = next((r for r in qtable if r["quest"] == num), None)
            e["status_note"] = ("presente dans la table exe mais ignoree (champ +0x30 != 0) : pas de suivi"
                                if skipped else "absente de la table exe 0xC4D820 : pas de tableau d'etat")
        e["listed_in_quest_menu"] = row is not None
        e["group_states"] = group
        e["sticky_states"] = [n for n in reg_names if re.fullmatch(q + r"_(DONE|FIN|END_\d+)", n)]
        codes = msg.get(num)
        e["msg_que_codes"] = sorted({c for c, _ in codes}) if codes is not None else None
        # recompense principale (quest_rewards.json) et etat pose juste apres dans la meme methode
        rw = rewards_json.get(q) or {}
        main_ids = rw.get("main_reward_ids") or []
        reward_states, reward_how = [], []
        for c in calls:
            if c["src"] != "script" or c["call"] != "getReWard" or not c["arg"] or not c["arg"].isdigit():
                continue
            if int(c["arg"]) not in main_ids:
                continue
            owned = any(int(c["arg"]) == r["reward_id"] and c["file"] in r["files"] and c["method"] in r["called_from"]
                        for r in rw.get("rewards", []))
            if not owned:
                continue
            same = [x for x in calls if x["src"] == "script" and x["file"] == c["file"] and x["member"] == c["member"]
                    and x["irep"] == c["irep"] and x["call"] in ("set_scene_state", "forward_scene_state")
                    and x["arg"] and x["arg"].startswith(q + "/")]
            after = sorted((x for x in same if x["k"] > c["k"]), key=lambda x: x["k"])
            before = sorted((x for x in same if x["k"] < c["k"]), key=lambda x: -x["k"])
            pick = after[0] if after else before[0] if before else None
            how = f'getReWard("{c["arg"]}") dans {c["file"]}:{c["method"]}'
            if pick:
                how += f' ; {pick["call"]}("{pick["arg"]}") {"apres" if after else "avant"} dans la meme methode'
                if pick["arg"] not in reward_states:
                    reward_states.append(pick["arg"])
            if how not in reward_how:
                reward_how.append(how)
        for m in mails:
            if m.get("QuestId") and m["QuestId"].lstrip("-").isdigit() and int(m["QuestId"]) == num \
                    and m.get("Attachment") not in (None, "-1"):
                reward_how.append(f'piece jointe {m["Attachment"]} du mail {m["MailNo"]} '
                                  f'({m.get("StateBefore")} -> {m.get("StateAfter")})')
                if m.get("StateAfter") and m["StateAfter"] not in reward_states:
                    reward_states.append(m["StateAfter"])
        e["reward"] = {"main_reward_ids": main_ids, "evidence": reward_how, "state_set_with_reward": reward_states}
        # classement de l'exe (0x3F5EE0 / 0x3F24E0)
        fin_registered = f"{q}/FIN" in reg_set
        has_end = codes is not None and any(c == 3 for c, _ in codes)
        has_fin = codes is not None and any(c == 4 and s == "-1" for c, s in codes)
        done_final = (codes is None) or (not fin_registered) or (num != 0x20 and not has_end and not has_fin)
        present = {s: f"{q}/{s}" in reg_set for s in STATUS_CODES}
        menu_complete = [v for s, v in STATUS_CODES.items() if present[s] and (
            s == "FIN" or (s in ("DONE", "END") and done_final))]
        e["exe_menu"] = {"done_is_final": done_final, "complete_status_values": sorted(menu_complete),
                         "rule": "0x3F5EE0 : FIN -> termine ; DONE/END -> termine seulement si 0x3F24E0 (pas d'etat "
                                 "qXXX/FIN declare, ou ni END ni FIN dans MsgQueInfo ; q032 jamais)"}
        # etat de fin retenu
        done, fin = f"{q}/DONE", f"{q}/FIN"
        comp, conf, why = None, "high", ""
        if done in reg_set and setters.get(done):
            comp = done
            why = "qXXX/DONE declare et pose par : " + " | ".join(setters[done][:3])
        elif done in reg_set:
            comp, conf = done, "medium"
            why = ("qXXX/DONE declare ; aucun appel direct trouve dans les fichiers parcourus (pose par un script "
                   "hors quest/ph/st, un nom construit, ou l'exe)")
            later_set = [n for n in group if split_state(n)[1] in ("END", "FIN") and setters.get(n)]
            if later_set:
                why += " ; seul etat terminal dont le poseur est trouve : " + ", ".join(
                    f"{n} ({setters[n][0]})" for n in later_set)
        elif reward_states:
            comp, conf = reward_states[0], "medium"
            why = "pas de qXXX/DONE declare : etat pose avec la recompense"
            if comp not in reg_set:
                conf = "none"
                why += (" ; ATTENTION : etat absent du registre, 0x356800 refuse de le poser (quete hors table exe : "
                        "contenu coupe)")
        elif group:
            last = [n for n in group if split_state(n)[1] in STATUS_CODES]
            comp, conf = (last[-1] if last else None), "low"
            why = "dernier etat terminal declare du groupe"
        if comp:
            suffix = split_state(comp)[1]
            later = [n for n in group if split_state(n)[1] in STATUS_CODES
                     and STATUS_CODES[split_state(n)[1]] > STATUS_CODES.get(suffix, 0)]
            sticky = f"{q}_DONE" if suffix == "DONE" and f"{q}_DONE" in reg_set else None
            if reward_states and comp not in reward_states and suffix in STATUS_CODES:
                rs = split_state(reward_states[0])[1]
                why += f" ; recompense posee avec {reward_states[0]}"
                if STATUS_CODES.get(rs, 99) < STATUS_CODES[suffix]:
                    why += " (AVANT l'etat de fin)"
            vals = sorted({STATUS_CODES[suffix]} | {STATUS_CODES[split_state(n)[1]] for n in later}) \
                if suffix in STATUS_CODES else []
            e["completion"] = {
                "state": comp, "hash": f"{state_hash(comp):#010x}", "registered": comp in reg_set,
                "status_value": STATUS_CODES.get(suffix),
                "done_or_later_status_values": vals,
                "later_states": [{"state": n, "hash": f"{state_hash(n):#010x}",
                                  "set_by": setters.get(n, [])[:3]} for n in later],
                "sticky_state": sticky, "sticky_hash": f"{state_hash(sticky):#010x}" if sticky else None,
                "sticky_note": ("mis par l'exe (0x356800) en meme temps que qXXX/DONE ; sans groupe, donc jamais "
                                "remplace par un autre etat du groupe" if sticky else None),
                "confidence": conf, "evidence": why}
        else:
            e["completion"] = None
        e["fail_states"] = [n for n in group if split_state(n)[1].startswith("FAIL_")]
        e["break_state"] = f"{q}/BREAK" if f"{q}/BREAK" in reg_set else None
        out[q] = e
    return out


# ------------------------------------------------------------------------------------------ lecteur
def read_scene_states(read, base):
    """Lecteur de reference. `read(adresse, n) -> bytes`, `base` = base du module.
    Renvoie {crc32: nom} des etats actifs (1 lecture du tableau + 1 par etat ; mettre en cache par pointeur :
    les enregistrements de chaines des etats declares restent vivants tant que le registre existe)."""
    ptr, cnt = struct.unpack("<QQ", read(base + SSS_ACT_PTR, 16))
    if not ptr or cnt > 0x1000:
        return {}
    raw = read(ptr, cnt * ENTRY_SIZE)
    out = {}
    for i in range(cnt):
        rec = struct.unpack_from("<Q", raw, i * ENTRY_SIZE + 0x10)[0]
        if not rec:
            continue
        b = read(rec + STR_HASH, 0x18 + 64)
        h = struct.unpack_from("<I", b, 0)[0]
        out[h] = b[0x18:].split(b"\0")[0].decode("ascii", "replace")
    return out


def read_quest_status(read, base):
    """{indice de la table exe: code} (-1 jamais suivi, 100+n RUN_n, 200+n FAIL_n, 1 CLR, 2 DONE, 3 END, 4 FIN)."""
    a = struct.unpack(f"<{QUEST_SPLIT}i", read(base + QUEST_STATUS, 4 * QUEST_SPLIT))
    b = struct.unpack("<2i", read(base + QUEST_STATUS_HI + 4 * QUEST_SPLIT, 8))
    return dict(enumerate(a + b))


def bit(words, n):
    return bool(words[n >> 5] & (0x80000000 >> (n & 31)))


def check_snapshot(path, doc):
    """Photo memoire de tools/memdiff.py (RVA 0xF00000..) ou fichier SlotData : controle hors ligne."""
    b = Path(path).read_bytes()
    if len(b) == SAVE_SIZE + 0xC:
        def g(rva, n):
            o = rva - SAVE_BLOCK + 0xC
            return b[o:o + n]
        kind = "SlotData"
    else:
        def g(rva, n):
            return b[rva - 0xF00000:rva - 0xF00000 + n]
        kind = "photo memoire"
    res = {"kind": kind}
    text = g(SAVE_HAP_TEXT, SAVE_HAP_SIZE).split(b"\0")[0].decode("latin1")
    lines = text.split("\n")
    states = []
    if "SceneState" in lines:
        for ln in lines[lines.index("SceneState") + 1:]:
            if not ln.startswith(" "):
                break
            states.append(ln.strip())
    known = {n for n in doc["scene_states"]["registry"]}
    res["saved_scene_states"] = states
    res["saved_states_all_registered"] = all(s in known for s in states)
    hs = [state_hash(s) for s in states]
    res["saved_states_sorted_by_crc32"] = hs == sorted(hs)
    st = struct.unpack(f"<{QUEST_SPLIT}i", g(QUEST_STATUS, 4 * QUEST_SPLIT))
    res["quest_status_not_default"] = {i: v for i, v in enumerate(st) if v != -1}
    ap = struct.unpack("<2I", g(AP_BITS, 8))
    res["ap_bits_set"] = [n for n in range(64) if bit(ap, n)]
    cf = struct.unpack("<2I", g(CLEAR_FLAGS, 8))
    res["clear_flags_set"] = [n for n in range(64) if bit(cf, n)]
    if kind != "SlotData":
        q = struct.unpack("<4Q", g(SSS + 0x60, 32)), struct.unpack("<4Q", g(SSS + 0x90, 32))
        res["registry_count_in_memory"] = q[0][2]
        res["active_count_in_memory"] = q[1][2]
        res["player_obj"] = hex(struct.unpack("<I", g(PLAYER_OBJ, 4))[0])
    return res


# -------------------------------------------------------------------------------------------- main
def build():
    evidence = verify_exe()
    reg = registry()
    reg_names = [n for _, n in reg]
    names_by_hash = {state_hash(n): n for n in reg_names}
    assert len(names_by_hash) == len(set(reg_names)), "collision de crc32 dans le registre"
    hard = hardcoded_hashes(names_by_hash)
    assert len(hard) >= 3 and all(h["state"] for h in hard), "hachage en dur non retrouve dans le registre"
    # indice dans le groupe = rang parmi les etats du meme groupe (ordre de declaration)
    order, registry_out = defaultdict(int), {}
    for table, n in reg:
        g, s = split_state(n)
        if n in registry_out:
            continue
        registry_out[n] = {"hash": f"{state_hash(n):#010x}", "group": g or None, "table": table,
                           "rank_in_group": order[g] if g else None}
        if g:
            order[g] += 1
    qtable, subq = exe_quest_table()
    calls = scan_scripts()
    msg, mails = coregm_tables()
    quests = build_quests(reg, calls, msg, mails, qtable)
    import resolve_static as rs
    full, bit_of, _partial = rs.resolve_access_points()
    aps = []
    for i, (_, code) in enumerate(full):
        if not code.startswith("ft_"):
            continue
        n = bit_of.get(code)
        aps.append({"code": code, "text_key": f"CORE_MAP_TRANS_{i + 1:04d}", "bit": n,
                    "dword_rva": f"{AP_BITS + 4 * (n >> 5):#x}" if n is not None else None,
                    "mask_u32_le": f"{0x80000000 >> (n & 31):#010x}" if n is not None else None,
                    "always_active": code == "ft_BK"})
    pf30 = pf30_endings()
    endings = {}
    for k, (letter, st) in enumerate(zip("ABCDE", ("ending_A", "ending_B", "ending_C", "ending_D", "ending_CD"))):
        endings[letter] = {"scene_state": st, "scene_state_hash": f"{state_hash(st):#010x}",
                           "flag_bit": k if k < 4 else None, "summary_mask": f"{1 << k:#x}"}
    endings["C"]["flag_note"] = endings["D"]["flag_note"] = (
        "bits 2/3 = generique C/D termine (0x85C160 : 3 si Route/D, etat jamais pose ; sinon 2) : utiliser "
        "l'etat ending_C / ending_D (0x863730 : select/9S -> ending_C, select/A2 -> ending_D)")
    endings["E"]["flag_note"] = "pas de bit : etat ending_CD pose en 0x85E636 ; le bit 8 n'est ecrit nulle part"
    for letter, v in sorted(pf30.items()):
        if "bit" in v:
            endings[letter] = {"scene_state": None, "flag_bit": v["bit"],
                               "flag_mask_u32_le": f"{0x80000000 >> v['bit']:#010x}",
                               "title_key": f"CREDIT_END_TITLE_{v['title_index'] + 1:02d}",
                               "summary_mask": f"{1 << (v['bit'] - 3):#x}"}

    def st(n):
        return {"state": n, "hash": f"{state_hash(n):#010x}"}

    return {
        "_source": "tools/runtime_state.py (analyse statique exe v1.04 + data ; aucune lecture du processus)",
        "image_base": "0x140000000",
        "hash": {
            "algorithm": "crc32 zlib (poly 0xEDB88320, init/xorout 0xFFFFFFFF) du nom complet ASCII, casse "
                         "conservee, 32 bits sans masque",
            "function_rva": f"{FN_CRC:#x}", "table_rva": "0xd81190",
            "verified_exe_constants": [
                {"string": "DONE", "hash": f"{state_hash('DONE'):#010x}", "rva": "0x356884",
                 "insn": "cmp dword ptr [rax+0x20], 0x26b80d1f"},
                {"string": "SceneState", "hash": f"{state_hash('SceneState'):#010x}", "rva": "0x9cc3f3",
                 "insn": "cmp eax, 0x6b8ce530 (section du document de sauvegarde)"},
                {"string": "Flags", "hash": f"{state_hash('Flags'):#010x}", "rva": "0x9cc405"},
                {"string": "Scene", "hash": f"{state_hash('Scene'):#010x}", "rva": "0x9cc3e5"},
            ],
            "verified_state_immediates": hard,
        },
        "scene_states": {
            "system_rva": f"{SSS:#x}",
            "active": {"ptr_rva": f"{SSS_ACT_PTR:#x}", "count_rva": f"{SSS_ACT_CNT:#x}",
                       "capacity_rva": f"{SSS + 0xA8:#x}", "sorted_by": "crc32 du nom complet, croissant",
                       "change_signature": "0x35CC40 : crc32 de la liste des hachages actifs (0x400 premiers) "
                                           "recalcule a chaque changement"},
            "registry_array": {"ptr_rva": f"{SSS_REG_PTR:#x}", "count_rva": f"{SSS_REG_CNT:#x}",
                               "expected_count": len(registry_out)},
            "entry": {"size": ENTRY_SIZE, "group_str_ptr": 0, "name_str_ptr": 8, "full_str_ptr": 0x10,
                      "rank_u32": 0x18},
            "interned_string": {"hash_u32": STR_HASH, "chars_ptr": STR_CHARS, "refcount_u64": STR_REF,
                                "inline_chars": STR_INLINE},
            "functions": {"has_by_hash": f"{FN_HAS_HASH:#x}", "has_by_path": f"{FN_HAS_PATH:#x}",
                          "has": f"{FN_HAS:#x}", "set": f"{FN_SET:#x}", "insert": f"{FN_INSERT:#x}",
                          "reset": f"{FN_RESET:#x}", "clear": f"{FN_CLEAR:#x}",
                          "clearGroup": f"{FN_CLEAR_GROUP:#x}", "forward": f"{FN_FORWARD:#x}",
                          "after_set_hook": f"{FN_AFTER_SET:#x}",
                          "mruby": {"scene_state?": "0x333be0", "set_scene_state": "0x335510",
                                    "reset_scene_state": "0x333820", "clear_scene_state": "0x329b40",
                                    "forward_scene_state": "0x32cdf0"}},
            "save": {"slot_block_rva": f"{SAVE_BLOCK:#x}", "slot_block_size": SAVE_SIZE,
                     "file_offset_delta": 0xC, "hap_text_rva": f"{SAVE_HAP_TEXT:#x}",
                     "hap_text_size": SAVE_HAP_SIZE, "hap_text_file_offset": 0x7C,
                     "format": "texte : sections 'Scene', 'SceneState', 'Flags' ; une ligne ' <nom>' par etat actif",
                     "live": False},
            "registry": registry_out,
        },
        "quest_status": {
            "array_rva": f"{QUEST_STATUS:#x}", "count": QUEST_SPLIT, "type": "i32",
            "high_rule": f"indice >= {QUEST_SPLIT} : {QUEST_STATUS_HI:#x} + 4*indice",
            "save_block_offset": f"{QUEST_STATUS - SAVE_BLOCK:#x}",
            "save_file_offset": f"{QUEST_STATUS - SAVE_BLOCK + 0xC:#x}",
            "values": {"-1": "jamais suivie (REQ/BREAK ne changent pas la valeur)", "1": "CLR", "2": "DONE",
                       "3": "END", "4": "FIN", "100+n": "RUN_n", "200+n": "FAIL_n"},
            "subquest_array_rva": f"{SUBQUEST_STATUS:#x}", "subquest_count": SUBQUEST_N,
            "exe_table": [{k: r[k] for k in ("index", "quest", "name", "npc", "skipped", "dlc")} for r in qtable],
            "exe_subquests": subq,
        },
        "quests": quests,
        "access_points": {"bits_rva": f"{AP_BITS:#x}", "save_file_offset": f"{AP_BITS - SAVE_BLOCK + 0xC:#x}",
                          "rule": "bit n : u32le[n>>5] & (0x80000000 >> (n&31))",
                          "other_bits": {"12": "pas un point d'acces : mis par la methode mruby visible_rm "
                                               "(0x33A610 -> 0x818080(12, 1))"},
                          "codes": aps},
        "endings": {"flags_rva": f"{CLEAR_FLAGS:#x}", "save_file_offset": f"{CLEAR_FLAGS - SAVE_BLOCK + 0xC:#x}",
                    "rule": "bit n : u32le[n>>5] & (0x80000000 >> (n&31))",
                    "system_flags_rva": f"{SYSTEM_FLAGS:#x}",
                    "slot_file_patch_fn": "0x9c9b80 (pose le bit dans la copie [0x1422290]+0x39508 et ecrit le "
                                          "fichier de l'emplacement : fins F..Z, 0x862EE0)",
                    "other_bits": {"4": "pose en 0x863BFE (sequence post-generique 0x8639E0 ; sens non trace)",
                                   "5": "pose en 0x863B55 (meme sequence)",
                                   "6": "pose en 0x86366B avant le message CORE_MAP_VOICECNG_01",
                                   "7": "pose en 0x950FE8 (interface)", "8": "jamais ecrit (emplacement de E)",
                                   "30": "pose en 0x864034 avant CREDIT_DIALOG_TRSHOP_0",
                                   "31": "pose en 0x99D1DE (interface)",
                                   "32": "pose par 0x7C7B00 quand le personnage selectionne est A2",
                                   "33": "pose en 0x855413"},
                    "letters": endings},
        "route_character": {
            "route_states": [st(f"Route/{c}") for c in "ABCD"],
            "route_note": "groupe 'Route' exclusif : au plus un etat actif ; Route/D n'est jamais pose (v1.04)",
            "player_states": [st(n) for n in reg_names if n.startswith("PL/")],
            "player_obj_rva": f"{PLAYER_OBJ:#x}",
            "player_obj_values": {"0x10000": "2B (pl0000)", "0x10100": "A2 (pl0100)", "0x10200": "9S (pl0200)"},
            "player_select_fn": f"{FN_PLAYER_SELECT:#x}",
            "phase": {"rva": f"{PHASE:#x}", "phase_u32": 0, "subphase_hash_u32": 4, "subphase_name_char32": 8,
                      "subphase_hash": "crc32(nom en minuscules) & 0x7fffffff (0x14C5B0)",
                      "evidence": "0x863AE4 copie {phase, hachage, nom[0x20]} vers 0xF64B18 ; photos memoire : "
                                  "p100 / '00_85_A_RobotM_Pro_2ndArea' / 0x24c4b954"},
        },
        "exe_evidence": evidence,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/research"))
    ap.add_argument("--save", help="fichier SlotData_N.dat a controler (lecture seule)")
    ap.add_argument("--snap", help="photo memoire tools/snaps/x.bin a controler")
    a = ap.parse_args()
    doc = build()
    out = Path(a.out) / "runtime_state.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
    q = doc["quests"]
    print(f"{out} : {len(doc['scene_states']['registry'])} etats, {len(q)} quetes "
          f"({sum(1 for v in q.values() if v['status_index'] is not None)} suivies par le tableau), "
          f"{len(doc['hash']['verified_state_immediates'])} hachages en dur verifies, "
          f"{len(doc['exe_evidence'])} controles exe")
    for p in (a.save, a.snap):
        if p:
            print(json.dumps(check_snapshot(p, doc), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
