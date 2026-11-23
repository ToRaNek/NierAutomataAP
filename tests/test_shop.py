import struct

from nier_automata.game import mcd_text, shop


# --- textes MCD ------------------------------------------------------------------------------

SYM = [(36, ord(c), i) for i, c in enumerate("APItemaudio2'?")] + [(1, ord("Z"), 99)]


def test_encode_pairs_letters_space_end():
    out = mcd_text.encode_pairs("AP Item", SYM, 36)
    idx = {chr(c): i for i, (f, c, g) in enumerate(SYM)}
    assert out == [idx["A"], 0, idx["P"], 0, 0x8001, mcd_text.SPACE_KERNING,
                   idx["I"], 0, idx["t"], 0, idx["e"], 0, idx["m"], 0, 0x8000]


def test_encode_pairs_accent_fallback_and_unknown():
    # 'é' absent -> 'e' ; 'Z' n'existe que dans une autre police -> '?'
    out = mcd_text.encode_pairs("éZ", SYM, 36)
    idx = {chr(c): i for i, (f, c, g) in enumerate(SYM)}
    assert out == [idx["e"], 0, idx["?"], 0, 0x8000]


def test_wrap_respects_width_and_lines():
    assert mcd_text.wrap("Pour Niicotine : Grappin (progression)", 20, 3) == [
        "Pour Niicotine :", "Grappin", "(progression)"]
    assert len(mcd_text.wrap("a " * 100, 10, 2)) == 2


# --- table des magasins (BXM) ------------------------------------------------------------------

def make_bxm(shops):
    """BXM minimal : ShopInfo > shop > Item > item > State_0..1 (valeurs '0'/'1')."""
    strings = bytearray()
    so = {}

    def s(t):
        if t is None:
            return 0xFFFF
        if t not in so:
            so[t] = len(strings); strings.extend(t.encode() + b"\0")
        return so[t]

    data, pairs = [], {}

    def d(name, value=None):
        key = (name, value)
        if key not in pairs:
            pairs[key] = len(data); data.append((s(name), s(value)))
        return pairs[key]

    # arbre en largeur : noeuds = (childCount, firstChild, attrCount, dataIndex)
    tree = ("ShopInfo", None, [(sh, None, [("Item", None, [(it, None, [(f"State_{k}", v, []) for k, v in enumerate(st)])
                                                          for it, st in items])])
                               for sh, items in shops])
    nodes, queue = [], [tree]
    nodes.append(None)
    order = [(tree, 0)]
    i = 0
    while i < len(order):
        (name, value, kids), idx = order[i]
        first = len(nodes)
        for kid in kids:
            nodes.append(None); order.append((kid, first + kids.index(kid)))
        nodes[idx] = (len(kids), first, 0, d(name, value))
        i += 1
    head = b"BXM\0" + b"\0" * 4 + struct.pack(">HHI", len(nodes), len(data), len(strings))
    body = b"".join(struct.pack(">HHHH", *n) for n in nodes) + b"".join(struct.pack(">HH", *x) for x in data)
    return head + body + bytes(strings)


def items_of(raw, shop_name):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
    import bxm
    root, _ = bxm.parse(raw)
    sh = [c for c in root["children"] if c["name"] == shop_name][0]
    return [(i["name"], "".join(x["value"] for x in i["children"])) for i in sh["children"][0]["children"]]


SHOPS = [("shop_RC_Grocery", [("item_rec_S", "11"), ("item_stUp_pAtk_S", "11"), ("item_stUp_pAtk_M", "01"),
                              ("item_feed_S", "11"), ("item_uq_music_2", "01")]),
         ("shop_PV_Grocery", [("item_rec_S", "11"), ("item_rec_M", "11")])]
CARRIERS = ["item_uq_music_2", "item_uq_music_3"]


def apply(raw, writes):
    b = bytearray(raw)
    for off, val in writes:
        struct.pack_into(">H", b, off, val)
    return bytes(b)


def test_plan_puts_carriers_first_and_always_on():
    raw = make_bxm(SHOPS + [("shop_X", [("item_uq_music_3", "00")])])
    writes = shop.plan(raw, {"shop_RC_Grocery": CARRIERS[:2]})
    got = items_of(apply(raw, writes), "shop_RC_Grocery")
    assert got[:2] == [("item_uq_music_2", "11"), ("item_uq_music_3", "11")]
    # victimes : d'abord l'objet porteur deja present, puis un bonus de stats ; le reste garde son ordre
    assert got[2:] == [("item_rec_S", "11"), ("item_stUp_pAtk_S", "11"), ("item_feed_S", "11")]
    assert items_of(apply(raw, writes), "shop_PV_Grocery") == SHOPS[1][1]  # autres magasins intacts


def test_plan_zero_slots_is_identity():
    raw = make_bxm(SHOPS + [("shop_X", [("item_uq_music_3", "11")])])
    assert apply(raw, shop.plan(raw, {"shop_RC_Grocery": []})) == raw


def test_plan_does_not_touch_shared_data_entries():
    raw = make_bxm(SHOPS + [("shop_X", [("item_uq_music_3", "11")])])
    patched = apply(raw, shop.plan(raw, {"shop_RC_Grocery": CARRIERS[:2], "shop_PV_Grocery": CARRIERS[1:2]}))
    nn, dn, _ = struct.unpack(">HHI", raw[8:16])
    data_area = slice(16 + nn * 8, 16 + nn * 8 + dn * 4)
    assert patched[data_area] == raw[data_area]


def test_identify_shop_by_displayed_items():
    sets = {"RC": {0, 1, 100, 101, 921}, "RC_small": {0, 1, 921}, "PV": {0, 1, 2, 50}}
    assert shop.identify([931, 0, 1, 100], sets, carriers={931, 932}) == "RC"
    assert shop.identify([931, 0, 1, 921], sets, carriers={931, 932}) == "RC_small"
    assert shop.identify([931, 2, 50], sets, carriers={931}) == "PV"
    assert shop.identify([931, 777], sets, carriers={931}) is None


def test_shop_text_for_content():
    assert shop.description(1, 2, "Grappin", "Niicotine", progression=True) == "Pour Niicotine : Grappin (progression)"
    assert shop.description(1, 1, "Phoenix Sword", "ToRaNek", progression=False) == "Pour toi : Phoenix Sword"
    assert shop.description(1, None, None, None, False) == "Objet Archipelago"


def test_reserve_names_reuses_test_shop_strings_only():
    shops = SHOPS + [("shop_TEST_Grocery", [("item_test_only_long_name", "1"), ("item_rec_S", "1")])]
    raw = make_bxm(shops)
    carriers = ["item_uq_hairSpray_A"]
    patched = apply_bytes(raw, shop.reserve_names(raw, carriers))
    assert ("item_uq_hairSpray_A", "1") in items_of(patched, "shop_TEST_Grocery")
    assert items_of(patched, "shop_RC_Grocery") == SHOPS[0][1]       # vrais magasins intacts
    writes = shop.plan(patched, {"shop_PV_Grocery": carriers[:1]})
    assert items_of(apply(patched, writes), "shop_PV_Grocery")[0] == ("item_uq_hairSpray_A", "11")


def test_reserve_names_never_touches_real_shop_names():
    raw = make_bxm(SHOPS + [("shop_TEST_Grocery", [("item_rec_S", "1")])])
    assert shop.reserve_names(raw, ["item_uq_hairSpray_A"]) == []   # aucun nom reutilisable : rien


def apply_bytes(raw, patches):
    b = bytearray(raw)
    for off, data in patches:
        b[off:off + len(data)] = data
    return bytes(b)


def test_key_hash_matches_game():
    assert mcd_text.key_hash("CORE_ITEM_NAME_931") == 0x11F3487D
    assert mcd_text.key_hash("CORE_ITEM_NAME_922") == 0x11E12886


def test_encode_pairs_case_fallback():
    sym = [(36, ord(c), i) for i, c in enumerate("niIcot?")]
    idx = {chr(c): i for i, (f, c, g) in enumerate(sym)}
    out = mcd_text.encode_pairs("Ni", sym, 36)          # 'N' absent -> 'n' ; 'i' present
    assert out == [idx["n"], 0, idx["i"], 0, 0x8000]
    out = mcd_text.encode_pairs("W", sym, 36)           # W absent, w absent -> ?
    assert out == [idx["?"], 0, 0x8000]


def test_active_slots_skip_checked():
    loc = {("RC", 1): 11, ("RC", 2): 12, ("RC", 3): 13}
    assert shop.active_slots("RC", 3, {12}, lambda p, k: loc[(p, k)]) == [1, 3]
    assert shop.active_slots("RC", 0, set(), lambda p, k: loc[(p, k)]) == []


def test_carrier_map_follows_active_slots():
    assert shop.carrier_map([1, 3], [880, 881, 882]) == {880: 1, 881: 3}


def test_glyph_plan_borrows_missing_into_spare_symbols():
    sym = [(36, ord(c), i) for i, c in enumerate("ab[]?")] + [(5, ord("N"), 9)]
    donor = [(36, ord(c), 100 + i) for i, c in enumerate("abNO")]
    plan = mcd_text.glyph_plan(sym, donor, 36, "NOx", spare="[]")
    assert plan == [(2, "N", 102), (3, "O", 103)]   # x absent du donneur : ignore


def test_identify_ignores_unknown_ids_like_chips():
    sets = {"RC": {0, 1, 100, 101, 921}, "RC_small": {0, 1, 921}, "PV": {0, 1, 2, 50}}
    assert shop.identify([880, 3335, 3336, 100, 0], sets, carriers={880}) == "RC"


def test_no_image_cave_skips_carriers_only():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    base, cave = 0x140000000, 0x13F000000
    code = shop.no_image_cave(cave, base, 950, 953)
    ins = [(i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, cave)]
    assert ins[0] == ("test", "eax, eax")
    assert ("cmp", "esi, 0x3b6") in ins and ("cmp", "esi, 0x3b9") in ins
    targets = {int(op, 16) for m, op in ins if m == "jmp"}
    assert targets == {base + shop.SHOW_IMAGE_RVA, base + shop.SKIP_IMAGE_RVA}


def test_thumb_cave_swaps_carrier_thumbnail_only():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    base, cave = 0x140000000, 0x13F000000
    code = shop.thumb_cave(cave, base, 950, 953, 4)
    ins = [(i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, cave)]
    assert ("cmp", "ebx, 0x3b6") in ins and ("cmp", "ebx, 0x3b9") in ins
    assert ("mov", "r9d, 4") in ins and ("mov", "edx, 0xf") in ins
    assert ins[-1] == ("jmp", hex(base + shop.THUMB_RETURN_RVA))


def test_assign_carriers_one_per_slot_skipping_owned():
    slots = [("Resistance Camp", 1), ("Resistance Camp", 2), ("Pascal's Village", 1)]
    pool = [950, 951, 952, 953]
    got = shop.assign_carriers(slots, pool, owned={951})
    assert got == {950: ("Resistance Camp", 1), 952: ("Resistance Camp", 2), 953: ("Pascal's Village", 1)}
    assert shop.assign_carriers(slots, [950], owned=set()) == {950: ("Resistance Camp", 1)}  # pas assez : le reste saute


def test_purchase_needs_recent_payment():
    w = shop.PaymentWatch(window=10.0)
    w.update(1000, now=0.0)
    w.update(1000, now=1.0)
    assert not w.paid(300, now=1.0)            # pas de baisse : pas d'achat
    w.update(700, now=2.0)
    assert w.paid(300, now=3.0)                # -300 G il y a 1 s : achat
    assert not w.paid(300, now=20.0)           # trop ancien
    w.update(5000, now=21.0)                   # gain (objet recu) : rien
    assert not w.paid(300, now=21.5)


def test_payment_consumed_once():
    w = shop.PaymentWatch(window=10.0)
    w.update(1000, now=0.0); w.update(700, now=1.0)
    assert w.consume(300, now=1.5) and not w.consume(300, now=2.0)
