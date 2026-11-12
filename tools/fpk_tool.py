"""FPK container tool (used inside GAME.MB, nests recursively).

Format (little endian):
  0x00 char[4] "FPK\\0"
  0x04 u32     entry count
  0x08 u32     0x10 (header size)
  0x0C u32     data start (0x10 + count*0x50)
  0x10 entry[count], 0x50 bytes each:
         char[64] name
         u32      offset (relative to data start)
         u32      size
         u32      padded size (next offset = offset + padded)
         u32      0

Usage:
  python fpk_tool.py list file.fpk
  python fpk_tool.py extract file.fpk outdir          (one level)
  python fpk_tool.py extract_all srcdir outdir        (all .fpk recursively, nested -> name/)
"""
import os
import struct
import sys

ALIGN = 0x40


def parse(data):
    assert data[:4] == b'FPK\0', 'not FPK'
    count, hsize, dstart = struct.unpack_from('<3I', data, 4)
    ents = []
    for i in range(count):
        base = 0x10 + i * 0x50
        name = data[base:base + 64].split(b'\0')[0].decode('ascii', 'replace')
        off, size, padded, z = struct.unpack_from('<4I', data, base + 64)
        ents.append({'name': name, 'offset': off, 'size': size, 'padded': padded, 'u': z,
                     'data': data[dstart + off: dstart + off + size]})
    return {'count': count, 'hsize': hsize, 'dstart': dstart, 'entries': ents}


def build(entries, align=None):
    """entries: list of (name, bytes). Recomputes offsets; padding follows the original
    rule observed in files (padded size rounded up to 0x40 unless align given)."""
    a = align or ALIGN
    count = len(entries)
    dstart = 0x10 + count * 0x50
    head = bytearray(dstart)
    head[:4] = b'FPK\0'
    struct.pack_into('<3I', head, 4, count, 0x10, dstart)
    body = bytearray()
    for i, (name, d) in enumerate(entries):
        padded = (len(d) + a - 1) // a * a
        nb = name.encode('ascii')
        head[0x10 + i * 0x50: 0x10 + i * 0x50 + len(nb)] = nb
        struct.pack_into('<4I', head, 0x10 + i * 0x50 + 64, len(body), len(d), padded, 0)
        body += d + b'\0' * (padded - len(d))
    return bytes(head + body)


def extract_rec(data, outdir):
    os.makedirs(outdir, exist_ok=True)
    f = parse(data)
    n = 0
    for e in f['entries']:
        p = os.path.join(outdir, e['name'])
        if e['data'][:4] == b'FPK\0':
            n += extract_rec(e['data'], p + '_')
        else:
            with open(p, 'wb') as o:
                o.write(e['data'])
            n += 1
    return n


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'list':
        f = parse(open(a[1], 'rb').read())
        for e in f['entries']:
            print('%-40s off=%08X size=%8d padded=%8d %s' % (e['name'], e['offset'], e['size'], e['padded'],
                                                             'FPK' if e['data'][:4] == b'FPK\0' else ''))
    elif a[0] == 'extract':
        print(extract_rec(open(a[1], 'rb').read(), a[2]))
    elif a[0] == 'extract_all':
        tot = 0
        for fn in sorted(os.listdir(a[1])):
            if fn.endswith('.fpk'):
                d = open(os.path.join(a[1], fn), 'rb').read()
                if d[:4] == b'FPK\0':
                    tot += extract_rec(d, os.path.join(a[2], fn + '_'))
        print('files', tot)
