"""PCSX2 savestate (.p2s, uncompressed zip) reader + screenshot helper.

Usage:
  python savestate.py shot <out.png> [slot]       save slot via PINE, extract Screenshot.png
  python savestate.py ram <state.p2s> <out.bin>   dump EE RAM (32 MB)
  python savestate.py diff <a.p2s> <b.p2s> [lo hi] list changed words in EE RAM
"""
import glob
import os
import struct
import sys
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SSDIR = os.path.join(ROOT, 'work', 'emulator', 'pcsx2', 'sstates')


def slot_path(slot):
    g = glob.glob(os.path.join(SSDIR, 'SLPS-25627 (*).%02d.p2s' % slot))
    return max(g, key=os.path.getmtime) if g else None


def ee_ram(path):
    with zipfile.ZipFile(path) as z:
        return z.read('eeMemory.bin')


def screenshot(path):
    with zipfile.ZipFile(path) as z:
        return z.read('Screenshot.png')


def shot(out, slot=9, pine=None):
    sys.path.insert(0, os.path.dirname(__file__))
    from pine import Pine
    p = pine or Pine()
    old_m = time.time() - 0.5
    p.save_state(slot)
    for _ in range(100):
        sp = slot_path(slot)
        if sp and os.path.getmtime(sp) > old_m:
            try:
                data = screenshot(sp)
                open(out, 'wb').write(data)
                return sp
            except Exception:
                pass
        time.sleep(0.2)
    raise RuntimeError('savestate not written')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'shot':
        print(shot(a[1], int(a[2]) if len(a) > 2 else 9))
    elif a[0] == 'ram':
        open(a[2], 'wb').write(ee_ram(a[1]))
    elif a[0] == 'diff':
        A, B = ee_ram(a[1]), ee_ram(a[2])
        lo = int(a[3], 16) if len(a) > 3 else 0
        hi = int(a[4], 16) if len(a) > 4 else len(A)
        for o in range(lo, hi, 4):
            x, y = A[o:o + 4], B[o:o + 4]
            if x != y:
                print('%08X %08X -> %08X' % (o, struct.unpack('<I', x)[0], struct.unpack('<I', y)[0]))
