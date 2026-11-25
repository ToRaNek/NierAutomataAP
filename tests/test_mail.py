import struct

from nier_automata.game import mail


def entry(no, sender=b"servermanager"):
    e = bytearray(mail.ENTRY)
    struct.pack_into("<i", e, 0, no)
    e[mail.SENDER_OFFSET:mail.SENDER_OFFSET + 16] = sender.ljust(16, b"\0")
    return bytes(e)


def test_insert_entry_sorted_with_sender():
    ents = [entry(1), entry(30), entry(35)]
    out = mail.insert_entry(ents, ents[0], 31, "Archipelago")
    assert [struct.unpack_from("<i", e, 0)[0] for e in out] == [1, 30, 31, 35]
    assert out[2][mail.SENDER_OFFSET:mail.SENDER_OFFSET + 11] == b"Archipelago"
    assert mail.insert_entry(out, ents[0], 31, "X") == out          # deja present : inchange


def test_sender_id_is_safe_ascii():
    assert mail.sender_id("Niicotine") == "Niicotine"
    assert mail.sender_id("Fifi la-Brindille éé!") == "Fifi_la_Brindil"  # 15 car. max, [A-Za-z0-9_]
    assert mail.sender_id("") == "Archipelago"


def test_insert_name_sorted_by_hash():
    ents = [(0x10, 1), (0x30, 3)]
    assert mail.insert_name(ents, 0x20, 2) == [(0x10, 1), (0x20, 2), (0x30, 3)]
    assert mail.insert_name(ents, 0x10, 9) == ents                    # deja present


def test_box_entry_unread_and_time():
    raw = struct.pack("<iIII", 31, 0xC0000000, 0xA0013, 0xFFFFFFFF)
    new = mail.unread_entry(raw, hour=20, minute=5)
    no, flags, t, x = struct.unpack("<iIII", new)
    assert (no, flags, t, x) == (31, 0, (5 << 16) | 20, 0xFFFFFFFF)


def test_checks_body_groups_and_counts():
    body = mail.checks_body(["Story: Camp Resistance", "Chest #1", "Story: Desert", "Level 5"], total=10)
    assert body.startswith("Checks restants : 4 / 10")
    assert "Story: Camp Resistance" in body and "Level 5" in body


def test_hints_body_latest_first():
    hints = [("Grappin", "Niicotine", "AP Item: Desert #1"), ("Epee", "Fifi", "Chest #3")]
    body = mail.hints_body(hints)
    assert body.index("Epee") < body.index("Grappin")
    assert "Grappin pour Niicotine\n  -> AP Item: Desert #1" in body


def _dis(code, at):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    return [(i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, at)]


def test_title_cave_view_swaps_hash_for_our_mails():
    base, cave = 0x140000000, 0x13F000000
    code = mail.title_cave_view(cave, base, {31: 0x1111, 32: 0x2222})
    ins = _dis(code, cave)
    assert ("cmp", "r14d, 0x1f") in ins and ("mov", "eax, 0x1111") in ins
    assert ("cmp", "r14d, 0x20") in ins and ("mov", "eax, 0x2222") in ins
    assert ("mov", "ebp, eax") in ins and ("mov", "rbx, qword ptr [r15 + 0x230]") in ins
    assert ins[-1] == ("jmp", hex(base + mail.VIEW_RETURN_RVA))


def test_title_cave_list_swaps_hash_for_our_mails():
    base, cave = 0x140000000, 0x13F000000
    ins = _dis(mail.title_cave_list(cave, base, {31: 0x1111}), cave)
    assert ins[0] == ("mov", "edx, dword ptr [r14]")
    assert ("cmp", "edx, 0x1f") in ins and ("mov", "eax, 0x1111") in ins and ("mov", "ebp, eax") in ins
    assert ins[-1] == ("jmp", hex(base + mail.LIST_RETURN_RVA))


def test_checks_mail_starts_with_a_count_per_kind():
    # avis du testeur : le jeu ne dit nulle part combien de coffres / objets il reste -> il faut un suivi
    from nier_automata.game.mail import checks_body
    body = checks_body(["Chest: City Ruins #1", "Chest: City Ruins #2", "AP Item: Desert Zone #1",
                        "Story A 02-01: Landing at the City Ruins", "Level 4", "Quest: Lost Girl"], 20, lang="en")
    lines = body.split("\n")
    assert lines[0] == "Remaining checks: 6 / 20"
    assert lines[1] == "Chest 2 | AP Item 1 | Story 1 | Quest 1 | Level 1"
    assert "- Chest: City Ruins #1" in lines
