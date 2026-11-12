"""Experiment: draw a test string every frame with the game's own text renderer, called from a hook at
the entry of a per-frame function. Debug-only (runtime RAM patch over PINE).

python subtest.py install <func_hex> [x] [y] [scale] [text]
python subtest.py remove
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import gdbg  # noqa: E402
from gdbg import hi, lo, j_insn  # noqa: E402
from asm import asm  # noqa: E402

CAVE = 0x4ADA00
STR = 0x4ADD00
SAVE = 0x4ADE80          # u32 hooked addr, 8 bytes original code
TEXT_CTX_GP = -0x7AB8    # *(gp-0x7AB8) = text context (CUmeStdFont renderer)
SET_COLOR = 0x196B90     # (ctx, r, g, b, a)
DRAW_FMT = 0x196D00      # (ctx, matrix*, fmt, ...)
MAT_COPY = 0x1396E8      # (dst, src) 4x4
MAT_TRANS = 0x18DDD0     # (m, x, y, z) in f12-f14
MAT_SCALE = 0x18DC50     # (m, sx, sy, sz)
BASE_MAT = 0x70003F10    # scratchpad 2D base matrix (used by the help-bar draw)


def f32(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


RN = {'ra': 31, 'a0': 4, 'a1': 5, 'a2': 6, 'a3': 7, 'sp': 29}


def sdld(op, rt, off, base='sp'):
    """keystone's MIPS32 mode has no sd/ld: encode them by hand."""
    return '.word 0x%08X' % (((0x3F if op == 'sd' else 0x37) << 26) | (RN[base] << 21) | (RN[rt] << 16) | off)


def code(func, orig, x, y, sc):
    w0, w1 = struct.unpack('<2I', orig)
    L = ['addiu $sp, $sp, -0xa0',
         sdld('sd', 'ra', 0x90), sdld('sd', 'a0', 0x80), sdld('sd', 'a1', 0x78), sdld('sd', 'a2', 0x70),
         sdld('sd', 'a3', 0x68),
         'lw $a0, %d($gp)' % TEXT_CTX_GP,
         'beqz $a0, skip', 'nop',
         'addiu $a1, $zero, 255', 'addiu $a2, $zero, 255', 'addiu $a3, $zero, 255',
         'addiu $t0, $zero, 255',
         'jal 0x%X' % SET_COLOR, 'nop',
         'addiu $a0, $sp, 0x10',
         'lui $a1, %d' % hi(BASE_MAT), 'addiu $a1, $a1, %d' % lo(BASE_MAT),
         'jal 0x%X' % MAT_COPY, 'nop',
         'addiu $a0, $sp, 0x10',
         'lui $at, %d' % (f32(x) >> 16), 'mtc1 $at, $f12',
         'lui $at, %d' % (f32(y) >> 16), 'mtc1 $at, $f13',
         'mtc1 $zero, $f14',
         'jal 0x%X' % MAT_TRANS, 'nop',
         'addiu $a0, $sp, 0x10',
         'lui $at, %d' % (f32(sc) >> 16), 'mtc1 $at, $f12', 'mtc1 $at, $f13',
         'lui $at, 0x3f80', 'mtc1 $at, $f14',
         'jal 0x%X' % MAT_SCALE, 'nop',
         'lw $a0, %d($gp)' % TEXT_CTX_GP,
         'addiu $a1, $sp, 0x10',
         'lui $a2, %d' % hi(STR), 'addiu $a2, $a2, %d' % lo(STR),
         'jal 0x%X' % DRAW_FMT, 'nop',
         'skip:',
         sdld('ld', 'ra', 0x90), sdld('ld', 'a0', 0x80), sdld('ld', 'a1', 0x78), sdld('ld', 'a2', 0x70),
         sdld('ld', 'a3', 0x68),
         'addiu $sp, $sp, 0xa0']
    if (w0 >> 26) == 3:      # hooked a jal: the cave is called instead and tail-jumps to the target
        L += ['j 0x%X' % ((w0 & 0x3FFFFFF) << 2), 'nop']
    else:                    # hooked a function entry: run the two replaced instructions, continue
        L += ['.word 0x%08X' % w0, '.word 0x%08X' % w1, 'j 0x%X' % (func + 8), 'nop']
    return asm(L, CAVE)


def install(d, func, x=100.0, y=380.0, sc=1.0, text='Subtitle test: the quick brown fox.'):
    remove(d)
    orig = d.p.read(func, 8)
    c = code(func, orig, x, y, sc)
    assert CAVE + len(c) <= STR
    s = text.encode('cp932') + b'\0'
    d.halt()
    try:
        d.p.write(STR, s)
        d.p.write(SAVE, struct.pack('<I', func) + orig)
        d.p.write(CAVE, c)
        if (struct.unpack('<I', orig[:4])[0] >> 26) == 3:
            d.p.write(func, struct.pack('<I', (3 << 26) | (CAVE >> 2)))   # jal CAVE (delay slot kept)
        else:
            d.p.write(func, struct.pack('<2I', j_insn(CAVE), 0))
        d.flush_rec()
    finally:
        d.resume()


def remove(d):
    func = d.p.r32(SAVE)
    if not func:
        return
    orig = d.p.read(SAVE + 4, 8)
    d.halt()
    try:
        d.p.write(func, orig)
        d.p.write(SAVE, b'\0' * 12)
        d.flush_rec()
    finally:
        d.resume()


if __name__ == '__main__':
    a = sys.argv[1:]
    d = gdbg.Dbg()
    if a[0] == 'install':
        args = [int(a[1], 16)] + [float(v) for v in a[2:5]]
        if len(a) > 5:
            args.append(a[5])
        install(d, *args)
    elif a[0] == 'remove':
        remove(d)
