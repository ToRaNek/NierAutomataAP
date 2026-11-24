"""Peche : table de poissons par zone et correspondance etfXXX -> objet fish_NN (analyse statique, lecture seule).

Relancer : `python tools/logic_gaps_fishing.py [--out fichier.json]` ; `run()` renvoie le dict (utilise par
tools/logic_gaps.py). Faible RAM : exe (17 Mo) + un .dat a la fois via le cache d'extract_research.

Preuves (RVA, base 0x140000000) :
- 0x81e180 charge `FishParam.csv` (0xce6bd8) dans le gestionnaire global 0x1251668 ; 0x7fa460 = analyseur :
  texte mis en majuscules, ligne commencant par '/' ou ',' ignoree, `indice (0..0x1d), ETFxxxx (hexa), poids
  (min 1)`, 30 entrees max par table ; table i : ids a +0xa8+i*0xf8, poids a +0x120+i*0xf8, nombre a +0x198+i*0xf8.
- 0x642ee0(peche, a, b) : [+0x3ec0] = a, [+0x3ec8] = b ; appele en 0x4b5191 avec a = [zone+0x59c], b = [zone+0x590].
- 0x6c2177 : [+0x3ecc] = 0x7e0a10(gestionnaire, position du flotteur) = [+0x590] du premier objet bga105 de la liste
  +0x90 dont le cercle (rayon^2 = (sx^2+sz^2)*k, [obj+0x70]/[obj+0x78]) contient le flotteur, sinon -1.
- 0x645130 (BehaviorFishingArea, vtable 0xc80028) : objId 0xca104 (bga104) -> liste +0x58 (0x7c9380),
  0xca105 (bga105) -> liste +0x90 (0x7cba60).
- 0x853b60 / 0x84d5df : [obj+0x590] = setInfo+0x70, [+0x594] = +0x74, [+0x59c] = +0x78 ; l'analyseur de layout
  0x3e96c0 lit setType, setRtn, setFlag dans cet ordre (+0x4c/+0x50/+0x54) -> +0x590 = setType (DEDUIT, coherent :
  valeurs de setType bga104 = 0..8 = tables remplies 0..8, bga105 setType 10 -> table 20).
- 0x59bf30 : 0x7e0b20(gestionnaire, [+0x3ec8], [+0x3ecc]) : si b >= 0 table b+10 (et si b+10 < 20 aussi la table a),
  sinon table a ; etf040 ignore si bit 0x400000 de [0x14948a0], etf042 ignore si bit 0x200000 ; tirage pondere
  (somme cumulee, LCG 0x19660d/0x3c6ef35f) ; table de sauts 0x59c3f0 : code CSV -> objId 0x4f0xx ; cas etf040 :
  objId 0x4f040 + (objId du joueur == 0x10200).
- 0x6c3a51 : table de sauts 0x6c4354 (objId - 0x4f000) -> indice ; 0x628e10(this, indice) : bit 'deja peche'
  [0x149489c] ; indice 41 -> Pod B (chaines own_podB / GET_POD_B) ; 42 -> objet 0x3f5 (1013 weapon_pipe = Iron Pipe) ;
  sinon addItem(0x1f41 + indice) = fish_(indice+1) (0x6290ed).
"""
import argparse, json, struct, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone  # noqa: E402
import xref  # noqa: E402
import extract_research as er  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRATCH_DEFAULT = None
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)

FISH_FILES = ["core/corehap.dat", "st1/r100.dat", "st1/r130.dat", "st1/r150.dat", "st1/r160.dat", "st1/r170.dat",
              "st2/r200.dat", "st5/r502.dat"]
AREA_IDS = ("bga104", "bga105")

# Traductions NON officielles des noms japonais (haps / groupes)
JP_EN = [("釣りエリア", "Fishing area"), ("釣りポイント", "Fishing point"), ("谷底", "valley bottom"),
         ("都市", "city"), ("森", "forest"), ("水道管", "water pipe"), ("オアシス", "oasis"), ("油田", "oil field"),
         ("海", "sea"), ("川", "river"), ("浅瀬", "shallows")]
GROUP_EN = {"谷底": "valley bottom (City Ruins ravine)", "ショッピングモール側": "shopping mall side",
            "森の段々川上流": "forest terraced river, upstream", "レジキャン側": "Resistance Camp side",
            "遊園地への水道管": "water pipe towards the Amusement Park", "砂漠のオアシス": "desert oasis",
            "砂漠の油田": "desert oil field", "森の城前の渓谷": "ravine in front of the Forest Castle",
            "水没都市への水道管": "water pipe towards the Flooded City",
            "エイリアンシップへの洞窟": "cave towards the alien ship", "陥没都市の中段": "middle level of the crater city",
            "エミールの住処への水道管": "water pipe towards Emil's home"}
ROOM_EN = {"r100": "City Ruins", "r130": "Amusement Park", "r150": "Desert", "r160": "Forest", "r170": "Flooded City",
           "r200": "City Ruins (crater/underground)", "r502": "hidden cave (r502)", "r100/r200": "City Ruins (r100/r200)"}


def tr(jp: str) -> str:
    s = jp
    for a, b in JP_EN:
        s = s.replace(a, b + " ")
    return " ".join(s.replace("_", " ").replace("（", "(").replace("）", ")").split()).replace(" )", ")")


# ----------------------------------------------------------------------------------------------- exe

def _ins(rva, n=0x20):
    o = xref.rva2off(rva)
    return list(MD.disasm(xref.D[o:o + n], xref.IMG + rva))


def jump_table(table_rva, count):
    o = xref.rva2off(table_rva)
    return [struct.unpack_from("<I", xref.D, o + 4 * i)[0] for i in range(count)]


def exe_maps():
    """etf objId -> indice de poisson (0x6c4354) et code CSV -> objId (0x59c3f0), lus dans l'exe."""
    checks = {}
    # verification des sites clefs (la version de l'exe doit etre 1.04)
    i = _ins(0x6c3a57, 8)[0]
    checks["0x6c3a57"] = f"{i.mnemonic} {i.op_str}"
    i = _ins(0x6290ed, 8)[0]
    checks["0x6290ed"] = f"{i.mnemonic} {i.op_str}"
    i = _ins(0x629045, 8)[0]
    checks["0x629045"] = f"{i.mnemonic} {i.op_str}"
    ok = ("0xfffb1000" in checks["0x6c3a57"] and "0x1f41" in checks["0x6290ed"] and "0x3f5" in checks["0x629045"])
    # objId -> indice : xor edx,edx = 0 ; mov edx,r14d = 1 (r14d = 1 en 0x6c196b) ; mov edx,N ; defaut 0x6c3bef
    obj_to_idx = {}
    for k, tgt in enumerate(jump_table(0x6c4354, 0x43)):
        ins = _ins(tgt, 8)[0]
        val = None
        if tgt == 0x6c3bef:
            val = None
        elif ins.mnemonic == "xor" and ins.op_str == "edx, edx":
            val = 0
        elif ins.mnemonic == "mov" and ins.op_str == "edx, r14d":
            val = 1
        elif ins.mnemonic == "mov" and ins.op_str.startswith("edx, "):
            val = int(ins.op_str.split(", ")[1], 16)
        if val is not None:
            obj_to_idx[0x4f000 + k] = val
    # code CSV (0xf000 + k) -> objId
    code_to_obj = {}
    for k, tgt in enumerate(jump_table(0x59c3f0, 0x43)):
        ins = _ins(tgt, 8)[0]
        if tgt == 0x59c1f7:
            code_to_obj[0xf000 + k] = "0x4f000 (defaut, edi initial)"
        elif tgt == 0x59c1a7:
            code_to_obj[0xf000 + k] = "0x4f040 ou 0x4f041 (0x4f041 si objId du joueur == 0x10200)"
        elif ins.mnemonic == "mov" and ins.op_str.startswith("edi, "):
            code_to_obj[0xf000 + k] = ins.op_str.split(", ")[1]
    return ok, checks, obj_to_idx, code_to_obj


# ----------------------------------------------------------------------------------------------- donnees

def fish_tables():
    """FishParam.csv avec les regles de 0x7fa460."""
    raw = er.dat_member("core/core.dat", "FishParam.csv").decode("shift_jis", "replace")
    tables, ignored = defaultdict(list), []
    for line in raw.upper().splitlines():
        if not line or line[0] in "/,":
            if line.strip(","):
                ignored.append(line)
            continue
        p = line.split(",")
        if not p[0].isdigit() or int(p[0]) > 0x1d or len(p) < 3 or not p[1].startswith("ET"):
            continue
        w = int(p[2]) if p[2].isdigit() else 0
        if len(tables[int(p[0])]) < 30:
            tables[int(p[0])].append(("etf" + p[1][3:].lower(), int(p[1][2:], 16), max(w, 1)))
    return dict(tables), ignored


def area_entities():
    import world_positions as wp  # import tardif (lourd)
    import cpk
    vocab = wp.Vocab()
    out = []
    for name in FISH_FILES:
        d = wp.members(name)
        for k, v in d.items():
            if not k.endswith(".pak"):  # *_hap.pak et *_grp.pak = donnees d'execution (les hap.z sont perimes)
                continue
            try:
                trees = cpk.pak_yax(v)
            except Exception:  # noqa: BLE001
                continue
            for t in trees:
                h = wp.yax_to_elem(t, vocab)
                for act in h.findall("action"):
                    vals = []
                    wp.walk_values(act, None, vals)
                    for bucket, val in vals:
                        if wp.txt(val, "objId") in AREA_IDS:
                            e = wp.entity_of(val, bucket)
                            e.update(file=name, member=k, hap=wp.txt(h, "name"), hap_id=wp.txt(h, "id"))
                            out.append(e)
        del d
    return out


def run() -> dict:
    ok, checks, obj_to_idx, code_to_obj = exe_maps()
    tables, ignored = fish_tables()
    texts = er.english_texts()
    items = json.loads((ROOT / "docs/research/items.json").read_text(encoding="utf-8"))
    by_uid = {x["UniqueID"]: x for x in items["items"]}

    def fish_item(etf_code):
        obj = 0x40000 | etf_code
        idx = obj_to_idx.get(obj)
        if idx is None:
            return {"fish_index": None, "item_id": None, "name": None}
        if idx == 41:
            return {"fish_index": 41, "item_id": None, "internal_name": "own_podB", "name": "Pod B",
                    "note": "0x628e10 : indice 0x29 -> chaines own_podB / GET_POD_B (obtention du Pod B), une fois"}
        if idx == 42:
            return {"fish_index": 42, "item_id": 1013, "internal_name": "weapon_pipe",
                    "name": texts.get("CORE_WP_NAME_1013", (None,))[0],
                    "note": "0x629045 : indice 0x2a -> objet 0x3f5 (arme 1013), une fois"}
        uid = 8001 + idx
        it = by_uid.get(uid, {})
        return {"fish_index": idx, "item_id": uid, "internal_name": it.get("internal_name"),
                "name": texts.get("CORE_FISH_%02d" % (idx + 1), (None,))[0],
                "help": texts.get("CORE_FISH_HELP_%02d" % (idx + 1), (None,))[0],
                "sell_price": (it.get("prices") or {}).get("State_0", {}).get("Sell")}

    etf_map = {}
    for obj, idx in sorted(obj_to_idx.items()):
        etf = "etf%03x" % (obj & 0xfff)
        etf_map[etf] = dict(objId=hex(obj), **fish_item(obj & 0xffff))

    def table_view(t):
        rows = tables.get(t, [])
        tot_all = sum(w for _e, _c, w in rows)
        tot_after = sum(w for e, _c, w in rows if e not in ("etf040", "etf042"))
        out = []
        for e, c, w in rows:
            r = {"etf": e, "weight": w, "pct_first": round(100 * w / tot_all, 2) if tot_all else None,
                 "pct_after_unique": (round(100 * w / tot_after, 2) if tot_after and e not in ("etf040", "etf042")
                                      else 0.0)}
            r.update(fish_item(c))
            if e == "etf040":
                r["objId_variants"] = "0x4f040 / 0x4f041 selon le personnage (0x59c1dc)"
            out.append(r)
        return {"table": t, "entries": out, "total_weight": tot_all}

    # zones
    ents = area_entities()
    wpj = json.loads((ROOT / "docs/research/world_positions.json").read_text(encoding="utf-8"))
    cond = {(a["file"], a["hap"]): a.get("conditions") for a in wpj["fishing"]["areas"]}
    del wpj
    groups = defaultdict(list)
    for e in ents:
        groups[(e["file"], e["hap"], e["objId"])].append(e)
    zones = []
    for (f, h, oid), es in sorted(groups.items()):
        room = f.split("/")[1][:-4] if f.startswith("st") else "r100/r200"
        st_counter = Counter(int(x["setType"]) if x["setType"] else 0 for x in es)
        pts = [x["position"] for x in es if x["position"]]
        c = cond.get((f, h)) or {}
        z = {"file": f, "hap": h, "hap_en": tr(h), "objId": oid, "room": room, "area_en": ROOM_EN.get(room),
             "group_chain": c.get("group_chain"),
             "group_chain_en": [GROUP_EN.get(g, g) for g in (c.get("group_chain") or [])],
             "volumes": len(es),
             "centroid": [round(sum(p[i] for p in pts) / len(pts), 2) for i in range(3)] if pts else None,
             "bbox": [[round(min(p[i] for p in pts), 1) for i in range(3)],
                      [round(max(p[i] for p in pts), 1) for i in range(3)]] if pts else None,
             "setType_counts": {str(k): v for k, v in sorted(st_counter.items())},
             "volumes_detail": [{"position": x["position"], "scale": x["scale"], "rotation": x["rotation"],
                                 "setType": int(x["setType"]) if x["setType"] else 0,
                                 "setRtn": int(x["setRtn"]) if x["setRtn"] else 0} for x in es]}
        if oid == "bga104":
            z["role"] = "zone ou le joueur peche : setType = table de base ([+0x590] -> [+0x3ec8])"
            z["tables"] = [table_view(t) for t in sorted(st_counter)]
            z["confidence"] = "high (lecture exe) / setType -> +0x590 deduit (medium-high)"
        else:
            z["role"] = ("point de peche bga105 : si le flotteur est dans le cercle, table setType+10 ; setType >= 10 "
                         "-> table setType+10 SEULE, sinon table setType+10 + table de base")
            z["tables"] = [table_view(t + 10) for t in sorted(st_counter)]
            z["confidence"] = "high (lecture exe 0x6c2177/0x7e0a10/0x7e0b20)"
        zones.append(z)

    return {
        "_source": "tools/logic_gaps_fishing.py (statique : NieRAutomata.exe v1.04 + core/core.dat:FishParam.csv + "
                   "*_hap.pak / *_grp.pak des fichiers " + ", ".join(FISH_FILES) + ")",
        "exe_signature_ok": ok, "exe_checks": checks,
        "mechanism": {
            "base_table": "[peche+0x3ec8] = setType ([+0x590]) de la zone bga104 ou le joueur peche (0x4b5191 -> "
                          "0x642ee0). confidence: high pour le flux de donnees, medium-high pour +0x590 = setType.",
            "overlay_table": "[peche+0x3ecc] = setType du premier bga105 (liste +0x90 de 0x1251668) dont le cercle "
                             "contient le flotteur (0x6c2177 -> 0x7e0a10), -1 sinon. 0x7e0b20 : b >= 0 -> table "
                             "b+10 ; si b+10 < 20 la table de base est ajoutee. confidence: high.",
            "unique_rewards": "etf040 (Pod B) exclu si bit 0x400000 de dword 0x14948a0 ; etf042 (Iron Pipe) exclu si "
                              "bit 0x200000 ; = bits 41/42 du tableau 'deja peche' 0x149489c mis par 0x628e10 "
                              "(or [rdi], esi en 0x62910e). Donc une seule fois. confidence: high.",
            "draw": "tirage pondere : probabilite = poids / somme des poids de la (des) table(s) (0x59bf87..0x59bffb).",
            "csv_rules": "0x7fa460 : ligne commencant par ',' ou '/' ignoree -> la ligne ',etf032,10,' (apres la "
                         "table 5) n'est PAS chargee ; tables 10-19 et 21-29 vides.",
            "character": "etf040 -> objId 0x4f041 si l'objId du joueur == 0x10200 (0x59c1dc) ; 0x4f041 donne "
                         "aussi l'indice 41 (Pod B). 0x10200 = pl0200 = 9S (prefixe pl = 0x1 ; hap p300/p200 : "
                         "objId pl0200 alias '9S' / 'npc_9s', pl0100 alias 'A2', pl0000 alias '2B' ; exe : "
                         "'mesh_pl0200' a cote de 'PL/9S_NoPatch'). Donc etf041 = variante 9S (meme Pod B). "
                         "confidence: high.",
            "setType_slot": "[obj+0x590] = setType du placement : copie setInfo+0x70 -> +0x590 (0x853b60, appele "
                            "par la creation d'entite 0x7453c0 en 0x74567d) ; trois consommateurs independants "
                            "confirment que c'est le setType : mort d'un ennemi 0x5f485a passe [+0x590] comme "
                            "setType a 0x825780 (compare au setType d'EmList), EmBase 0x5a74cc teste [+0x590]==10 "
                            "(lignes EMP), ascenseur Ba0200 [+0x590] = id (setType des 12 cabines coherent). "
                            "L'analyseur de layout 0x3e94d0/0x3e96c0 range setType/setRtn/setFlag en +0x4c/+0x50/"
                            "+0x54 ; la copie layout -> setInfo (decalage +0x24) n'est pas lue instruction par "
                            "instruction. Note : la mort passe [+0x598] (setInfo+0x7c) comme setFlag. "
                            "confidence: high (par les consommateurs).",
        },
        "csv_ignored_lines": ignored,
        "csv_code_to_objId": {hex(k): v for k, v in code_to_obj.items()},
        "etf_to_item": etf_map,
        "tables": {str(t): table_view(t) for t in sorted(tables)},
        "zones": zones,
        "open": ["copie instruction par instruction layout (+0x4c) -> setInfo (+0x70) non lue (setType confirme "
                 "par 3 consommateurs, voir rules.setType_slot)",
                 "role de [+0x3ec0] (= [zone+0x59c]) et de setRtn des volumes : non utilise pour le choix de table"],
        "resolved_2026_11_24": ["0x10200 = pl0200 = 9S (etf041 = variante 9S de Pod B)",
                                "[obj+0x590] = setType (consommateurs : 0x5f485a, 0x5a74cc, Ba0200)"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = run()
    out = Path(a.out) if a.out else Path(__import__("tempfile").gettempdir()) / "lg_fishing.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ecrit", out, "zones", len(res["zones"]), "etf", len(res["etf_to_item"]), "exe ok", res["exe_signature_ok"])


if __name__ == "__main__":
    main()
