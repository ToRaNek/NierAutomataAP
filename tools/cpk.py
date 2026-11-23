"""Lecture minimale des archives CPK (CRI) : table des matieres (@UTF) et extraction (CRILAYLA geree)."""
import struct
import sys
from pathlib import Path

DATA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\NieRAutomata\data")


def utf_table(b: bytes):
    """Table @UTF (gros-boutiste) -> liste de dict."""
    assert b[:4] == b"@UTF", b[:4]
    size, _ver, rows_off, strings_off, data_off, name_off, ncols, row_len, nrows = struct.unpack(">IHHIIIHHI", b[4:32])
    base = 8
    strings = base + strings_off
    data = base + data_off

    def cstr(o):
        e = b.index(b"\0", strings + o)
        return b[strings + o:e].decode("utf-8", "replace")

    cols, p = [], 32
    for _ in range(ncols):
        flags = b[p]; p += 1
        name = cstr(struct.unpack(">I", b[p:p + 4])[0]); p += 4
        storage, typ = flags & 0xF0, flags & 0x0F
        const = None
        if storage == 0x30:  # constante
            const, p = _read(b, p, typ, cstr, data)
        cols.append((name, storage, typ, const))
    rows = []
    for r in range(nrows):
        p = base + rows_off + r * row_len
        row = {}
        for name, storage, typ, const in cols:
            if storage == 0x50:
                row[name], p = _read(b, p, typ, cstr, data)
            elif storage == 0x30:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows


def _read(b, p, typ, cstr, data):
    fmt = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f"}
    if typ in fmt:
        n = struct.calcsize(fmt[typ])
        return struct.unpack(fmt[typ], b[p:p + n])[0], p + n
    if typ == 0xA:
        return cstr(struct.unpack(">I", b[p:p + 4])[0]), p + 4
    if typ == 0xB:
        o, n = struct.unpack(">II", b[p:p + 8])
        return b[data + o:data + o + n], p + 8
    raise ValueError(f"type {typ}")


def _decrypt(chunk: bytes) -> bytes:
    """Les tables @UTF peuvent etre chiffrees (XOR CRI)."""
    if chunk[:4] == b"@UTF":
        return chunk
    out = bytearray(chunk); m = 0x655F; t = 0x4115
    for i in range(len(out)):
        out[i] ^= m & 0xFF
        m = (m * t) & 0xFFFFFFFF
    return bytes(out)


def toc(path: Path):
    with open(path, "rb") as f:
        head = f.read(0x800)
        assert head[:4] == b"CPK ", head[:4]
        n = struct.unpack("<I", head[8:12])[0]
        cpk = utf_table(_decrypt(head[16:16 + n]))[0]
        toc_off = cpk.get("TocOffset")
        content_off = cpk.get("ContentOffset")
        if not toc_off:
            return [], cpk
        f.seek(toc_off)
        h = f.read(16)
        n = struct.unpack("<I", h[8:12])[0]
        rows = utf_table(_decrypt(f.read(n)))
        add = min(toc_off, content_off) if content_off else toc_off
        for r in rows:
            r["_abs"] = r["FileOffset"] + add
        return rows, cpk


def crilayla(src: bytes) -> bytes:
    """Decompression CRILAYLA (algorithme de reference : bits lus a reculons, sortie ecrite a reculons)."""
    if src[:8] != b"CRILAYLA":
        return src
    usize, hoff = struct.unpack("<II", src[8:16])
    out = bytearray(usize + 0x100)
    out[:0x100] = src[hoff + 0x10:hoff + 0x110]
    st = {"off": len(src) - 0x100 - 1, "pool": 0, "left": 0}

    def bits(n):
        v = produced = 0
        while produced < n:
            if st["left"] == 0:
                st["pool"] = src[st["off"]]; st["left"] = 8; st["off"] -= 1
            take = min(st["left"], n - produced)
            v = (v << take) | ((st["pool"] >> (st["left"] - take)) & ((1 << take) - 1))
            st["left"] -= take; produced += take
        return v

    out_end = 0x100 + usize - 1
    done = 0
    while done < usize:
        if bits(1):
            ref = out_end - done + bits(13) + 3
            ln = 3
            for lvl, nb in enumerate((2, 3, 5, 8)):
                x = bits(nb)
                ln += x
                if x != (1 << nb) - 1:
                    break
            else:
                while True:
                    x = bits(8)
                    ln += x
                    if x != 255:
                        break
            for _ in range(ln):
                out[out_end - done] = out[ref]
                ref -= 1
                done += 1
        else:
            out[out_end - done] = bits(8)
            done += 1
    return bytes(out)


def extract(path: Path, row) -> bytes:
    with open(path, "rb") as f:
        f.seek(row["_abs"])
        data = f.read(row["FileSize"])
    if row.get("ExtractSize") and row["ExtractSize"] != row["FileSize"]:
        data = crilayla(data)
    return data


if __name__ == "__main__":
    for p in sorted(DATA.glob("*.cpk")):
        rows, _ = toc(p)
        names = [f'{r.get("DirName") or ""}/{r.get("FileName")}' for r in rows]
        pat = sys.argv[1] if len(sys.argv) > 1 else ""
        hits = [n for n in names if pat in n]
        print(p.name, len(rows), hits[:15])


def dat_files(b: bytes):
    """Conteneur DAT PlatinumGames -> {nom: octets}."""
    assert b[:4] == b"DAT\0", b[:4]
    n, off_t, ext_t, name_t, size_t = struct.unpack("<IIIII", b[4:24])
    offs = struct.unpack(f"<{n}I", b[off_t:off_t + 4 * n])
    sizes = struct.unpack(f"<{n}I", b[size_t:size_t + 4 * n])
    nlen = struct.unpack("<I", b[name_t:name_t + 4])[0]
    names = [b[name_t + 4 + i * nlen:name_t + 4 + (i + 1) * nlen].split(b"\0")[0].decode() for i in range(n)]
    return {nm: b[o:o + s] for nm, o, s in zip(names, offs, sizes)}


def find(name: str):
    for p in sorted(DATA.glob("*.cpk")):
        rows, _ = toc(p)
        for r in rows:
            if f'{r.get("DirName") or ""}/{r.get("FileName")}' == name:
                return p, r
    return None, None


def pak_yax(b: bytes):
    """Paquet .pak -> liste d'arbres YAX [(profondeur, hachage de balise, valeur)]."""
    import zlib
    count_like, _ = struct.unpack("<II", b[:8])
    hsize = struct.unpack("<I", b[8:12])[0]
    entries = []
    p = 12
    while p + 12 <= hsize + 12 and p < len(b):
        typ, size, off = struct.unpack("<III", b[p:p + 12])
        if off == 0 or off > len(b):
            break
        entries.append((typ, size, off)); p += 12
        if p >= hsize:
            break
    out = []
    for i, (typ, size, off) in enumerate(entries):
        nxt = entries[i + 1][2] if i + 1 < len(entries) else len(b)
        raw = b[off:nxt]
        if len(raw) != size:
            try:
                raw = zlib.decompress(raw[4:]) if len(raw) > 4 else raw
            except zlib.error:
                pass
        out.append(yax(raw))
    return out


def yax(b: bytes):
    n = struct.unpack("<I", b[:4])[0]
    nodes = []
    for i in range(n):
        ind, tag, vo = struct.unpack("<BII", b[4 + i * 9:4 + i * 9 + 9])
        val = b[vo:b.index(b"\0", vo)].decode("shift_jis", "replace") if vo else ""
        nodes.append((ind, tag, val))
    return nodes


TAG_POS, TAG_OBJ = 0x462CE4F5, 0x624B37F2


def hap_items(dat: bytes, prefix="it"):
    """Entites d'un fichier de phase/quete dont l'objId commence par `prefix` -> [(objId, (x,y,z), source)]."""
    out = []
    for name, data in dat_files(dat).items():
        if not name.endswith(".pak"):
            continue
        try:
            trees = pak_yax(data)
        except Exception:
            continue
        for t in trees:
            for i, (ind, tag, v) in enumerate(t):
                if tag == TAG_OBJ and v.startswith(prefix):
                    for j in range(i - 1, max(-1, i - 12), -1):
                        if t[j][1] == TAG_POS and t[j][0] == ind + 1:
                            try:
                                out.append((v, tuple(map(float, t[j][2].split()))[:3], name))
                            except ValueError:
                                pass
                            break
    return out
