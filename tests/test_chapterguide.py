from nier_automata.data import chapterguide as cg
from nier_automata.data import chapterlocks as cl
from nier_automata.data import worlddb as db
from nier_automata.data.gagendings import GAG_ENDINGS

ALL = len(db.CHAPTERS)
B01 = next(i for i, c in enumerate(db.CHAPTERS) if c["region"] == "B01")
B03 = next(i for i, c in enumerate(db.CHAPTERS) if c["region"] == "B03")


def rows(**kw):
    base = dict(chapters=ALL, reached=set(), received=[], route_keys={}, chapter_keys={}, missing=None,
                gag_endings=(), endings_seen=set())
    base.update(kw)
    return cg.rows(**base)


def test_every_gag_ending_has_a_place_and_a_how_to():
    assert set(cg.GAG_GUIDE) == set(GAG_ENDINGS)
    for letter, (where, how) in cg.GAG_GUIDE.items():
        assert how and len(how) < 200
        if where is not None:                                   # (route, code de chapitre) : doit exister
            assert cg.chapter_index(*where) is not None, letter
            assert db.CHAPTERS[cg.chapter_index(*where)]["route"] == GAG_ENDINGS[letter] or letter in "HLN"


def test_one_row_per_chapter_in_scope():
    r = rows(chapters=10)
    assert [x.index for x in r] == list(range(10))
    assert r[0].name == db.CHAPTERS[0]["name"] and r[0].route == "A"


def test_only_reached_and_jumpable_chapters_can_be_replayed():
    i = next(k for k in sorted(cl.STARTS))
    j = next(k for k in range(ALL) if k not in cl.STARTS)
    r = rows(reached={i, j})
    assert r[i].reached and r[i].can_go
    assert r[j].reached and not r[j].can_go                      # pas de debut de chapitre connu : pas de bouton
    other = next(k for k in sorted(cl.STARTS) if k != i)
    assert not r[other].reached and not r[other].can_go


def test_needs_lists_what_is_missing_to_open_the_chapter():
    keys = {"B": "Route B Access"}
    ckeys = dict(cl.CHAPTER_KEYS)
    r = rows(route_keys=keys, chapter_keys=ckeys)
    assert r[0].needs == []
    assert "Route B Access" in r[B01].needs
    assert any("B Chapter Key" in n and "0/2" in n for n in r[B03].needs)
    r = rows(route_keys=keys, chapter_keys=ckeys, received=["Route B Access", "B Chapter Key", "B Chapter Key"])
    assert r[B01].needs == [] and r[B03].needs == []


def test_a_locked_chapter_cannot_be_replayed_even_if_reached():
    ckeys = dict(cl.CHAPTER_KEYS)
    assert B03 in cl.STARTS
    assert not rows(reached={B03}, chapter_keys=ckeys)[B03].can_go
    assert rows(reached={B03}, chapter_keys=ckeys, received=["B Chapter Key"] * 2)[B03].can_go


def test_story_check_done_follows_missing_locations():
    name = db.CHAPTERS[5]["name"]
    assert rows(missing={name})[5].check_done is False
    assert rows(missing=set())[5].check_done is True
    assert rows(missing=None)[5].check_done is None             # pas connecte : inconnu


def test_gag_endings_are_listed_on_their_chapter_only_when_they_are_checks():
    i = cg.chapter_index(*cg.GAG_GUIDE["J"][0])
    assert rows()[i].endings == []
    r = rows(gag_endings=("J", "K"), endings_seen={"K"})
    assert [(e.letter, e.done) for e in r[i].endings] == [("J", False)]
    assert all(e.letter != "K" for x in r for e in x.endings)     # K se fait partout : pas sur un chapitre


def test_anywhere_endings():
    out = cg.anywhere(gag_endings=("K", "T", "J"), endings_seen={"T"})
    assert [(e.letter, e.done) for e in out] == [("K", False), ("T", True)]


def test_summary_line():
    r = rows(reached={0}, missing=set(), gag_endings=("W",))
    line = cg.line(r[0])
    assert "01-01" in line and "W" in line


def test_ending_start_is_the_exact_subphase_when_known():
    assert cg.ending_start("F") == ("B", "9S", 0x100, "05_30_B_RobotM_ProBoss_phase3")
    assert cg.ending_start("X") == ("C", "A2", 0x300, "50_10_CD_Ruined_City_A2Come_2B")
    assert cg.ending_start("H") == cl.STARTS[cg.chapter_index("A", "05-02")]
    assert cg.ending_start("K") is None
    for letter, sub in cg.GAG_SUBPHASE.items():
        assert cg.ending_start(letter)[3] == sub, letter


class _Names:
    def lookup_in_game(self, x):
        return x


class _Item:
    def __init__(self, name):
        self.item = name


class _Ctx:
    def __init__(self, reached, received=(), missing=(), gag=(), seen=(), ckeys=None):
        from types import SimpleNamespace as NS
        self.state = NS(chapters=set(reached), endings_seen=set(seen))
        self.scope = NS(chapters=ALL, route_keys={}, chapter_keys=ckeys or {}, gag_endings=tuple(gag))
        self.item_names = self.location_names = _Names()
        self.items_received = [_Item(n) for n in received]
        self.missing_locations, self.server_locations = set(missing), {1}
        self.area_lock = None
        self.chapter_request = None


def test_tab_entries_offer_go_only_for_open_reached_chapters():
    from nier_automata.game import chapters_ui as ui
    assert ui.entries(type("C", (), {"state": None, "scope": None})())[0].kind == "note"
    j = cg.chapter_index("A", "09-01")
    ctx = _Ctx(reached={j}, gag=("J", "K"), missing={db.CHAPTERS[j]["name"]})
    es = ui.entries(ctx)
    chap = next(e for e in es if e.kind == "chapter" and e.text.startswith("09-01"))
    assert chap.enabled and chap.target == cl.STARTS[j] and "check: reach" in chap.text
    end = next(e for e in es if e.text.startswith("Ending J"))
    assert end.enabled and end.target[3] == "140_00_A_RobotM_CrazyReligion"
    assert not next(e for e in es if e.text.startswith("Ending K")).enabled         # partout : pas de saut
    other = next(e for e in es if e.kind == "chapter" and e.text.startswith("05-01"))
    assert not other.enabled and other.target is None and "not reached" in other.text
    assert ui.request(ctx, end) and ctx.chapter_request == (end.label, end.target)
    assert not ui.request(ctx, other)


def test_tab_entries_show_what_a_locked_chapter_needs():
    from nier_automata.game import chapters_ui as ui
    es = ui.entries(_Ctx(reached={B03}, ckeys=dict(cl.CHAPTER_KEYS)))
    row = next(e for e in es if e.kind == "chapter" and "B Chapter Key 0/2" in e.text)
    assert not row.enabled and "locked" in row.text
