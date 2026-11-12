"""GitHub social preview (1280x640) in the retro-trans style: game art panel left, title right.

The art panel is composed from the game's own title-screen textures (Gundam montage + logo), read from
your extracted game files; nothing is downloaded.

python tools/social_preview.py [out.png]      (default work/release/social-preview.png)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import xts_tool  # noqa: E402

FONT = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'NotoSansJP-VF.ttf')
TITLE_DIR = os.path.join(ROOT, 'work', 'source', 'fpk', 'saga_title0.fpk_')
W, H = 1280, 640
CREAM, BLUE, GOLD = (246, 238, 222), (122, 166, 232), (232, 184, 48)


def tex(xts, name):
    d = open(os.path.join(TITLE_DIR, xts), 'rb').read()
    cl, im = xts_tool.parse(d)
    i = next(x for x in im if x['name'] == name)
    return xts_tool.to_image(d, cl, i).transpose(Image.FLIP_TOP_BOTTOM).convert('RGBA')


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    # deep navy, lighter towards the upper middle (like the series' other previews)
    d = np.sqrt(((x - 760) / 900) ** 2 + ((y - 180) / 620) ** 2)
    t = np.clip(d, 0, 1)[..., None]
    top, bottom = np.array((22, 52, 112), np.float32), np.array((8, 18, 52), np.float32)
    img = top * (1 - t) + bottom * t
    noise = np.random.default_rng(7).normal(0, 2.2, img.shape[:2])[..., None]
    return Image.fromarray(np.clip(img + noise, 0, 255).astype(np.uint8), 'RGB')


def art_panel(pw, ph):
    """Portrait panel: the title montage cropped to the mobile suits, with the logo at the bottom."""
    bg = tex('title_01.xts', 'title_rend01')                       # 512x512
    crop = bg.crop((0, 90, 512, 430))                               # suits band
    scale = ph / crop.height
    art = crop.resize((int(crop.width * scale), ph), Image.LANCZOS)
    left = int(art.width * 0.62) - pw // 2                          # centre on the RX-78 / Zeta group
    left = max(0, min(art.width - pw, left))
    panel = Image.new('RGBA', (pw, ph), (0, 0, 0, 255))
    panel.alpha_composite(art.crop((left, 0, left + pw, ph)))
    # darken towards the bottom for the logo
    g = np.linspace(0, 1, ph)[:, None] ** 2.2
    shade = Image.fromarray((np.repeat(g, pw, 1) * 215).astype(np.uint8), 'L')
    panel.alpha_composite(Image.merge('RGBA', [Image.new('L', (pw, ph), 0)] * 3 + [shade]))
    logo = tex('title_02.xts', 'title_n01')
    logo.alpha_composite(tex('title_02.xts', 'title_n02'))
    bb = logo.getbbox()
    logo = logo.crop((bb[0], bb[1], bb[2], bb[3] - 13))             # drop the small Japanese line
    lw = int(pw * 0.9)
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    glow = logo.split()[3].filter(ImageFilter.GaussianBlur(6))
    halo = Image.merge('RGBA', [Image.new('L', logo.size, 0)] * 3 + [glow.point(lambda v: v * 0.8)])
    pos = ((pw - lw) // 2, ph - logo.height - 26)
    panel.alpha_composite(halo, pos)
    panel.alpha_composite(logo, pos)
    return panel


def main(out):
    img = background().convert('RGBA')
    # art panel with a light border and a soft shadow
    px, py, pw, ph = 62, 52, 392, 536
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((px - 2, py + 8, px + pw + 10, py + ph + 14), fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(img).rectangle((px - 4, py - 4, px + pw + 3, py + ph + 3), fill=(236, 236, 236, 255))
    img.alpha_composite(art_panel(pw, ph), (px, py))

    dr = ImageDraw.Draw(img)
    x0 = 520
    # platform line, letter-spaced
    f = font(30, 700)
    x = x0
    for ch in 'PLAYSTATION 2':
        dr.text((x, 120), ch, font=f, fill=BLUE, anchor='ls')
        x += dr.textlength(ch, font=f) + 11
    # title, fitted to the column
    lines = ['MOBILE SUIT', 'GUNDAM', 'CLIMAX U.C.']
    maxw = W - x0 - 60
    size = 120
    while True:
        f = font(size, 900)
        if max(dr.textlength(l, font=f) for l in lines) <= maxw:
            break
        size -= 2
    y = 150
    for k, l in enumerate(lines):
        fl = font(int(size * (0.62 if k == 0 else 1.0)), 900)
        asc = fl.getbbox('M')[3] - fl.getbbox('M')[1]
        y += asc
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x0 + 3, y + 5), l, font=fl, fill=(0, 0, 0, 120), anchor='ls')
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
        dr = ImageDraw.Draw(img)
        dr.text((x0, y), l, font=fl, fill=CREAM, anchor='ls')
        y += int(size * 0.22)
    y += 14
    dr.rectangle((x0 + 2, y, x0 + 262, y + 7), fill=GOLD)
    y += 62
    dr.text((x0, y), 'English translation patch', font=font(46, 700), fill=CREAM, anchor='ls')
    dr.text((W - 44, H - 40), 'retro-trans', font=font(32, 600), fill=BLUE, anchor='rs')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert('RGB').save(out)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'release', 'social-preview.png'))
