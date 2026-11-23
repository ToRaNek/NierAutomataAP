"""Resolution statique (exe v1.04 + donnees) : points d'acces et programmes de Pod. LECTURE SEULE.

Usage :
    python tools/resolve_static.py [--out docs/research] [--no-hap]

- Points d'acces : lit dans NieRAutomata.exe les tables de hachages des codes ft_XX construites par les
  initialiseurs statiques, verifie le code qui en derive CORE_MAP_TRANS_%04d, le numero de bit d'activation,
  et parcourt les *_hap.z (un fichier a la fois, sans cache disque) pour lister toutes les references aux
  codes ft_XX et aux verrous globaux (WarpLock, TerminalLock, ...).
- Programmes de Pod : verifie que les 3 sites qui formatent CORE_ACT_SKILL_NAME_%02d utilisent UniqueID - 2000
  et joint avec items.json + textes anglais.
Le jeu n'est jamais lance ; rien n'est ecrit dans le dossier du jeu. Voir docs/research/data_formats.md.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capstone import CS_ARCH_X86, CS_MODE_64, Cs  # noqa: E402

import xref  # noqa: E402
from xref import D, func_of, refs, rva2off  # noqa: E402

MD = Cs(CS_ARCH_X86, CS_MODE_64)
HASH_FN = 0x28EE00  # crc32 (zlib) d'une chaine C ; verifie ci-dessous

# Adresses v1.04 (RVA)
INIT_FT_FULL = 0x109EE0     # initialiseur : 27 hachages -> tableau 0x13FD4A0 (ordre CORE_MAP_TRANS)
INIT_FT_BITS = 0x105A90     # initialiseur : 21 hachages -> tableau 0x13EC770 (ordre des bits d'activation)
CODE_TO_KEY = 0x86F0D0      # codeName -> "CORE_MAP_TRANS_%04d" (indice + 1)
NUM_TO_KEY = 0x86F250       # numero 1..27 -> cle de texte (cas speciaux 14, 23-26, 27)
CODE_TO_NUM = 0x86FD90      # codeName -> indice + 1 (ou -1)
CODE_TO_BIT = 0x7E43C0      # codeName -> numero de bit d'activation (switch, table de sauts 0x7E45F4)
IS_ACTIVE = 0x7F82D0        # ft_BK -> 1 ; sinon bit dans 0x14957E0
SET_ACTIVE = 0x818040       # met le bit
ACT_BITFIELD = 0x14957E0
TRANSPORTER_UPDATE = 0x604BD0   # comportement ba1100 (vtable 0xCA4108) : premiere activation
DEST_LIST = 0x8BC580            # liste des destinations du menu Transport (verrous globaux)
SAVE_FIXUP = 0x7623D0           # corrections forcees (ft_RC, ft_CC) selon la phase


def cstr(rva):
    o = rva2off(rva)
    if o is None:
        return None
    e = D.find(b"\0", o)
    s = D[o:e]
    if 1 <= len(s) < 96 and all(32 <= c < 127 for c in s):
        return s.decode()


def dis(a, b=None):
    if b is None:
        a, b = func_of(a)
    return list(MD.disasm(D[rva2off(a):rva2off(b)], a))


def rip_target(ins):
    m = re.search(r"rip ([+-]) 0x([0-9a-f]+)", ins.op_str)
    if m:
        return ins.address + ins.size + int(m.group(2), 16) * (1 if m.group(1) == "+" else -1)


def hash_init_table(fn):
    """Initialiseur `lea rcx,str ; call crc ; mov [g+4i],eax` -> [(adresse globale, chaine)]."""
    ins = dis(fn)
    out = [rip_target(i) for i in ins if i.mnemonic == "mov" and i.op_str.startswith("dword ptr [rip")
           and i.op_str.endswith("eax")]
    strs = [cstr(rip_target(i)) for i in ins if i.mnemonic == "lea" and i.op_str.startswith("rcx")]
    assert len(strs) == len(out), (len(strs), len(out))
    return list(zip(out, strs))


def jump_table_values(fn, table, n):
    vals = []
    for k in range(n):
        tgt = struct.unpack_from("<i", D, rva2off(table) + 4 * k)[0]
        ins = next(MD.disasm(D[rva2off(tgt):rva2off(tgt) + 8], tgt))
        if ins.mnemonic == "xor":
            vals.append(0)
        else:
            vals.append(int(ins.op_str.split(",")[1], 0))
    return vals


# --- points d'acces -----------------------------------------------------------------------------

LOCK_TOKENS = ["WarpLock", "WarpPartialLock", "TerminalLock", "Electronic_Lock", "lock_ft_PV", "UI_namePV",
               "Pascal_Terminal_txt", "BehaviorTransporterBa"]


def resolve_access_points():
    full = hash_init_table(INIT_FT_FULL)
    bits_order = hash_init_table(INIT_FT_BITS)
    # verifie que la boucle de 0x86F0D0 parcourt 0x13FD4A0 (27 entrees) et formate rbx+1
    f = dis(CODE_TO_KEY)
    tbl = [rip_target(i) for i in f if i.mnemonic == "lea" and rip_target(i) and rip_target(i) > 0x1000000]
    assert tbl and tbl[0] == full[0][0], "table 0x13FD4A0 non trouvee dans 0x86F0D0"
    assert any(i.mnemonic == "cmp" and i.op_str == "ebx, 0x1b" for i in f)
    assert any(i.mnemonic == "lea" and i.op_str == "r9d, [rbx + 1]" for i in f)
    assert any(cstr(rip_target(i) or 0) == "CORE_MAP_TRANS_%04d" for i in f)
    # numero de bit : switch sur l'ordre de bits_order, valeurs de la table de sauts 0x7E45F4
    bitvals = jump_table_values(CODE_TO_BIT, 0x7E45F4, len(bits_order))
    bit_of = {s: v for (_, s), v in zip(bits_order, bitvals)}
    pv_hash = zlib.crc32(b"ft_PV")
    assert any(i.op_str == f"eax, {hex(pv_hash)}" for i in f)  # cas special ft_PV (UI_namePV)
    partial_allowed = []
    for i in dis(DEST_LIST):
        m = re.match(r"r14d, (0x[0-9a-f]+)$", i.op_str)
        if i.mnemonic == "cmp" and m:
            partial_allowed.append(int(m.group(1), 16))
    partial_codes = [s for _, s in full if zlib.crc32(s.encode()) in partial_allowed]
    return full, bit_of, partial_codes


def scan_haps():
    """References textuelles aux codes ft_ et aux verrous dans tous les *_hap.z (+ core_hap.pak brut)."""
    import cpk
    import extract_research as er
    pat = re.compile(r"ft_[A-Za-z0-9]+(?:_[A-Z0-9]+)?|" + "|".join(LOCK_TOKENS))
    hits = []
    names = sorted(n for n in er.all_names() if re.match(r"(ph\w|quest|st\d)/[^/]+\.dat$", n))
    for n in names:
        p, row = er._toc_index()[n]
        c = er.CACHE / n.replace("/", "__")
        raw = c.read_bytes() if c.exists() else cpk.extract(p, row)
        files = cpk.dat_files(raw)
        del raw
        for k, v in files.items():
            if not k.endswith("_hap.z"):
                continue
            t = zlib.decompress(v).decode("shift_jis", "replace")
            for m in pat.finditer(t):
                tok = m.group()
                if tok.startswith("ft_") and tok not in FT_SET:
                    continue
                hs = t.rfind("<hap>", 0, m.start())
                hap = re.search(r"<name>(.*?)</name>", t[hs:hs + 400])
                a = t.rfind("<action>", 0, m.start())
                ae = t.find("</action>", m.start())
                blk = t[a:ae] if a > hs else ""
                an = re.search(r"<name>(.*?)</name>", blk)
                cm = re.search(r"<comment>(.*?)</comment>", blk)
                lb = re.findall(r"<label>(.*?)</label>", blk)
                line_s = t.rfind("\n", 0, m.start()) + 1
                line = t[line_s:t.find("\n", m.end())].strip()
                hits.append(dict(file=n, member=k, token=tok, hap=hap.group(1) if hap else None,
                                 action=an.group(1) if an else None, comment=cm.group(1) if cm else None,
                                 labels=sorted(set(lb)), line=line[:200]))
        del files
    # core_hap.pak : YAX binaire, simple recherche de chaines
    raw = er.game_file("core/corehap.dat")
    pak = cpk.dat_files(raw)["core_hap.pak"]
    for m in re.finditer(rb"(ft_[A-Za-z0-9_]+|" + "|".join(LOCK_TOKENS).encode() + rb")\x00", pak):
        tok = m.group(1).decode()
        if tok.startswith("ft_") and tok not in FT_SET:
            continue
        hits.append(dict(file="core/corehap.dat", member="core_hap.pak", token=tok, offset=m.start()))
    return hits


FT_SET: set = set()


# --- programmes de Pod --------------------------------------------------------------------------

def resolve_pod_sites():
    s = D.find(b"CORE_ACT_SKILL_NAME_%02d\0")
    srva = xref.off2rva(s)
    sites = []
    for kind, a in refs(srva):
        if kind != "lea":
            continue
        back = [i for i in dis(func_of(a)[0], a + 7) if i.address >= a - 0x40]
        sub = [i for i in back if i.mnemonic == "lea" and re.match(r"r9d, \[r[a-z0-9]+ - 0x7d0\]", i.op_str)]
        sites.append(dict(rva=hex(a), function=hex(func_of(a)[0]), index_expr=sub[-1].op_str if sub else None))
    return hex(srva), sites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "docs" / "research"))
    ap.add_argument("--no-hap", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    import extract_research as er
    texts = er.english_texts()

    def t(k):
        return texts.get(k, (None,))[0]

    # --- points d'acces
    full, bit_of, partial = resolve_access_points()
    FT_SET.update(s for _, s in full if s.startswith("ft_"))
    old = json.loads((out / "access_points.json").read_text(encoding="utf8"))
    ents = {}
    for e in old.get("terminal_entities", []):
        ents.setdefault(e["codeName"], []).append(dict(objId=e["objId"], file=e["file"], position=e["position"],
                                                       hap=e.get("hap"), action=e.get("action")))
    hap_hits = [] if args.no_hap else scan_haps()
    entries = []
    for idx, (g, code) in enumerate(full):
        num = idx + 1
        if num == 14:
            key_rule = "CORE_MAP_TRANS_0014 si la variable UI_namePV est vraie, sinon CORE_SUB_MAP_AREA_111 ('???')"
        elif 23 <= num <= 26:
            key_rule = "CORE_MAP_AREA_090 (0x86F250)"
        elif num == 27:
            key_rule = "CORE_MAP_TRANS_0021 (0x86F250)"
        else:
            key_rule = None
        key = f"CORE_MAP_TRANS_{num:04d}" if num <= 22 else ("CORE_MAP_AREA_090" if num <= 26 else
                                                               "CORE_MAP_TRANS_0021")
        bit = bit_of.get(code)
        e = dict(index=idx, number=num, code=code, crc32=hex(zlib.crc32(code.encode())), hash_slot=hex(g),
                 text_key=key, english_name=t(key), text_key_rule=key_rule,
                 is_access_point=code.startswith("ft_"),
                 activation_bit=bit,
                 activation_bit_rva=(None if bit is None else
                                     dict(word=hex(ACT_BITFIELD + 4 * (bit >> 5)), mask=hex(0x80000000 >> (bit & 31)))),
                 always_active=(code == "ft_BK"),
                 allowed_under_WarpPartialLock=(code in partial),
                 confidence="high",
                 evidence=(f"0x109EE0 stocke crc32('{code}') dans {hex(g)} = 0x13FD4A0+4*{idx} ; 0x86F0D0 cherche le "
                           f"hachage du codeName dans ce tableau (27 entrees) et formate CORE_MAP_TRANS_%04d avec "
                           f"indice+1 = {num}"),
                 placed_entities=ents.get(code, []),
                 hap_references=[h for h in hap_hits if h["token"] == code])
        if code.startswith("ft_"):
            entries.append(e)
        else:
            e["note"] = "point de reprise (non affiche comme point d'acces)"
            entries.append(e)
    special = {
        "ft_BK": "Toujours actif (0x7F82D0 retourne 1, pas de bit). p300 'バンカーセーブ禁止' : setvar ft_BK false "
                 "(route C/D). Place dans qb40 (6 ba1000).",
        "ft_RC": "0x7623D0 force enableTransporter ft_RC + bit si (phase==p100 et sous-phase >= "
                 "'40_AB_Resistance_Camp_Leader') ou phase p200/p300. p200 流れ(2) : panne 'レジキャン端末故障' puis "
                 "'レジキャン端末復旧' (true). p200 '転送端末ロック処理' et 'セーブ制御' : false. Seule destination "
                 "permise sous TerminalLock.",
        "ft_CC": "0x7623D0 force enableTransporter ft_CC + bit si la sous-phase courante == '100_A_Submerge_City_2B'. "
                 "q170 (Terminal Repairs) 流れ(7) : panne puis condition transporterIsReadyToUnlock ft_CC. p200 : false.",
        "ft_CRb": "q170 (Terminal Repairs) 流れ(8) : panne puis condition transporterIsReadyToUnlock ft_CRb. "
                  "Place seulement dans core_hap.pak.",
        "ft_CS": "q170 (Terminal Repairs) 流れ(13) : panne puis condition transporterIsReadyToUnlock ft_CS. "
                 "Place seulement dans core_hap.pak.",
        "ft_DC": "Place r150 (砂漠入口). p200 '転送端末ロック処理' : false. Point de 'メモリセーブ' de p100.",
        "ft_DI": "Place r150 (砂漠内部). p200 '転送端末ロック処理' : false.",
        "ft_AP": "Place r130 (遊園地, 飛行機遊具前). p200 : false. 0x39FCF0 (DLC q095 'Mysterious Invitation') "
                 "lit l'objet ft_AP.",
        "ft_AP_C": "Aucune reference trouvee dans les hap.z ni core_hap.pak (placement ailleurs : non trouve).",
        "ft_AP_T": "Aucune reference trouvee dans les hap.z ni core_hap.pak (placement ailleurs : non trouve).",
        "ft_AP_T2": "Aucune reference trouvee dans les hap.z ni core_hap.pak (placement ailleurs : non trouve).",
        "ft_PV": "Nom '???' (CORE_SUB_MAP_AREA_111) tant que la variable UI_namePV est fausse (0x86F0D0/0x86F250). "
                 "Grisee si lock_ft_PV (HELP_15) ou Pascal_Terminal_txt (HELP_13) (0x8BC580). p200 : false. "
                 "Placement : seulement une chaine dans core_hap.pak.",
        "ft_FC": "Place r160 (森). p200 '転送端末ロック処理' : false.",
        "ft_RME": "Place r120 (ロボット山入口). Point de 'メモリセーブ' de p200.",
        "ft_RMI": "Place r520 (ボス前). 0x2FE220 traite ft_RMI/ft_RMI2 a part.",
        "ft_RMI2": "Place r520 (開始地点). 0x2FE220 traite ft_RMI/ft_RMI2 a part.",
        "ft_SC": "Place r170. p200 流れ(2) : panne '水没都市端末故障' puis condition transporterIsEnabled ft_SC "
                 "('アクセスポイントを修復したら会話発生'). r170 'ファストトラベル条件リセット' commente "
                 "'水没都市怪獣撃破後のファストトラベル制限用'. p200 : false.",
        "ft_AS": "Place r200. p200 流れ(2) : panne 'エイリアンシップ端末故障' puis condition transporterIsEnabled "
                 "ft_AS. p200 : false.",
    }
    for e in entries:
        if e["code"] in special:
            e["unlock_notes"] = special[e["code"]]
    ap_out = dict(
        note=("Correspondance LUE dans l'exe v1.04 (pas deduite). Cle de texte = CORE_MAP_TRANS_%04d(indice+1) ou "
              "indice = position du crc32(codeName) dans le tableau 0x13FD4A0 rempli par 0x109EE0. Les entrees 23-27 "
              "(re_*) sont des points de reprise de la Tour/p200, pas des points d'acces."),
        unlock_model=dict(
            visible_in_transport_menu=("le bit d'activation est mis (0x7F82D0 ; ft_BK toujours) : mis par 0x818040 lors "
                                       "de la premiere interaction avec le terminal (comportement ba1100 0x604BD0, "
                                       "evenement 'ba1100_warp_device_first_boot') ou par 0x7623D0 pour ft_RC/ft_CC"),
            terminal_usable=("variable 'ft_XX' vraie dans la table de variables 0xF23540 (nom -> octet). Ecrite par "
                             "MiscState.setvar \"ft_XX true|false\" (gestionnaire 0x3AEBD0, meme table via 0x358540) "
                             "et FastTravel.enableTransporter (0x324CB0) ; lue par FastTravel.transporterIsEnabled "
                             "(0x3587F0 -> 0x327FF0). Fausse = terminal en panne : destination grisee avec "
                             "CORE_PM_TM_HELP_13 'Unavailable due to signal interference.' (confiance haute)"),
            first_activation=("le terminal ba1100 (0x604BD0, etat 0) appelle FastTravel.transporterIsReadyToUnlock "
                              "(0x358800) : vrai si la variable est vraie, sinon depend d'un etat de l'objet terminal "
                              "(bit 21 de [obj+0x1C] puis 0x3DF840(obj+0x140)) - vraisemblablement la condition "
                              "'ennemis du 敵発生機_ft_XX elimines' (q170 : condition transporterIsReadyToUnlock suivie "
                              "du dialogue '敵撃破会話'), NON verifie. Si faux : evenement 0x8132D7F8 (refus). Si vrai et "
                              "bit pas encore mis : evenement 'ba1100_warp_device_first_boot' puis 0x818040 (bit)."),
            unlock_notes_caveat=("unlock_notes = references directes (haute confiance sur leur existence) ; l'ordre et "
                                 "les declencheurs des actions hap ne sont pas resolus (scripts *_scp.bin non decodes)"),
            hap_actions=("chaque terminal place a une action 'ファストトラベル条件リセット' (code 0x5797C250, "
                         "parametre codeName) et souvent un generateur d'ennemis '敵発生機_ft_XX' (code 0x6F0FB5BD)"),
            global_locks={
                "WarpLock": "aucune destination (0x8BC580)",
                "Electronic_Lock": "aucune destination (0x8BC580)",
                "TerminalLock": "seule ft_RC est proposee (si sa variable est vraie)",
                "WarpPartialLock": "seules " + ", ".join(partial) + " restent selectionnables ; les autres : "
                                   "CORE_PM_TM_HELP_11 'You cannot travel outside of the mission area.'",
                "lock_ft_PV": "ft_PV grisee (CORE_PM_TM_HELP_15)",
                "Pascal_Terminal_txt": "ft_PV grisee (CORE_PM_TM_HELP_13)",
            },
            activation_bitfield=dict(rva=hex(ACT_BITFIELD), order="bit n = dword[n>>5] & (0x80000000 >> (n&31))",
                                     note="numero de bit = valeur de 0x7E43C0 (0..21, 12 inutilise ; ft_BK sans bit)"),
        ),
        functions={hex(k): v for k, v in {
            INIT_FT_FULL: "initialiseur statique : crc32 de 27 codes (22 ft_ + 5 re_*) -> 0x13FD4A0",
            INIT_FT_BITS: "initialiseur statique : crc32 de 21 codes ft_ (sans ft_BK) -> 0x13EC770",
            CODE_TO_KEY: "codeName -> cle CORE_MAP_TRANS_%04d (indice+1), cas ft_PV/UI_namePV",
            NUM_TO_KEY: "numero -> cle de texte (14: UI_namePV, 23-26: CORE_MAP_AREA_090, 27: CORE_MAP_TRANS_0021)",
            CODE_TO_NUM: "codeName -> numero 1..27 ou -1",
            CODE_TO_BIT: "codeName -> numero de bit d'activation",
            IS_ACTIVE: "terminal active ? (ft_BK toujours vrai)",
            SET_ACTIVE: "active le terminal (met le bit)",
            TRANSPORTER_UPDATE: "machine a etats du terminal ba1100 (vtable 0xCA4108)",
            DEST_LIST: "construit la liste des destinations du menu Transport",
            SAVE_FIXUP: "forcage de ft_RC / ft_CC selon la phase",
            HASH_FN: "crc32 (zlib) d'une chaine C",
        }.items()},
        access_points=entries,
        hap_lock_references=[h for h in hap_hits if not h["token"].startswith("ft_")],
    )
    (out / "access_points_resolved.json").write_text(json.dumps(ap_out, ensure_ascii=False, indent=1), encoding="utf8")

    # --- programmes de Pod
    srva, sites = resolve_pod_sites()
    assert sites and all(s["index_expr"] for s in sites), sites
    items = json.loads((out / "items.json").read_text(encoding="utf8"))["items"]
    progs = []
    for it in sorted((i for i in items if str(i["internal_name"]).startswith("skill_act_")), key=lambda i: i["UniqueID"]):
        n = it["UniqueID"] - 2000
        k = f"CORE_ACT_SKILL_NAME_{n:02d}"
        progs.append(dict(unique_id=it["UniqueID"], internal_name=it["internal_name"], text_index=n, name_key=k,
                          english_name=t(k), help_key=f"CORE_ACT_SKILL_HELP_{n:02d}",
                          english_help=t(f"CORE_ACT_SKILL_HELP_{n:02d}"), confidence="high"))
    pod_out = dict(
        note=("Cle de nom = CORE_ACT_SKILL_NAME_%02d avec UniqueID - 2000 (0x7D0). Verifie aux 3 sites qui formatent "
              "cette chaine ; 0x86E4B0 est le switch par categorie (0x86FDD0) qui donne le nom de tout objet."),
        format_string_rva=srva, sites=sites, programs=progs,
        unused_text_indices=[n for n in range(1, 25) if t(f"CORE_ACT_SKILL_NAME_{n:02d}") is None],
    )
    (out / "pod_programs.json").write_text(json.dumps(pod_out, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"{len([e for e in entries if e['is_access_point']])} points d'acces, {len(hap_hits)} references hap, "
          f"{len(progs)} programmes de Pod")


if __name__ == "__main__":
    main()
