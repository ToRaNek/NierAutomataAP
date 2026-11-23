"""Lecture d'un fichier BXM (XML binaire PlatinumGames, gros-boutiste)."""
import struct


def parse(d: bytes):
    nn, dn, ds = struct.unpack(">HHI", d[8:16])
    nodes = [struct.unpack_from(">HHHH", d, 16 + i * 8) for i in range(nn)]
    doff = 16 + nn * 8
    data = [struct.unpack_from(">HH", d, doff + i * 4) for i in range(dn)]
    soff = doff + dn * 4

    def s(o):
        if o == 0xFFFF:
            return None
        e = d.index(b"\0", soff + o)
        return d[soff + o:e].decode("shift_jis", "replace")

    def build(i):
        cc, fc, ac, di = nodes[i]
        name, val = s(data[di][0]), s(data[di][1])
        attrs = {s(data[di + 1 + k][0]): s(data[di + 1 + k][1]) for k in range(ac)}
        return {"name": name, "value": val, "attrs": attrs, "children": [build(fc + c) for c in range(cc)]}

    return build(0), soff


def dump(n, depth=0, out=None):
    out = out if out is not None else []
    a = " ".join(f"{k}={v}" for k, v in n["attrs"].items())
    out.append("  " * depth + f"{n['name']}" + (f"={n['value']}" if n["value"] else "") + (f" [{a}]" if a else ""))
    for c in n["children"]:
        dump(c, depth + 1, out)
    return out


def value_slots(d: bytes, path_test):
    """Adresses (dans d) des champs 'valeur' des noeuds dont le chemin satisfait path_test(path)."""
    nn, dn, ds = struct.unpack(">HHI", d[8:16])
    nodes = [struct.unpack_from(">HHHH", d, 16 + i * 8) for i in range(nn)]
    doff = 16 + nn * 8
    soff = doff + dn * 4

    def s(o):
        e = d.index(b"\0", soff + o)
        return d[soff + o:e].decode("shift_jis", "replace")

    out = []

    def walk(i, path):
        cc, fc, ac, di = nodes[i]
        name = s(struct.unpack_from(">H", d, doff + di * 4)[0])
        p = path + (name,)
        if path_test(p):
            out.append(doff + di * 4 + 2)
        for c in range(cc):
            walk(fc + c, p)

    walk(0, ())
    return out, soff
