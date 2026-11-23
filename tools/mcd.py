"""Fichiers de messages MCD (NieR:Automata) charges en memoire : texte code en indices de symboles."""
import struct


def header_ok(h: bytes, size_limit=0x800000):
    if len(h) < 40:
        return False
    mo, mc, so, sc, go, gc, fo, fc, eo, ec = struct.unpack_from("<10I", h)
    return (mo == 0x28 and 0 < mc < 20000 and mo < so < size_limit and 0 < sc < 20000
            and so < go < size_limit and 0 < gc < 20000 and go < fo < size_limit and 0 < fc < 64
            and fo < eo <= size_limit and ec < 20000)


def decode_letters(letters, symbols):
    out = []
    i = 0
    while i < len(letters):
        c = letters[i]
        if c == 0x8000:
            break
        if c == 0x8001:
            out.append(" "); i += 2; continue
        if c < len(symbols):
            out.append(chr(symbols[c][1]))
        else:
            out.append("?")
        i += 1
    return "".join(out)


def lines(mem, base):
    """[(adresse des lettres, nb de lettres u16, texte)] de toutes les lignes du fichier."""
    h = mem.read(base, 40)
    mo, mc, so, sc, go, gc, fo, fc, eo, ec = struct.unpack_from("<10I", h)
    sym_raw = mem.read(base + so, sc * 8)
    symbols = [struct.unpack_from("<HHI", sym_raw, i * 8) for i in range(sc)]
    msgs = mem.read(base + mo, mc * 16)
    out = []
    for k in range(mc):
        po, pc, _, _ = struct.unpack_from("<4I", msgs, k * 16)
        if pc > 64:
            continue
        pars = mem.read(base + po, pc * 20)
        for j in range(pc):
            lo, lc, _, _, _ = struct.unpack_from("<5I", pars, j * 20)
            if lc > 64:
                continue
            ls = mem.read(base + lo, lc * 24)
            for n in range(lc):
                _, _, to, tc, _, _ = struct.unpack_from("<4I2f", ls, n * 24)
                if not 0 < tc < 2048:
                    continue
                raw = mem.read(base + to, tc * 2)
                letters = struct.unpack(f"<{tc}H", raw)
                out.append((base + to, tc, decode_letters(letters, symbols)))
    return out, symbols


def encode(text, symbols, kerning=0):
    """Texte -> lettres u16 avec les symboles existants (None si un caractere manque)."""
    idx = {}
    for i, (font, ch, glyph) in enumerate(symbols):
        idx.setdefault(ch, i)
    out = []
    for c in text:
        if c == " ":
            out += [0x8001, kerning]
        elif ord(c) in idx:
            out.append(idx[ord(c)])
        else:
            return None
    return out
