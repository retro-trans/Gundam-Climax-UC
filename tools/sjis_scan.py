"""Scan binary files for Shift-JIS text runs (full-width and half-width katakana + ASCII).

Usage: python sjis_scan.py <out.tsv> <file_or_dir>... [--min N] [--dump]
Writes per-file counts (and with --dump every run) to out.tsv in UTF-8.
"""
import os
import sys


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def is_trail(b):
    return 0x40 <= b <= 0xFC and b != 0x7F


def scan(data, min_jp=2):
    """Yield (offset, bytes) for runs holding >= min_jp double-byte chars."""
    i, n = 0, len(data)
    start, jp = None, 0
    while i < n:
        b = data[i]
        ok = 0
        if is_lead(b) and i + 1 < n and is_trail(data[i + 1]):
            ok = 2
        elif 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF or b in (0x0A, 0x0D):
            ok = 1
        if ok:
            if start is None:
                start, jp = i, 0
            if ok == 2:
                jp += 1
            i += ok
        else:
            if start is not None and jp >= min_jp:
                yield start, data[start:i]
            start = None
            i += 1
    if start is not None and jp >= min_jp:
        yield start, data[start:i]


def main():
    args = sys.argv[1:]
    out = args.pop(0)
    min_jp = 2
    dump = False
    if '--min' in args:
        k = args.index('--min'); min_jp = int(args[k + 1]); del args[k:k + 2]
    if '--dump' in args:
        args.remove('--dump'); dump = True
    files = []
    for p in args:
        if os.path.isdir(p):
            for r, _, fs in os.walk(p):
                files += [os.path.join(r, f) for f in sorted(fs)]
        else:
            files.append(p)
    with open(out, 'w', encoding='utf-8') as o:
        for fp in files:
            data = open(fp, 'rb').read()
            runs = list(scan(data, min_jp))
            if not runs:
                continue
            o.write('%s\t%d\t%d\n' % (fp, len(runs), sum(len(r) for _, r in runs)))
            if dump:
                for off, r in runs:
                    o.write('  %08X\t%s\n' % (off, r.decode('cp932', 'replace').replace('\n', '\\n')))


if __name__ == '__main__':
    main()
