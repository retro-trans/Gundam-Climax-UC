"""Tiny MIPS assembler wrapper: one instruction at a time (keystone adds delay-slot nops
when given a sequence and rejects absolute branch targets), so branches and jumps are
encoded here and everything else goes through keystone.

asm(lines, base) -> bytes ; lines may contain 'label:' entries and '.word N'.
"""
import re
import struct

from keystone import Ks, KS_ARCH_MIPS, KS_MODE_MIPS32, KS_MODE_LITTLE_ENDIAN

_ks = Ks(KS_ARCH_MIPS, KS_MODE_MIPS32 + KS_MODE_LITTLE_ENDIAN)

REGS = {n: i for i, n in enumerate(
    'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}

BR2 = {'beq': 4, 'bne': 5, 'beql': 0x14, 'bnel': 0x15}
BR1 = {'beqz': (4, None), 'bnez': (5, None), 'blez': (6, None), 'bgtz': (7, None),
       'bltz': (1, 0), 'bgez': (1, 1)}


def reg(s):
    return REGS[s.strip().lstrip('$')]


def _branch(op, args, addr, target):
    off = (target - (addr + 4)) >> 2
    if not -0x8000 <= off < 0x8000:
        raise ValueError('branch out of range')
    off &= 0xFFFF
    if op == 'b':
        return (4 << 26) | off
    if op in BR2:
        return (BR2[op] << 26) | (reg(args[0]) << 21) | (reg(args[1]) << 16) | off
    code, rt = BR1[op]
    if rt is None:
        return (code << 26) | (reg(args[0]) << 21) | off
    return (code << 26) | (reg(args[0]) << 21) | (rt << 16) | off


def asm(lines, base):
    labels = {}
    addr = base
    items = []
    for ln in lines:
        ln = ln.split('#')[0].strip()
        if not ln:
            continue
        if ln.endswith(':'):
            labels[ln[:-1]] = addr
            continue
        items.append((addr, ln))
        addr += 4

    def val(s):
        s = s.strip()
        return labels[s] if s in labels else int(s, 0)

    out = bytearray()
    for a, ln in items:
        m = re.match(r'(\S+)\s*(.*)', ln)
        op, rest = m.group(1), m.group(2)
        args = [x.strip() for x in rest.split(',')] if rest else []
        if op == '.word':
            w = val(args[0])
        elif op == 'b' or op in BR2 or op in BR1:
            w = _branch(op, args[:-1], a, val(args[-1]))
        elif op in ('j', 'jal'):
            w = ((2 if op == 'j' else 3) << 26) | ((val(args[0]) >> 2) & 0x3FFFFFF)
        elif op == 'nop':
            w = 0
        else:
            enc, _ = _ks.asm(ln, a)
            w = struct.unpack('<I', bytes(enc[:4]))[0]
        out += struct.pack('<I', w)
    return bytes(out)
