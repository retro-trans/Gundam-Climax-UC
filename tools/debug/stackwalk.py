"""Call chain of a function at runtime: snapshot the stack at its entry, then unwind frame by frame
using each function's prologue (addiu $sp,-N and sd/sw $ra,K($sp)) from the ELF.

python stackwalk.py <func_hex> [seconds] [press_button]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import gdbg  # noqa: E402

ELF = os.path.join(os.path.dirname(__file__), '..', '..', 'work', 'source', 'iso', 'SLPS_256.27')
IMG = open(ELF, 'rb').read()[0x80:]
SNAP = 0x6F8


def w(a):
    return struct.unpack_from('<I', IMG, a - 0x100000)[0]


def prologue(func):
    """-> (frame size, ra offset) of the function starting at func."""
    size = ra = None
    for k in range(0, 40 * 4, 4):
        x = w(func + k)
        if x >> 16 == 0x27BD and size is None:
            size = 0x10000 - (x & 0xFFFF)
        if (x >> 16) in (0xFFBF, 0xAFBF):      # sd/sw $ra, K($sp)
            ra = x & 0xFFFF
        if size is not None and ra is not None:
            return size, ra
    return size, ra


def fstart(a):
    while True:
        a -= 4
        x = w(a)
        if x >> 16 == 0x27BD and x & 0x8000:
            return a


def unwind(func, ra0, stack):
    """At the entry of func nothing is allocated yet: sp is the caller's sp after its prologue."""
    chain = [(func, ra0)]
    sp, ra = 0, ra0
    for _ in range(16):
        caller = fstart(ra)
        csize, cra = prologue(caller)
        if cra is None or sp + cra + 4 > len(stack):
            break
        ra = struct.unpack_from('<I', stack, sp + cra)[0]
        sp += csize
        if not 0x100000 <= ra < 0x32D000:
            break
        chain.append((caller, ra))
    return chain


def walk(func, seconds=2.0, press=None):
    d = gdbg.Dbg()

    def act(d):
        if press:
            d.press(press.split('+'), 10, 10)
        time.sleep(seconds)
    res = d.trace_str(func, 'sp', action=act, n=SNAP, maxn=1)
    return [unwind(func, ra, st) for ra, st in res]


if __name__ == '__main__':
    a = sys.argv[1:]
    for chain in walk(int(a[0], 16), float(a[1]) if len(a) > 1 else 2.0, a[2] if len(a) > 2 else None):
        for f, ra in chain:
            print('func %08X   returns to %08X' % (f, ra))
