"""Keep old builds as xdelta patches (AGENTS.md: only the latest ISO is kept; older versions as xdelta,
at most 10).

Patches are made against the original Japanese ISO, so any version can be rebuilt from it alone.
xdelta3: work/bin/xdelta3/xdelta3-3.1.0-x86_64.exe (official release, github.com/jmacd/xdelta-gpl v3.1.0).

python tools/patches.py make   <version>   -> work/output/patches/Gundam_Climax_UC_EN_v<version>.xdelta
python tools/patches.py verify <version>   decode to a temp file, compare SHA-1 with the ISO
python tools/patches.py retire <version>   make + verify, then delete that version's ISO
python tools/patches.py prune              keep the 10 newest patches
"""
import glob
import hashlib
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XD = os.path.join(ROOT, 'work', 'bin', 'xdelta3', 'xdelta3-3.1.0-x86_64.exe')
SRC = os.path.join(ROOT, 'Mobile Suit Gundam - Climax U.C. (Japan).iso')
OUT = os.path.join(ROOT, 'work', 'output')
PD = os.path.join(OUT, 'patches')
KEEP = 10


def iso(v):
    return os.path.join(OUT, 'Gundam_Climax_UC_EN_v%s.iso' % v)


def patch(v):
    return os.path.join(PD, 'Gundam_Climax_UC_EN_v%s.xdelta' % v)


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def make(v):
    os.makedirs(PD, exist_ok=True)
    subprocess.check_call([XD, '-e', '-9', '-f', '-B', '268435456', '-s', SRC, iso(v), patch(v)])
    print('patch', patch(v), os.path.getsize(patch(v)))


def verify(v):
    fd, tmp = tempfile.mkstemp(suffix='.iso', dir=OUT)
    os.close(fd)
    try:
        subprocess.check_call([XD, '-d', '-f', '-B', '268435456', '-s', SRC, patch(v), tmp])
        a, b = sha1(tmp), sha1(iso(v))
        print('decoded', a, '\niso    ', b)
        return a == b
    finally:
        os.remove(tmp)


def prune():
    ps = sorted(glob.glob(os.path.join(PD, '*.xdelta')), key=os.path.getmtime)
    for p in ps[:-KEEP]:
        print('remove', p)
        os.remove(p)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make':
        make(sys.argv[2])
    elif cmd == 'verify':
        sys.exit(0 if verify(sys.argv[2]) else 1)
    elif cmd == 'retire':
        v = sys.argv[2]
        if not os.path.exists(patch(v)):
            make(v)
        if not verify(v):
            sys.exit('verify failed; ISO kept')
        os.remove(iso(v))
        print('removed', iso(v))
        prune()
    elif cmd == 'prune':
        prune()
