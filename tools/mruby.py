"""Lecteur minimal de bytecode mruby 1.x ("RITE0003") : les *_scp.bin de NieR:Automata.

Format (gros-boutiste) : en-tete 22 o ("RITE0003", crc u16, taille u32, "MATZ", "0000"), section "IREP"
(taille u32, "0000"), puis enregistrements IREP en profondeur d'abord :
  u32 taille, u16 nlocals, u16 nregs, u16 nb enfants, u32 nb instructions, [bourrage -> alignement 4 du fichier],
  instructions u32, u32 nb pool + (u8 type 0=chaine 1=entier 2=flottant, u16 long, octets),
  u32 nb symboles + (u16 long | 0xFFFF = nul, octets, NUL), puis les enfants.
Instruction 32 bits : op = i & 0x7f, A = i>>23, B = (i>>14)&0x1ff, C = (i>>7)&0x7f, Bx = (i>>7)&0xffff,
sBx = Bx - 0x7fff.
"""
from __future__ import annotations

import struct

OPS = ("NOP MOVE LOADL LOADI LOADSYM LOADNIL LOADSELF LOADT LOADF GETGLOBAL SETGLOBAL GETSPECIAL SETSPECIAL "
       "GETIV SETIV GETCV SETCV GETCONST SETCONST GETMCNST SETMCNST GETUPVAR SETUPVAR JMP JMPIF JMPNOT ONERR "
       "RESCUE POPERR RAISE EPUSH EPOP SEND SENDB FSEND CALL SUPER ARGARY ENTER KARG KDICT RETURN TAILCALL "
       "BLKPUSH ADD ADDI SUB SUBI MUL DIV EQ LT LE GT GE ARRAY ARYCAT ARYPUSH AREF ASET APOST STRING STRCAT "
       "HASH LAMBDA RANGE OCLASS CLASS MODULE EXEC METHOD SCLASS TCLASS DEBUG STOP ERR").split()


class Irep:
    __slots__ = ("nlocals", "nregs", "iseq", "pool", "syms", "kids", "offset")

    def ins(self):
        """Instructions decodees : (op, A, B, C, Bx, sBx)."""
        for i in self.iseq:
            op = i & 0x7F
            bx = (i >> 7) & 0xFFFF
            yield (OPS[op] if op < len(OPS) else f"op{op}", i >> 23, (i >> 14) & 0x1FF, (i >> 7) & 0x7F, bx,
                   bx - 0x7FFF)


def parse(b: bytes) -> Irep:
    if b[:8] != b"RITE0003":
        raise ValueError("pas un binaire mruby RITE0003")
    p = 22
    if b[p:p + 4] != b"IREP":
        raise ValueError("section IREP absente")
    p += 12

    def rec():
        nonlocal p
        r = Irep()
        r.offset = p
        _, r.nlocals, r.nregs, nk, ni = struct.unpack_from(">IHHHI", b, p)
        p += 14
        p += (-p) & 3
        r.iseq = list(struct.unpack_from(f">{ni}I", b, p))
        p += 4 * ni
        (np_,) = struct.unpack_from(">I", b, p)
        p += 4
        r.pool = []
        for _ in range(np_):
            tt, ln = struct.unpack_from(">BH", b, p)
            p += 3
            v = b[p:p + ln]
            p += ln
            r.pool.append(v.decode("utf-8", "replace") if tt == 0 else
                          int(v) if tt == 1 else float(v) if tt == 2 else v)
        (ns,) = struct.unpack_from(">I", b, p)
        p += 4
        r.syms = []
        for _ in range(ns):
            (ln,) = struct.unpack_from(">H", b, p)
            p += 2
            if ln == 0xFFFF:
                r.syms.append(None)
                continue
            r.syms.append(b[p:p + ln].decode("utf-8", "replace"))
            p += ln + 1
        r.kids = [rec() for _ in range(nk)]
        return r

    return rec()


def walk(r: Irep):
    yield r
    for k in r.kids:
        yield from walk(k)


def calls(root: Irep, name: str):
    """Appels SEND/FSEND de la methode `name` : liste de (irep, indice, A, nb args, [valeurs constantes des args]).
    Une valeur d'argument est resolue si le registre a ete charge juste avant par LOADI/LOADL/LOADSYM/STRING/
    LOADT/LOADF/LOADNIL dans le meme bloc (dernier chargement avant l'appel), sinon None."""
    out = []
    for r in walk(root):
        ins = list(r.ins())
        for k, (op, a, b, c, bx, sbx) in enumerate(ins):
            if op not in ("SEND", "FSEND", "SENDB") or r.syms[b] != name:
                continue
            args = []
            for reg in range(a + 1, a + 1 + c):
                val = None
                for j in range(k - 1, -1, -1):
                    op2, a2, b2, c2, bx2, sbx2 = ins[j]
                    if op2 in ("JMP", "JMPIF", "JMPNOT"):
                        break
                    if a2 != reg:
                        continue
                    val = {"LOADI": sbx2, "LOADL": r.pool[bx2] if op2 == "LOADL" else None,
                           "LOADSYM": ":" + str(r.syms[bx2]) if op2 == "LOADSYM" else None,
                           "STRING": r.pool[bx2] if op2 == "STRING" else None,
                           "LOADT": True, "LOADF": False, "LOADNIL": "nil",
                           "SEND": ("call", r.syms[b2]) if op2 == "SEND" else None}.get(op2, ("?", op2))
                    break
                args.append(val)
            out.append((r, k, a, c, args))
    return out
