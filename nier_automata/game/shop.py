"""AP Items vendus dans les magasins.

Verifie en jeu (v1.04, 2026-11-23) :
- la table ShopInfoTable.bxm (XML binaire gros-boutiste) est relue a chaque ouverture d'un magasin :
  ShopInfo > shop_<X> > Item > item_<nom> > State_0..6 = "0"/"1" (vendu selon l'avancee) ;
- les paires (nom, valeur) sont PARTAGEES entre noeuds : on ne modifie que les noeuds (indice de donnee,
  ordre des enregistrements), jamais les donnees ;
- l'objet "magasin ouvert" est global (RVA 0x1410E00) ; +0x748 : identifiants des objets affiches (-1 = fin) ;
- porteurs : skins de Pod 950..953 (objets uniques jamais vendus) renommes "AP Item" (texte MCD CORE) ;
- image : une deviation saute l'image de l'objet pour les porteurs.
"""
from __future__ import annotations

import struct
from typing import Iterable, Optional

SHOP_UI_RVA = 0x1410E00
SHOP_LIST_OFFSET = 0x748
# Porteurs : skins de Pod 1-4 (objets uniques jamais vendus, textes dans le fichier CORE qui a toutes les
# lettres ; les teintures 880.. ont leurs textes dans un fichier aux lettres incompletes). 959 = notifications.
CARRIER_POOL = list(range(950, 959))                      # skins de Pod 1-9 (959 : notifications)
CARRIER_NAME = {950 + i: f"item_uq_podSkin{i + 1}" for i in range(9)}
CARRIER_NAMES = [CARRIER_NAME[c] for c in CARRIER_POOL]
CARRIER_IDS = CARRIER_POOL
THUMB_SITE_RVA = 0x808FFF        # mov edx,0xf ; juste avant sprintf("item_thumb_%03d", id % 1000) (r9 = numero)
THUMB_SITE_ORIGINAL = bytes.fromhex("ba0f000000")
THUMB_RETURN_RVA = 0x809004
THUMB_NONE = 4                    # item_thumb_004 n'existe pas : pas d'image
NO_IMAGE_SITE_RVA = 0x8FFE1B     # test eax,eax ; je <pas d'image> (apres recherche de l'image de l'objet)
NO_IMAGE_SITE_ORIGINAL = bytes.fromhex("85c00f84b5feffff")
SHOW_IMAGE_RVA = 0x8FFE23
SKIP_IMAGE_RVA = 0x8FFCD8
ITEM_TABLE_RVA = 0x133BA60   # fiches objets (0x1A0 octets) : +0x0 id, +0x10 nom interne, +0x98 prix d'achat
ITEM_ENTRY = 0x1A0
PRICE_OFFSET = 0x98

# Magasins sur la route A (les variantes d'un meme lieu partagent les emplacements).
SHOP_PLACES: dict[str, list[str]] = {
    "Resistance Camp": ["shop_RC_Grocery", "shop_RC_Grocery_small"],
    "Pascal's Village": ["shop_PV_Grocery"],
    "Forest Castle": ["shop_FC_Grocery"],
}


# --- table BXM ---------------------------------------------------------------------------------

class _Bxm:
    def __init__(self, raw: bytes):
        self.raw = raw
        nn, dn, _ = struct.unpack(">HHI", raw[8:16])
        self.nodes = [list(struct.unpack_from(">HHHH", raw, 16 + i * 8)) for i in range(nn)]
        self.doff = 16 + nn * 8
        self.soff = self.doff + dn * 4
        self.data = [struct.unpack_from(">HH", raw, self.doff + i * 4) for i in range(dn)]

    def s(self, o: int) -> Optional[str]:
        if o == 0xFFFF:
            return None
        e = self.raw.index(b"\0", self.soff + o)
        return self.raw[self.soff + o:e].decode("shift_jis", "replace")

    def name(self, i: int) -> str:
        return self.s(self.data[self.nodes[i][3]][0])

    def children(self, i: int) -> list[int]:
        cc, fc, _, _ = self.nodes[i]
        return list(range(fc, fc + cc))

    def pair(self, name: str, value: Optional[str]) -> Optional[int]:
        for j, (n, v) in enumerate(self.data):
            if self.s(n) == name and self.s(v) == value:
                return j
        return None

    def item_list(self, shop: str) -> Optional[int]:
        for sh in self.children(0):
            if self.name(sh) == shop:
                for c in self.children(sh):
                    if self.name(c) == "Item":
                        return c
        return None


def _victims(names: list[str], count: int, carriers: list[str]) -> list[int]:
    order = ([i for i, n in enumerate(names) if n in carriers]
             + [i for i, n in enumerate(names) if n.startswith("item_stUp_") and n.endswith("_M")]
             + [i for i, n in enumerate(names) if n.startswith("item_stUp_") and n.endswith("_S")]
             + list(range(len(names) - 1, -1, -1)))
    out: list[int] = []
    for i in order:
        if i not in out:
            out.append(i)
        if len(out) == count:
            break
    return out


def plan(raw: bytes, carriers_by_shop: dict[str, list[str]]) -> list[tuple[int, int]]:
    """Ecritures (offset, u16) pour mettre en tete de chaque magasin ses porteurs (dans l'ordre), toujours
    en vente. Les autres objets gardent leur ordre ; les victimes sont d'abord les bonus de stats."""
    b = _Bxm(raw)
    writes: list[tuple[int, int]] = []
    for shop, carriers in carriers_by_shop.items():
        lst = b.item_list(shop)
        data = [b.pair(c, None) for c in carriers]
        if lst is None or not carriers or None in data:
            continue
        kids = b.children(lst)
        names = [b.name(k) for k in kids]
        vic = _victims(names, len(carriers), carriers)
        records = [list(b.nodes[k]) for k in kids]
        for slot, v in enumerate(vic):
            records[v][3] = data[slot]
            for st in range(records[v][1], records[v][1] + records[v][0]):
                one = b.pair(b.name(st), "1")
                if one is not None and one != b.nodes[st][3]:
                    writes.append((16 + st * 8 + 6, one))
        new_order = [records[v] for v in vic] + [r for i, r in enumerate(records) if i not in vic]
        for pos, rec in zip(kids, new_order):
            for f in range(4):
                if rec[f] != b.nodes[pos][f]:
                    writes.append((16 + pos * 8 + 2 * f, rec[f]))
    return writes


def assign_carriers(slots: list[tuple[str, int]], pool: list[int], owned: set) -> dict[int, tuple[str, int]]:
    """Un porteur (objet unique non possede) par emplacement (lieu, numero)."""
    free = [c for c in pool if c not in owned]
    return dict(zip(free, slots))


def reserve_names(raw: bytes, carriers: list[str]) -> list[tuple[int, bytes]]:
    """Le BXM ne contient pas les noms des porteurs et on ne peut pas y ajouter de texte : on reecrit des noms
    utilises UNIQUEMENT par les magasins de test (shop_TEST_*, jamais ouverts en jeu). Renvoie (offset, octets)."""
    b = _Bxm(raw)
    missing = [c for c in carriers if b.pair(c, None) is None]
    if not missing:
        return []
    users: dict[int, set[str]] = {}          # offset de chaine -> magasins dont un noeud l'utilise
    for sh in b.children(0):
        shop_name = b.name(sh)
        stack = list(b.children(sh))
        while stack:
            n = stack.pop()
            users.setdefault(b.data[b.nodes[n][3]][0], set()).add(shop_name)
            stack.extend(b.children(n))
    used_as_value = {v for _, v in b.data}
    free = sorted((o for o, shops in users.items()
                   if shops and all("TEST" in s for s in shops) and o not in used_as_value
                   and b.s(o) and b.s(o).startswith(("item_", "skill_", "weapon_"))),
                  key=lambda o: len(b.s(o)))
    out: list[tuple[int, bytes]] = []
    for c in missing:
        pick = next((o for o in free if len(b.s(o)) >= len(c)), None)
        if pick is None:
            break
        free.remove(pick)
        out.append((b.soff + pick, c.encode() + b"\0"))
    return out


def shop_item_names(raw: bytes) -> dict[str, set[str]]:
    b = _Bxm(raw)
    out = {}
    for sh in b.children(0):
        for c in b.children(sh):
            if b.name(c) == "Item":
                out[b.name(sh)] = {b.name(i) for i in b.children(c)}
    return out


def identify(displayed: Iterable[int], shop_ids: dict[str, set[int]], carriers: set[int]) -> Optional[str]:
    """Magasin ouvert : le plus petit dont le contenu couvre tous les objets affiches (hors porteurs)."""
    known = set().union(*shop_ids.values()) if shop_ids else set()
    shown = {i for i in displayed if i >= 0 and i not in carriers and i in known}  # puces/armes : ignorees
    fits = [s for s, ids in shop_ids.items() if shown <= ids]
    return min(fits, key=lambda s: len(shop_ids[s])) if fits and shown else None


def description(me: int, receiver, item, receiver_name, progression: bool) -> str:
    if item is None or receiver is None:
        return "Objet Archipelago"
    who = "toi" if receiver == me else receiver_name
    return f"Pour {who} : {item}" + (" (progression)" if progression else "")


def location_name(place: str, k: int) -> str:
    return f"Shop {place} #{k}"


# --- acces memoire -----------------------------------------------------------------------------

def find_table(mem) -> Optional[int]:
    from .notify import _scan
    for a in _scan(mem, [b"BXM\0"])[b"BXM\0"]:
        try:
            h = mem.read(a, 16)
            nn, dn, ds = struct.unpack(">HHI", h[8:16])
            if 0 < nn < 60000 and 0 < dn < 60000 and 0 < ds < 0x100000:
                head = mem.read(a + 16 + nn * 8 + dn * 4, 16)
                if head.startswith(b"ShopInfo\0"):
                    return a
        except OSError:
            continue
    return None


def table_size(mem, a: int) -> int:
    nn, dn, ds = struct.unpack(">HHI", mem.read(a, 16)[8:16])
    return 16 + nn * 8 + dn * 4 + ds


def item_ids_by_name(mem, count: int = 1100) -> dict[str, int]:
    raw = mem.read(mem.base + ITEM_TABLE_RVA, ITEM_ENTRY * count)
    out = {}
    for k in range(count):
        e = raw[k * ITEM_ENTRY:(k + 1) * ITEM_ENTRY]
        name = e[0x10:0x40].split(b"\0")[0].decode("ascii", "replace")
        if name:
            out[name] = struct.unpack_from("<I", e, 0)[0]
    return out


def displayed_ids(mem) -> list[int]:
    ids = struct.unpack("<128i", mem.read(mem.base + SHOP_UI_RVA + SHOP_LIST_OFFSET, 512))
    out = []
    for i in ids:
        if i < 0:
            break
        out.append(i)
    return out


def set_price(mem, names_to_ids: dict[str, int], carrier: str, price: int) -> None:
    raw = mem.read(mem.base + ITEM_TABLE_RVA, ITEM_ENTRY * 1100)
    for k in range(1100):
        if raw[k * ITEM_ENTRY + 0x10:k * ITEM_ENTRY + 0x40].split(b"\0")[0] == carrier.encode():
            mem.write(mem.base + ITEM_TABLE_RVA + k * ITEM_ENTRY + PRICE_OFFSET, struct.pack("<I", price))
            return


def active_slots(place: str, count: int, checked: set, loc_id) -> list[int]:
    """Emplacements 1..count du magasin pas encore achetes (check non envoye)."""
    return [k for k in range(1, count + 1) if loc_id(place, k) not in checked]


def carrier_map(active: list[int], carrier_ids: list[int]) -> dict[int, int]:
    """Porteur (id d'objet) -> numero d'emplacement : les porteurs suivent les emplacements restants."""
    return dict(zip(carrier_ids, active))


class ShopSession:
    """AP Items en magasin pour un processus du jeu. Chaque emplacement (lieu, numero) a son propre porteur :
    description fixe, et un achat identifie directement l'emplacement (rien a deviner)."""

    def __init__(self, mem, orig_path, price: int, slots: list[tuple[str, int]], owned: set):
        from .mcd_text import MenuTexts
        self.mem = mem
        self.ok = False
        self.addr = find_table(mem)
        if self.addr is None:
            return
        size = table_size(mem, self.addr)
        cached = None
        try:
            data = orig_path.read_bytes()
            if len(data) == size:
                cached = data   # table d'origine gardee par une session precedente (meme processus)
        except OSError:
            pass
        self.orig = cached or mem.read(self.addr, size)
        if cached is None:
            try:
                orig_path.write_bytes(self.orig)
            except OSError:
                pass
        self.carriers = assign_carriers(slots, CARRIER_POOL, owned)     # id -> (lieu, numero)
        used = [CARRIER_NAME[c] for c in self.carriers]
        base = bytearray(self.orig)
        for off, data in reserve_names(self.orig, used):
            base[off:off + len(data)] = data
        self.base = bytes(base)
        self.texts = MenuTexts(mem)
        ids = item_ids_by_name(mem)
        for cid in self.carriers:
            self.texts.set_text(f"CORE_ITEM_NAME_{cid}", "AP Item")
            set_price(mem, ids, CARRIER_NAME[cid], price)
        if self.carriers:
            install_thumb(mem, min(self.carriers), max(self.carriers))
        self.described: dict[int, str] = {}
        self.ok = True

    def apply(self, active: dict[str, list[int]]) -> None:
        by_place: dict[str, list[str]] = {}
        for cid, (place, k) in sorted(self.carriers.items(), key=lambda kv: kv[1]):
            if k in active.get(place, []):
                by_place.setdefault(place, []).append(CARRIER_NAME[cid])
        per_shop = {shop: by_place.get(place, []) for place, shops in SHOP_PLACES.items() for shop in shops}
        b = bytearray(self.base)
        for off, val in plan(self.base, per_shop):
            struct.pack_into(">H", b, off, val)
        self.mem.write(self.addr, bytes(b))

    def describe(self, texts: dict[tuple[str, int], str]) -> None:
        for cid, slot in self.carriers.items():
            t = texts.get(slot, "Objet Archipelago")
            if self.described.get(cid) != t:
                self.texts.set_text(f"CORE_ITEM_HELP_{cid}", t, width=34)
                self.described[cid] = t

def no_image_cave(cave: int, base: int, lo: int, hi: int) -> bytes:
    """test eax,eax ; je skip ; cmp esi,lo ; jb show ; cmp esi,hi ; jbe skip ; show: jmp ; skip: jmp."""
    c = bytearray(b"\x85\xC0")
    je = len(c); c += b"\x0F\x84\0\0\0\0"
    c += b"\x81\xFE" + struct.pack("<I", lo)
    jb = len(c); c += b"\x72\x00"
    c += b"\x81\xFE" + struct.pack("<I", hi)
    jbe = len(c); c += b"\x0F\x86\0\0\0\0"
    show = len(c); c += b"\xE9" + struct.pack("<i", base + SHOW_IMAGE_RVA - (cave + show + 5))
    skip = len(c); c += b"\xE9" + struct.pack("<i", base + SKIP_IMAGE_RVA - (cave + skip + 5))
    struct.pack_into("<i", c, je + 2, skip - (je + 6))
    c[jb + 1] = show - (jb + 2)
    struct.pack_into("<i", c, jbe + 2, skip - (jbe + 6))
    return bytes(c)


def install_no_image(mem) -> bool:
    """Pas d'image pour les porteurs (une fois par processus)."""
    import ctypes
    from ctypes import wintypes
    site = mem.base + NO_IMAGE_SITE_RVA
    cur = mem.read(site, 8)
    if cur[0] == 0xE9:
        return True
    if cur != NO_IMAGE_SITE_ORIGINAL:
        return False
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    cave = None
    for delta in range(0x10000000, 0x7F000000, 0x1000000):
        cave = k.VirtualAllocEx(h, ctypes.c_void_p((mem.base - delta) & ~0xFFFF), 0x1000, 0x3000, 0x40)
        if cave:
            break
    k.CloseHandle(h)
    if not cave:
        return False
    mem.write(cave, no_image_cave(cave, mem.base, min(CARRIER_IDS), max(CARRIER_IDS)))
    mem.write_code(site, b"\xE9" + struct.pack("<i", cave - (site + 5)) + b"\x90" * 3)
    return True


def thumb_cave(cave: int, base: int, lo: int, hi: int, thumb: int) -> bytes:
    """cmp ebx,lo ; jb L ; cmp ebx,hi ; ja L ; mov r9d,thumb ; L: mov edx,0xf ; jmp retour."""
    c = bytearray()
    c += bytes([0x81, 0xFB]) + struct.pack("<I", lo)
    jb = len(c); c += bytes([0x72, 0x00])
    c += bytes([0x81, 0xFB]) + struct.pack("<I", hi)
    ja = len(c); c += bytes([0x77, 0x00])
    c += bytes([0x41, 0xB9]) + struct.pack("<I", thumb)
    lab = len(c)
    c += THUMB_SITE_ORIGINAL
    c += bytes([0xE9]) + struct.pack("<i", base + THUMB_RETURN_RVA - (cave + len(c) + 5))
    c[jb + 1] = lab - (jb + 2)
    c[ja + 1] = lab - (ja + 2)
    return bytes(c)


def install_thumb(mem, lo: int = 950, hi: int = 958) -> bool:
    """Les porteurs n'ont pas de vignette (une fois par processus)."""
    import ctypes
    from ctypes import wintypes
    site = mem.base + THUMB_SITE_RVA
    cur = mem.read(site, 5)
    if cur[0] == 0xE9:   # deja installee (session precedente) : on met a jour les bornes
        cave = site + 5 + struct.unpack("<i", cur[1:5])[0]
        mem.write(cave, thumb_cave(cave, mem.base, lo, hi, THUMB_NONE))
        return True
    if cur != THUMB_SITE_ORIGINAL:
        return False
    k = mem._k
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1F0FFF, False, mem.pid)
    k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k.VirtualAllocEx.restype = ctypes.c_void_p
    cave = None
    for delta in range(0x10000000, 0x7F000000, 0x1000000):
        cave = k.VirtualAllocEx(h, ctypes.c_void_p((mem.base - delta) & ~0xFFFF), 0x1000, 0x3000, 0x40)
        if cave:
            break
    k.CloseHandle(h)
    if not cave:
        return False
    mem.write(cave, thumb_cave(cave, mem.base, lo, hi, THUMB_NONE))
    mem.write_code(site, bytes([0xE9]) + struct.pack("<i", cave - (site + 5)))
    return True
