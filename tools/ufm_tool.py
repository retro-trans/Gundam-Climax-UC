"""s18rm04.ufm font tool.

Format:
  0x00 "FM" 0x10 0x3F 0x5A(=bytes per glyph) ...  (16-byte header)
  0x10 u16 map[84*96]   index = (jis_row-0x21)*96 + (jis_col-0x20)   (game code at 0x198260)
          value 0x8000|glyph, 0 = no glyph
          SJIS text is converted to JIS first (0x198350); single-byte ASCII b -> JIS 0x29b,
          half-width kana 0xA1..0xDF -> JIS 0x29(b-0x80+... ) see sjis_to_jis().
  0x3F10 glyph[n], 90 bytes each: 20 wide x 18 tall, 2bpp, MSB-first,
          row-major (5 bytes per row), values 0..3 (3 = solid)

Usage:
  python ufm_tool.py sheet font.ufm out.png [first_code_hex count]
  python ufm_tool.py render font.ufm "text" out.png
"""
import struct
import sys

from PIL import Image

W, H, GB, MAP, GLYPHS = 20, 18, 90, 0x10, 0x3F10


def sjis_to_jis(code):
    """Mirror of the game's conversion at 0x198350. code: 1-byte (<0x100) or 2-byte SJIS."""
    if code < 0x100:
        if 0x21 <= code < 0x80:
            return 0x2900 + code
        if 0xA1 <= code < 0x100:
            return 0x2980 + code      # game: (b + 0x2980) & 0xFFFF
        return 0x2121
    lead, tr = code >> 8, code & 0xFF
    hi = ((lead - 0xC1) if lead >= 0xE0 else (lead - 0x81)) << 9
    if tr < 0x9F:
        return (hi + 0x2100 + tr - (0x1F if tr < 0x7F else 0x20)) & 0xFFFF
    return (hi + 0x2200 + tr - 0x7E) & 0xFFFF


def map_index(jis):
    return ((jis >> 8) - 0x21) * 96 + ((jis & 0xFF) - 0x20)


class UFM:
    def __init__(self, path):
        self.data = bytearray(open(path, 'rb').read())
        self.count = (len(self.data) - GLYPHS) // GB

    def index_jis(self, jis):
        i = map_index(jis)
        if not 0 <= i < 84 * 96:
            return None
        v = struct.unpack_from('<H', self.data, MAP + 2 * i)[0]
        return (v & 0x7FFF) if v & 0x8000 else None

    def index(self, code):
        """code: SJIS (1 or 2 bytes) as the game sees it."""
        return self.index_jis(sjis_to_jis(code))

    def set_index_jis(self, jis, glyph):
        struct.pack_into('<H', self.data, MAP + 2 * map_index(jis), 0x8000 | glyph)

    def get_pixels(self, g):
        b = self.data[GLYPHS + g * GB: GLYPHS + (g + 1) * GB]
        return [(b[k // 4] >> (6 - 2 * (k % 4))) & 3 for k in range(W * H)]

    def set_pixels(self, g, px):
        out = bytearray(GB)
        for k, v in enumerate(px):
            out[k // 4] |= (v & 3) << (6 - 2 * (k % 4))
        self.data[GLYPHS + g * GB: GLYPHS + (g + 1) * GB] = out

    def image(self, g):
        im = Image.new('L', (W, H))
        im.putdata([v * 85 for v in self.get_pixels(g)])
        return im

    def save(self, path):
        open(path, 'wb').write(self.data)


def main():
    a = sys.argv[1:]
    f = UFM(a[1])
    if a[0] == 'sheet':
        first = int(a[3], 16) if len(a) > 3 else 0
        n = int(a[4]) if len(a) > 4 else f.count - first
        cols = 64
        sh = Image.new('L', (cols * (W + 1), ((n + cols - 1) // cols) * (H + 1)), 30)
        for i in range(n):
            sh.paste(f.image(first + i), ((i % cols) * (W + 1), (i // cols) * (H + 1)))
        sh.save(a[2])
    elif a[0] == 'render':
        t = a[2].encode('cp932')
        im = Image.new('L', (W * len(t), H))
        x = i = 0
        while i < len(t):
            if t[i] >= 0x81 and not 0xA0 <= t[i] < 0xE0:
                c = t[i] << 8 | t[i + 1]
                i += 2
            else:
                c = t[i]
                i += 1
            g = f.index(c)
            if g is not None:
                im.paste(f.image(g), (x, 0))
            x += W
        im.crop((0, 0, x, H)).resize((x * 3, H * 3), Image.NEAREST).save(a[3])


if __name__ == '__main__':
    main()
