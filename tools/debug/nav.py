"""Navigation helpers for in-game checks (emulator already running).

python nav.py menu                       fresh boot -> title menu (installs the pad hook)
python nav.py press b1,b2,... [gap_s]    press buttons with a real-time gap (default 1.5 s)
python nav.py wait <seconds>
python nav.py grid <out.png> [n] [gap_s] screenshot series -> one contact sheet (3 per row)
python nav.py shot <out.png>
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import boot_to  # noqa: E402
from gdbg import Dbg  # noqa: E402
from pine import Pine  # noqa: E402


def dbg():
    return Dbg(Pine())


def menu():
    p = Pine()
    boot_to.wait_game(p)
    boot_to.wait_hook_safe(p)
    time.sleep(3)
    d = Dbg(p)
    d.install()
    time.sleep(12)
    d.press(['start'], 10, 10)
    time.sleep(5)
    d.press(['start'], 10, 10)
    time.sleep(4)
    return d


def press(seq, gap=1.5):
    d = dbg()
    for b in seq.split(','):
        b = b.strip()
        if b:
            d.press(b.split('+'), 10, 10)
            time.sleep(gap)


def grid(out, n=6, gap=2.5):
    from PIL import Image
    d = dbg()
    tmp = []
    for i in range(n):
        f = out[:-4] + '_%d.png' % i
        for _ in range(3):
            try:
                d.shot(f)
                break
            except Exception:
                time.sleep(1)
        tmp.append(f)
        if i < n - 1:
            time.sleep(gap)
    cols = 3
    rows = -(-n // cols)
    sheet = Image.new('RGB', (320 * cols, 240 * rows))
    for k, f in enumerate(tmp):
        if os.path.exists(f):
            sheet.paste(Image.open(f).resize((320, 240)), (320 * (k % cols), 240 * (k // cols)))
    sheet.save(out)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'menu':
        menu()
    elif a[0] == 'press':
        press(a[1], float(a[2]) if len(a) > 2 else 1.5)
    elif a[0] == 'wait':
        time.sleep(float(a[1]))
    elif a[0] == 'grid':
        grid(a[1], int(a[2]) if len(a) > 2 else 6, float(a[3]) if len(a) > 3 else 2.5)
    elif a[0] == 'shot':
        dbg().shot(a[1])
