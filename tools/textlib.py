"""Shared text extraction / insertion logic for GAME.MB contents.

Logical paths: "<mb entry>[/<fpk member>...]", e.g. "briefingb.pack.fpk/BriefingB.bin".

Kinds of text slot (each occurrence = dict):
  c2b   : C2B table char[N] field          {path, off, max}
  rec   : fixed-record .inf string slot    {path, off, max}
  csv   : mission intro CSV line cell      {path, line, cell}
"""
import os
import re
import struct

import fpk_tool
import mb_tool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_MB = os.path.join(ROOT, 'work', 'source', 'iso', 'MB', 'GAME.MB')

# at least one full-width Japanese char (half-width kana alone is mostly float noise)
JP_RE = re.compile('[぀-ヿ㐀-鿿！-｠　-〿Ⅰ-ⅿ①-⓿]')

SKIP_EXT = ('.xts', '.px5', '.anm', '.ANM', '.mmd', '.gma', '.hg', '.trg', '.stc', '.rlt', '.hd', '.bd',
            '.idx', '.msi', '.env', '.drm', '.ico', '.adi', '.xls', '.gev', '.evl', '.sed', '.mef', '.mev',
            '.mbe', '.ufm', '.dat', '.sys', '.scc')
# developer-only files (never displayed)
SKIP_FILES = ('enum.csv', 'format.csv', 'enum.xls', 'format.xls',
              'card_info.inf')  # card_info handled by cards.py


def has_jp(s):
    return bool(JP_RE.search(s))


def iter_mb_files(mb=GAME_MB, base=0):
    """yield (logical path, bytes) for every leaf file, recursing into FPKs.
    base: byte offset of the archive inside the file (e.g. GAME.MB inside an ISO)."""
    with open(mb, 'rb') as f:
        f.seek(base)
        head = f.read(0x18)
        count = struct.unpack_from('<I', head, 8)[0]
        data_start = struct.unpack_from('<I', head, 0x10)[0]
        tab = f.read(count * 0x30)
        ents = []
        for i in range(count):
            name, sec, size = struct.unpack_from('<32s2I', tab, i * 0x30)
            ents.append({'name': name.split(b'\0')[0].decode('ascii'), 'sector': sec, 'size': size})
        for e in ents:
            f.seek(base + data_start + e['sector'] * 2048)
            data = f.read(e['size'])
            yield from _rec(e['name'], data)


def _rec(path, data):
    if data[:4] == b'FPK\0':
        for m in fpk_tool.parse(data)['entries']:
            yield from _rec(path + '/' + m['name'], m['data'])
    else:
        yield path, data


# ---------------------------------------------------------------- C2B
def c2b_tables(d):
    o = 0
    tabs = []
    while o + 0x60 <= len(d) and d[o:o + 4] == b'C2B\0':
        nf, nr, rs = struct.unpack_from('<3I', d, o + 0x54)
        fields = []
        fo = 0
        for i in range(nf):
            code = d[o + 0x60 + i * 8: o + 0x64 + i * 8].rstrip(b'\0')[::-1].decode('latin1')
            label = d[o + 0x64 + i * 8: o + 0x68 + i * 8].rstrip(b'\0')[::-1].decode('latin1')
            size = int(code[1:]) if code[1:].isdigit() else 4
            fields.append((code[0], size, fo, label))
            fo += size
        recs = o + 0x60 + nf * 8
        name = d[o + 0x24:o + 0x54].split(b'\0')[0].decode('cp932', 'replace')
        tabs.append({'off': o, 'name': name, 'nrec': nr, 'rsize': rs, 'fields': fields, 'recs': recs})
        if fo != rs:
            raise ValueError('C2B field sizes %d != record size %d' % (fo, rs))
        o = recs + nr * rs
    return tabs


def is_c2b(d):
    return d[:4] == b'C2B\0'


def extract_c2b(path, d):
    out = []
    for ti, t in enumerate(c2b_tables(d)):
        for r in range(t['nrec']):
            base = t['recs'] + r * t['rsize']
            for fi, (ty, size, fo, label) in enumerate(t['fields']):
                if ty != 'C':
                    continue
                raw = d[base + fo: base + fo + size].split(b'\0')[0]
                s = raw.decode('cp932', 'replace')
                if raw and has_jp(s):
                    out.append({'kind': 'c2b', 'path': path, 'off': base + fo, 'max': size - 1, 'jp': s,
                                'ctx': '%s#%d rec%d f%d' % (t['name'], ti, r, fi)})
    return out


# ---------------------------------------------------------------- fixed records
def is_fixed_rec(d):
    if len(d) < 8:
        return None
    n = struct.unpack_from('<I', d)[0]
    if n == 0 or n > 100000 or (len(d) - 4) % n:
        return None
    return n, (len(d) - 4) // n


def _strings_in(rec):
    """(start, end) of null-terminated strings with JP or ASCII letters that start after a 0."""
    res = []
    i = 0
    n = len(rec)
    while i < n:
        if rec[i] and (i == 0 or rec[i - 1] == 0):
            j = i
            while j < n and rec[j]:
                j += 1
            raw = rec[i:j]
            try:
                s = raw.decode('cp932')
            except UnicodeDecodeError:
                s = ''
            if s and (has_jp(s) or re.fullmatch(r'[ -~]{2,}', s)):
                res.append((i, j, s))
            i = j
        else:
            i += 1
    return res


def extract_fixed(path, d):
    fr = is_fixed_rec(d)
    if not fr:
        return []
    n, rs = fr
    recs = [d[4 + k * rs: 4 + (k + 1) * rs] for k in range(n)]
    per = [_strings_in(r) for r in recs]
    starts = sorted({s for p in per for (s, e, t) in p if has_jp(t)})
    if not starts:
        return []
    # slot limit: next start, or first non-zero byte (not part of the string at s) in any record
    limits = {}
    for s in starts:
        lim = min([x for x in starts if x > s] + [rs])
        for r in recs:
            j = s
            while j < rs and r[j]:
                j += 1
            k = j
            while k < lim and r[k] == 0:
                k += 1
            lim = min(lim, k) if k < lim else lim
        limits[s] = lim
    out = []
    for k, p in enumerate(per):
        for (s, e, t) in p:
            if s in limits and has_jp(t):
                out.append({'kind': 'rec', 'path': path, 'off': 4 + k * rs + s, 'max': limits[s] - s - 1,
                            'jp': t, 'ctx': 'rec%d +0x%X' % (k, s)})
    return out


# ---------------------------------------------------------------- mission intro CSV
CSV_RE = re.compile(r'mp_(cn|pr)_.*\.inf$')


def extract_csv(path, d):
    out = []
    text = d.decode('cp932')
    for li, line in enumerate(text.split('\r\n')):
        cells = line.split(',')
        for ci, c in enumerate(cells):
            if has_jp(c) and not c.lstrip().startswith('//'):   # '//' cells are dev comments
                out.append({'kind': 'csv', 'path': path, 'line': li, 'cell': ci, 'jp': c,
                            'ctx': 'line%d cell%d' % (li, ci)})
    return out


# ---------------------------------------------------------------- quoted CSV (one message per record)
QCSV_FILES = ('mcd_msg_data.csv',)   # memory card system messages; multi-line cells are "quoted"


def qcsv_records(d):
    import csv
    import io
    return list(csv.reader(io.StringIO(d.decode('cp932'), newline='')))


def extract_qcsv(path, d):
    out = []
    for ri, rec in enumerate(qcsv_records(d)):
        for ci, c in enumerate(rec):
            if has_jp(c):
                out.append({'kind': 'qcsv', 'path': path, 'rec': ri, 'cell': ci, 'jp': c,
                            'ctx': 'record%d' % ri})
    return out


def extract_file(path, d):
    base = path.rsplit('/', 1)[-1]
    if base in QCSV_FILES:
        return extract_qcsv(path, d)
    if base.endswith(SKIP_EXT) or base in SKIP_FILES:
        return []
    if CSV_RE.search(base.lower()):
        return extract_csv(path, d)
    if is_c2b(d):
        return extract_c2b(path, d)
    if base.endswith('.inf') or base.endswith('.bin'):
        return extract_fixed(path, d)
    return []
