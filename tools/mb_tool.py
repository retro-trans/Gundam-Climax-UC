"""MB13CDVD archive tool (GAME.MB / STREAM.MB / TESTDATA.MB / MOVIE3.MB).

Format (little endian):
  0x00  char[8]  "MB13CDVD"
  0x08  u32      entry count
  0x0C  u32      end of table (0x18 + count*0x30)
  0x10  u32      data start (sector aligned, 0x800)
  0x14  char[4]  "ARCC"
  0x18  entry[count], 0x30 bytes each:
          char[32] name
          u32      sector  (relative to data start, 0x800 units)
          u32      size
          u32      0
          u32      0xFFFFFFFF

Usage:
  python mb_tool.py list  GAME.MB
  python mb_tool.py extract GAME.MB outdir [pattern]
  python mb_tool.py build orig.MB replacements_dir out.MB
"""
import fnmatch
import os
import struct
import sys

SECTOR = 0x800


def read_table(path):
    with open(path, 'rb') as f:
        head = f.read(0x18)
        assert head[:8] == b'MB13CDVD', 'not an MB13CDVD archive'
        count, end, data_start = struct.unpack_from('<3I', head, 8)
        tab = f.read(count * 0x30)
    entries = []
    for i in range(count):
        name, sec, size, z, ff = struct.unpack_from('<32s4I', tab, i * 0x30)
        entries.append({
            'index': i,
            'name': name.split(b'\0')[0].decode('ascii'),
            'sector': sec,
            'size': size,
            'u0': z,
            'u1': ff,
        })
    return {'count': count, 'end': end, 'data_start': data_start,
            'magic2': head[0x14:0x18], 'entries': entries}


def cmd_list(path):
    t = read_table(path)
    print('entries %d data_start 0x%X' % (t['count'], t['data_start']))
    for e in t['entries']:
        print('%5d %-32s sec=%7d size=%9d' % (e['index'], e['name'], e['sector'], e['size']))


def cmd_extract(path, outdir, pattern='*'):
    t = read_table(path)
    os.makedirs(outdir, exist_ok=True)
    n = 0
    with open(path, 'rb') as f:
        for e in t['entries']:
            if not fnmatch.fnmatch(e['name'], pattern):
                continue
            f.seek(t['data_start'] + e['sector'] * SECTOR)
            data = f.read(e['size'])
            with open(os.path.join(outdir, e['name']), 'wb') as o:
                o.write(data)
            n += 1
    print('extracted %d files' % n)


def cmd_build(orig, repl_dir, out):
    """Rebuild archive keeping entry order; files present in repl_dir replace originals.

    The archive keeps the same entry count and names; sectors are recomputed, so any
    in-game copy of sector numbers (e.g. inside the ELF) must be checked separately.
    """
    t = read_table(orig)
    with open(orig, 'rb') as f, open(out, 'wb') as o:
        f.seek(0)
        header = bytearray(f.read(t['data_start']))
        o.write(b'\0' * t['data_start'])
        sec = 0
        replaced = 0
        for e in t['entries']:
            rp = os.path.join(repl_dir, e['name'])
            if os.path.isfile(rp):
                data = open(rp, 'rb').read()
                replaced += 1
            else:
                f.seek(t['data_start'] + e['sector'] * SECTOR)
                data = f.read(e['size'])
            o.seek(t['data_start'] + sec * SECTOR)
            o.write(data)
            pad = (-len(data)) % SECTOR
            o.write(b'\0' * pad)
            struct.pack_into('<II', header, 0x18 + e['index'] * 0x30 + 32, sec, len(data))
            sec += (len(data) + SECTOR - 1) // SECTOR
        o.seek(0)
        o.write(header)
    print('built %s, %d replaced, %d sectors' % (out, replaced, sec))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == 'list':
        cmd_list(a[1])
    elif a[0] == 'extract':
        cmd_extract(a[1], a[2], a[3] if len(a) > 3 else '*')
    elif a[0] == 'build':
        cmd_build(a[1], a[2], a[3])
