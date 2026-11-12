"""XTS texture container -> PNG.

Layout (little endian), decoded from base_font01.xts and mp_cn_*.xts:
  0x00 "XTSAG\\0"  0x06 u16 version(1)  0x0C u16 clut_count  0x0E u16 image_count
  0x10 clut[clut_count]   { char[32] name, u32 off, u32 size, u16 w, u16 h, u32 bpp(32) }   0x30 bytes
  then image[image_count] { char[32] name, char[32] clut name, u32 off, u32 size,
                            u16 w, u16 h, u32 bpp }                                          0x50 bytes
  Offsets are from the file start. 4/8 bpp images use the clut named in their entry. 8-bit CLUTs use the PS2 CSM1 order (entries 8..15 <-> 16..23 in each 32 block).
  Alpha is PS2 style (0x80 = opaque).

Usage:
  python xts_tool.py info file.xts
  python xts_tool.py png file.xts outdir
  python xts_tool.py dumpdir <dir> <outdir>   (all .xts below dir)
"""
import os
import struct
import sys

from PIL import Image


def parse(d):
    assert d[:4] == b'XTSA', 'not XTS'   # variants XTSAA/AC/AF/AG share the layout
    nclut, nimg = struct.unpack_from('<HH', d, 0x0C)
    p = 0x10
    cluts, imgs = [], []
    for _ in range(nclut):
        name = d[p:p + 0x20].split(b'\0')[0].decode('latin1')
        off, size, w, h, bpp = struct.unpack_from('<IIHHI', d, p + 0x20)
        cluts.append({'off': off, 'size': size, 'w': w, 'h': h, 'bpp': bpp, 'name': name})
        p += 0x30
    for _ in range(nimg):
        name = d[p:p + 0x20].split(b'\0')[0].decode('latin1')
        cname = d[p + 0x20:p + 0x40].split(b'\0')[0].decode('latin1')
        off, size, w, h, bpp = struct.unpack_from('<IIHHI', d, p + 0x40)
        imgs.append({'off': off, 'size': size, 'w': w, 'h': h, 'bpp': bpp, 'name': name, 'clut': cname,
                     'entry': p})
        p += 0x50
    return cluts, imgs


def _alpha(a):
    return min(255, a * 2)


def clut_colors(d, c):
    raw = d[c['off']:c['off'] + c['size']]
    n = c['size'] // 4
    cols = [tuple(raw[i * 4:i * 4 + 4]) for i in range(n)]
    if n == 256:  # CSM1 unswizzle
        out = list(cols)
        for blk in range(0, 256, 32):
            out[blk + 8:blk + 16], out[blk + 16:blk + 24] = cols[blk + 16:blk + 24], cols[blk + 8:blk + 16]
        cols = out
    return [(r, g, b, _alpha(a)) for r, g, b, a in cols]


def to_image(d, cluts, im, idx=0):
    w, h, bpp = im['w'], im['h'], im['bpp']
    raw = d[im['off']:im['off'] + im['size']]
    if bpp == 24:
        return Image.frombytes('RGB', (w, h), raw[:w * h * 3])
    if bpp == 32:
        px = bytearray(raw[:w * h * 4])
        for i in range(3, len(px), 4):
            px[i] = _alpha(px[i])
        return Image.frombytes('RGBA', (w, h), bytes(px))
    c = next(c for c in cluts if c['name'] == im['clut'])
    pal = clut_colors(d, c)
    out = Image.new('RGBA', (w, h))
    if bpp == 8:
        out.putdata([pal[b] for b in raw[:w * h]])
    elif bpp == 4:
        px = []
        for b in raw[:w * h // 2]:
            px.append(pal[b & 15])
            px.append(pal[b >> 4])
        out.putdata(px)
    else:
        raise ValueError('bpp %d' % bpp)
    return out


def _ps2_alpha(a):
    return min(0x80, (a + 1) // 2)


def encode_image(d, name, img):
    """Return a copy of XTS bytes d with image `name` replaced by PIL image `img` (raw orientation,
    i.e. as to_image() returns it - the game draws these flipped). Size, bpp and file layout are
    unchanged. 4/8 bpp: the image is quantized to 16/256 colours (with alpha) and its own CLUT is
    rewritten (only the CLUT named by the image; shared CLUTs are refused). 32 bpp: written directly."""
    d = bytearray(d)
    cluts, imgs = parse(d)
    im = next(x for x in imgs if x['name'] == name)
    w, h, bpp = im['w'], im['h'], im['bpp']
    img = img.convert('RGBA')
    if img.size != (w, h):
        raise ValueError('%s: size %s, expected %dx%d' % (name, img.size, w, h))
    if bpp == 32:
        px = bytearray(img.tobytes())
        for i in range(3, len(px), 4):
            px[i] = _ps2_alpha(px[i])
        d[im['off']:im['off'] + w * h * 4] = px
        return bytes(d)
    users = [x for x in imgs if x['clut'] == im['clut']]
    if len(users) > 1:
        raise ValueError('%s: CLUT %s shared by %d images' % (name, im['clut'], len(users)))
    c = next(c for c in cluts if c['name'] == im['clut'])
    n = 16 if bpp == 4 else 256
    q = img.quantize(colors=n, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = q.getpalette('RGBA')[:n * 4]
    pal += [0] * (n * 4 - len(pal))
    cols = [tuple(pal[i * 4:i * 4 + 4]) for i in range(n)]
    if n == 256:   # CSM1 order on disc
        out = list(cols)
        for blk in range(0, 256, 32):
            out[blk + 8:blk + 16], out[blk + 16:blk + 24] = cols[blk + 16:blk + 24], cols[blk + 8:blk + 16]
        cols = out
    raw = bytearray()
    for r, g, b, a in cols:
        raw += bytes((r, g, b, _ps2_alpha(a)))
    if len(raw) != c['size']:
        raise ValueError('%s: CLUT size %d != %d' % (name, len(raw), c['size']))
    d[c['off']:c['off'] + c['size']] = raw
    idx = q.tobytes()
    if bpp == 8:
        d[im['off']:im['off'] + w * h] = idx
    else:
        packed = bytearray(w * h // 2)
        for i in range(0, w * h, 2):
            packed[i // 2] = (idx[i] & 15) | ((idx[i + 1] & 15) << 4)
        d[im['off']:im['off'] + len(packed)] = packed
    return bytes(d)


def to_pngs(path, outdir):
    d = open(path, 'rb').read()
    cluts, imgs = parse(d)
    os.makedirs(outdir, exist_ok=True)
    base = os.path.basename(path)[:-4]
    res = []
    for i, im in enumerate(imgs):
        try:
            img = to_image(d, cluts, im, i)
        except Exception as e:  # noqa
            res.append('%s: %s' % (im['name'], e))
            continue
        fn = os.path.join(outdir, '%s__%02d_%s.png' % (base, i, im['name'] or 'img'))
        img.save(fn)
        res.append(fn)
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'info':
        c, i = parse(open(a[1], 'rb').read())
        print('cluts', c)
        print('images', i)
    elif a[0] == 'png':
        print('\n'.join(to_pngs(a[1], a[2])))
    elif a[0] == 'dumpdir':
        n = 0
        for r, _, fs in os.walk(a[1]):
            for f in fs:
                if f.lower().endswith('.xts'):
                    rel = os.path.relpath(r, a[1])
                    to_pngs(os.path.join(r, f), os.path.join(a[2], rel))
                    n += 1
        print('xts files', n)
