"""Draw English into textures (work/translation/en/textures.json) and patch them into GAME.MB.

Text is drawn with the game's own font (the built VWF s18rm04.ufm: same letters as the in-game
text). Textures are 4-bit with their own 16-colour CLUT; xts_tool.encode_image re-quantizes.
Textures are stored upside down (the game draws them flipped): images are composed upright and
flipped back before encoding.

Styles
  title_sub  256x64 title-menu description: "< Mode >" header + one description line, light grey;
             smooth font drawn half-width (the game stretches it 2x horizontally)
             on black (as the original).
  label3     64x64 briefing labels: three rows of grey text with alpha.
  plate      128x32 skill plates (families AS / PS / MS): background = per-pixel median of every
             plate of the family (removes the varying Japanese name, keeps gradient + tag), name in
             bold white with a dark drop shadow, centred. Falls back to regular weight / tighter
             spacing when the bold name is wider than the plate.

Insertion: every extracted copy of a texture file (same name, same bytes) under work/source/fpk
belongs to one GAME.MB entry (first path component); the original XTS bytes are replaced in that
entry wherever they occur (same size, so offsets and FPK tables are untouched).

python tools/tex_make.py preview     -> work/translation/en/tex/*.png + contact sheet
python tools/tex_make.py check       -> fit report only
"""
import collections
import hashlib
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import ufm_tool  # noqa: E402
import vwf  # noqa: E402
import xts_tool  # noqa: E402

FPK = os.path.join(ROOT, 'work', 'source', 'fpk')
GAME = os.path.join(ROOT, 'work', 'source', 'game')
JOBS = os.path.join(ROOT, 'work', 'translation', 'en', 'textures.json')
PREV = os.path.join(ROOT, 'work', 'translation', 'en', 'tex')

_F = None


def font():
    global _F
    if _F is None:
        data, tab = vwf.build_font(os.path.join(GAME, 's18rm04.ufm'))
        f = ufm_tool.UFM.__new__(ufm_tool.UFM)
        f.data = bytearray(data)
        _F = (f, tab)
    return _F


def glyph(ch, bold):
    f, tab = font()
    g = f.index(ord(ch))
    W, H = ufm_tool.W, ufm_tool.H
    if g is None:
        return None, tab[ord(ch)] if ord(ch) < 256 else 10
    px = f.get_pixels(g)
    m = [[px[y * W + x] for x in range(W)] for y in range(H)]
    adv = tab[ord(ch)]
    if bold and ch != ' ':
        for y in range(H):
            row = m[y][:]
            for x in range(1, W):
                m[y][x] = max(row[x], row[x - 1])
        adv += 1
    return m, adv


def measure(text, bold=False, spacing=0):
    return sum(glyph(c, bold)[1] + spacing for c in text) - (spacing if text else 0)


def draw(img, x, y, text, colour, bold=False, spacing=0, shadow=None, levels=(0, 0.55, 1.0)):
    """Draw text into an upright RGBA image. colour: RGB; alpha from glyph level (0..2)."""
    pxl = img.load()
    W, H = ufm_tool.W, ufm_tool.H

    def put(px_, py_, rgb, a):
        if 0 <= px_ < img.width and 0 <= py_ < img.height and a > 0:
            r, g, b, a0 = pxl[px_, py_]
            k = a
            pxl[px_, py_] = (int(r * (1 - k) + rgb[0] * k), int(g * (1 - k) + rgb[1] * k),
                             int(b * (1 - k) + rgb[2] * k), max(a0, int(255 * k)))
    for layer in ([shadow] if shadow else []) + [None]:
        cx = x
        for ch in text:
            m, adv = glyph(ch, bold)
            if m and ch != ' ':   # the game never draws the space glyph (it has a baseline pixel row)
                for gy in range(H):
                    for gx in range(W):
                        v = m[gy][gx]
                        if not v:
                            continue
                        if layer:
                            dx, dy, rgb = layer
                            put(cx + gx + dx, y + gy + dy, rgb, levels[v] * 0.9)
                        else:
                            put(cx + gx, y + gy, colour, levels[v])
            cx += adv + spacing


def load(xts, image):
    d = open(os.path.join(FPK, xts), 'rb').read()
    cl, ims = xts_tool.parse(d)
    im = next(x for x in ims if x['name'] == image)
    return d, xts_tool.to_image(d, cl, im).convert('RGBA')


_MED = {}
NAME_ROWS_RAW = (1, 19)   # plate rows (raw = upside-down orientation) that hold the skill name
TEXT_DELTA = 28           # brightness difference from the row's background that counts as text


def family_background(fam):
    if fam not in _MED:
        pat = {'AS': 'skill_panel.fpk_/AS_*.xts', 'PS': 'skill_panel.fpk_/PS_*.xts',
               'MS': 'msskill_panel.fpk_/MS_*.xts'}[fam]
        arrs = []
        for p in sorted(glob.glob(os.path.join(FPK, pat))):
            d = open(p, 'rb').read()
            cl, ims = xts_tool.parse(d)
            arrs.append(np.array(xts_tool.to_image(d, cl, ims[0]).convert('RGBA')).astype(np.float32))
        # Background reconstruction. In each plate, pixels of the name area whose brightness is far
        # from that row's typical background are text (white strokes or dark shadow). Every
        # background pixel is the median over the plates where it is NOT text; the tag area
        # (PASSIVE / ACTIVE / MS SKILL) is outside the name area and taken as a plain median.
        A = np.stack(arrs)                                   # n, h, w, 4 (raw orientation)
        n, h, w, _ = A.shape
        lum = A[..., :3].mean(axis=3)
        r0, r1 = NAME_ROWS_RAW
        text = np.zeros((n, h, w), bool)
        for k in range(n):
            for y in range(r0, r1):
                row = lum[k, y, 2:w - 2]
                ref = np.median(row)
                text[k, y, 2:w - 2] = np.abs(row - ref) > TEXT_DELTA
        # grow the mask by 1 px so anti-aliased edges go too
        g = text.copy()
        g[:, 1:, :] |= text[:, :-1, :]
        g[:, :-1, :] |= text[:, 1:, :]
        g[:, :, 1:] |= text[:, :, :-1]
        g[:, :, :-1] |= text[:, :, 1:]
        out = np.median(A, axis=0)
        for y in range(r0, r1):
            for x in range(w):
                ok = ~g[:, y, x]
                if ok.any():
                    out[y, x] = np.median(A[ok, y, x], axis=0)
                else:   # every plate has ink here: interpolate from the row's clean pixels
                    clean = [np.median(A[~g[:, y, xx], y, xx], axis=0) for xx in range(w) if (~g[:, y, xx]).any()]
                    out[y, x] = np.median(np.array(clean), axis=0) if clean else out[y, x]
        # the plate background is a vertical gradient: flatten each name row (inside the 3 px border)
        for y in range(r0, r1):
            out[y, 3:w - 3] = np.median(out[y, 3:w - 3], axis=0)
        _MED[fam] = Image.fromarray(out.round().astype(np.uint8), 'RGBA').transpose(Image.FLIP_TOP_BOTTOM)
    return _MED[fam].copy()


def _lum(p):
    return (p[0] + p[1] + p[2]) / 3.0


def inpaint(img, mask):
    """Onion-peel fill: masked pixels take the mean of their known 8-neighbours, layer by layer."""
    px = img.load()
    w, h = img.size
    todo = {(x, y) for (x, y) in mask}
    while todo:
        layer = {}
        for (x, y) in todo:
            nb = [px[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  if (dx or dy) and 0 <= x + dx < w and 0 <= y + dy < h and (x + dx, y + dy) not in todo]
            if nb:
                layer[(x, y)] = tuple(int(round(sum(c[i] for c in nb) / len(nb))) for i in range(4))
        if not layer:
            break
        for k, v in layer.items():
            px[k] = v
        todo -= set(layer)


def draw_outlined(img, x, y, text, fill, outline, bold=True):
    """Text with a 1 px outline (8 directions), as the original stat captions."""
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                draw(img, x + dx, y + dy, text, outline, bold=bold, levels=(0, 1.0, 1.0))
    draw(img, x, y, text, fill, bold=bold, levels=(0, 0.7, 1.0))


STAT_TERMS = {'armor': 'Defense', 'cp': 'Condition Pts', 'infighting': 'Melee',
              'mainweapon': 'Shooting', 'mobility': 'Mobility', 'nt': 'Newtype'}


def _fit(text, avail):
    for bold, sp in ((True, 0), (False, 0), (False, -1)):
        w = measure(text, bold, sp)
        if w <= avail:
            return bold, sp, w
    return False, -1, measure(text, False, -1)


def render_stat(job, up):
    """Stat labels in three designs (see module notes in docs/textures.md)."""
    probs = []
    img = up.copy()
    px = img.load()
    w, h = img.size
    term = job.get('en') or STAT_TERMS[job['image']]
    st = job['style']
    if st == 'stat_result':        # Japanese only, right-aligned, grey + white outline, speed lines
        cols = [x for x in range(w) for y in range(h) if px[x, y][3] > 150 and _lum(px[x, y]) < 120]
        x0 = min(cols) - 2
        right = max(cols) + 1
        bold, sp, tw = _fit(term, w - 4)
        x0 = min(x0, right - tw - 2)
        for x in range(max(0, x0), w):
            for y in range(h):
                px[x, y] = (255, 255, 255, 0)
        draw_outlined(img, right - tw, 8, term, (70, 70, 70), (255, 255, 255), bold=bold)
        return img, probs
    if st == 'stat_menu':          # small English word + large Japanese gloss on a gradient band
        eng = [x for x in range(w) for y in range(h) if px[x, y][3] > 200 and _lum(px[x, y]) < 20]
        er = max(eng) + 1
        mask = set()
        for x in range(er + 1, w):
            for y in range(h):
                p = px[x, y]
                if p[3] > 200 and _lum(p) < 190:
                    mask.add((x, y))
        grown = set()
        for (x, y) in mask:
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if er < x + dx < w and 0 <= y + dy < h:
                        grown.add((x + dx, y + dy))
        right = max(x for x, _ in mask) + 1
        inpaint(img, grown)
        bold, sp, tw = _fit(term, right - er - 3)
        if tw > right - er - 3:
            probs.append('too wide: %s' % term)
        draw_outlined(img, right - tw, 12, term, (90, 90, 90), (250, 250, 250), bold=bold)
        return img, probs
    if st == 'stat_pause':         # big outlined English word, small caption over its last letters
        def grey(p):
            return p[3] > 150 and 30 < _lum(p) < 245
        mask = {(x, y) for x in range(w) for y in range(h) if grey(px[x, y])}
        # the caption is the grey cluster at the right; ignore isolated grey anti-aliasing pixels
        if mask:
            xs = sorted(x for x, _ in mask)
            cx0 = xs[len(xs) // 4]
            mask = {(x, y) for (x, y) in mask if x >= cx0 - 6}
        grown = set()
        for (x, y) in mask:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if 0 <= x + dx < w and 0 <= y + dy < h:
                        grown.add((x + dx, y + dy))
        mcols = {x for x, _ in grown}
        clean = [x for x in range(w) if x not in mcols]
        white_rows = [y for x in clean for y in range(h) if px[x, y][3] > 200 and _lum(px[x, y]) > 245]
        black_rows = [y for x in clean for y in range(h) if px[x, y][3] > 100 and _lum(px[x, y]) < 20]
        bw, bb = max(white_rows), max(black_rows)
        for x in sorted(mcols):
            col_white = False
            for y in range(h):
                if (x, y) not in grown:
                    p = px[x, y]
                    col_white = p[3] > 200 and _lum(p) > 245
                    continue
                above = px[x, y - 1] if y > 0 else (255, 255, 255, 0)
                if y <= bw:
                    px[x, y] = above
                    col_white = above[3] > 200 and _lum(above) > 245
                elif y <= bb:
                    px[x, y] = (3, 3, 3, 254) if (above[3] > 100) else (255, 255, 255, 0)
                else:
                    px[x, y] = (255, 255, 255, 0)
        return img, probs
    raise ValueError(st)


def _outline_word(img, x, y, text, fill, ol, r=2, bold=True):
    """Bold text with an r-px solid outline (8-neighbour dilation); returns drawn width."""
    lay = Image.new('RGBA', (measure(text, bold) + 4, 20), (0, 0, 0, 0))
    draw(lay, 1, 0, text, fill, bold=bold, levels=(0, 1.0, 1.0))
    src = np.array(lay)
    a = src[..., 3] > 0
    m = a.copy()
    for _ in range(r):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        g[1:, 1:] |= m[:-1, :-1]
        g[:-1, :-1] |= m[1:, 1:]
        g[1:, :-1] |= m[:-1, 1:]
        g[:-1, 1:] |= m[1:, :-1]
        m = g
    base = np.zeros(src.shape, np.uint8)
    base[m] = (ol[0], ol[1], ol[2], 254)
    base[a] = src[a]
    base[a, 3] = 254
    img.alpha_composite(Image.fromarray(base, 'RGBA'), (x, y))
    return lay.width


def render_redraw(job, up):
    """Designs where Japanese is layered over English lettering: redrawn with the plate's own
    English wording (job['en']), Japanese removed."""
    st = job['style']
    if st == 'rank_plate':        # grey bevelled plate, embossed text
        a = np.array(up).astype(int)
        h, w = a.shape[:2]
        y0, y1, x0, x1 = RANK_INTERIOR
        y1, x1 = h + y1, w + x1
        ring = np.concatenate([a[y0, x0:x1], a[y1, x0:x1], a[y0:y1, x0], a[y0:y1, x1]])
        a[y0:y1 + 1, x0:x1 + 1] = np.median(ring, axis=0)
        img = Image.fromarray(a.astype(np.uint8), 'RGBA').copy()
        lines = job['en']
        y = (y0 + y1) // 2 - len(lines) * 16 // 2 - 1
        for l in lines:
            tw = measure(l, True)
            x = (w - tw) // 2
            draw(img, x - 1, y - 1, l, (255, 255, 255), bold=True, levels=(0, 1, 1))
            draw(img, x + 1, y + 1, l, (40, 40, 40), bold=True, levels=(0, 1, 1))
            draw(img, x, y, l, (112, 112, 112), bold=True, levels=(0, 1, 1))
            y += 16
        return img, []
    if st == 'personality':       # big outlined word on transparent
        img = Image.new('RGBA', up.size, (255, 255, 255, 0))
        word = job['en']
        tw = measure(word, True)
        _outline_word(img, (up.width - tw) // 2 - 1, up.height // 2 - 10, word, (255, 255, 255), (10, 10, 10))
        return img, []
    if st == 'stat_word':         # official English word, outlined; grey gloss for CP / NT
        img = Image.new('RGBA', up.size, (255, 255, 255, 0))
        word, gloss = job['en']
        x = 3 + _outline_word(img, 2, (up.height - 18) // 2, word, (255, 255, 255), (3, 3, 3))
        probs = []
        if gloss:
            gw = measure(gloss)
            if x + 4 + gw > up.width - 1:
                probs.append('gloss too wide: %s' % gloss)
            draw_outlined(img, x + 4, (up.height - 18) // 2 + 3, gloss, (110, 110, 110), (225, 225, 225), bold=False)
        return img, probs
    raise ValueError(st)


def render_ops(job, up):
    """style 'ops': replace white text inside rectangles. Each op: rect [x0,y0,x1,y1] (upright,
    inclusive), text, align ('center'|'left'), bold, outline (rgb or null), dy (optional).
    Text pixels (light, opaque) grown by 2 px are painted with the median of the row's other pixels
    inside the rectangle (button gradients stay, transparent stays transparent)."""
    img = up.copy()
    a = np.array(img).astype(np.int32)
    probs = []
    for op in job['ops']:
        x0, y0, x1, y1 = op['rect']
        sub = a[y0:y1 + 1, x0:x1 + 1]
        lum = sub[..., :3].mean(axis=2)
        m = (lum > 170) & (sub[..., 3] > 100)
        for _ in range(op.get('grow', 2)):
            g = m.copy()
            g[1:] |= m[:-1]
            g[:-1] |= m[1:]
            g[:, 1:] |= m[:, :-1]
            g[:, :-1] |= m[:, 1:]
            m = g
        for yy in range(sub.shape[0]):
            keep = ~m[yy]
            fill = np.median(sub[yy][keep], axis=0) if keep.any() else np.array([255, 255, 255, 0])
            sub[yy][m[yy]] = fill
        a[y0:y1 + 1, x0:x1 + 1] = sub
    img = Image.fromarray(a.astype(np.uint8), 'RGBA').copy()
    for op in job['ops']:
        if not op.get('text'):
            continue
        x0, y0, x1, y1 = op['rect']
        bold = op.get('bold', True)
        tw = measure(op['text'], bold)
        if tw > x1 - x0 - 1 and bold:
            bold, tw = False, measure(op['text'], False)
        if tw > x1 - x0 - 1:
            probs.append('too wide (%d > %d): %s' % (tw, x1 - x0 - 1, op['text']))
        x = x0 + (x1 - x0 + 1 - tw) // 2 if op.get('align', 'center') == 'center' else x0
        y = (y0 + y1) // 2 - 9 + op.get('dy', 0)
        if op.get('outline'):
            _outline_word(img, x - 1, y, op['text'], tuple(op.get('colour', (255, 255, 255))),
                          tuple(op['outline']), r=1, bold=bold)
            if op.get('heavy'):   # second pass 1 px right: the guide lettering is extra heavy
                _outline_word(img, x, y, op['text'], tuple(op.get('colour', (255, 255, 255))),
                              tuple(op['outline']), r=1, bold=bold)
        else:
            draw(img, x, y, op['text'], tuple(op.get('colour', (255, 255, 255))), bold=bold,
                 levels=(0, 0.7, 1.0))
    return img, probs


TITLE_FONT = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'NotoSansJP-VF.ttf')  # SIL OFL


def render_title_sub(job, up, probs):
    """Title-menu description (256x64 texture). The game shows it stretched 2x horizontally and 1x
    vertically, so (like the original Japanese art: a smooth font drawn half-width) the text is drawn
    on a 512x64 screen-proportioned canvas, 4x supersampled, then reduced to 256x64."""
    from PIL import ImageFont
    W, H, SS = up.width * 2, up.height, 4
    head, desc = job['en']
    big = Image.new('L', (W * SS, H * SS), 0)
    dr = ImageDraw.Draw(big)
    for text, size, base in ((head, 17, 19), (desc, 25, 53)):     # base = baseline y on the canvas
        f = ImageFont.truetype(TITLE_FONT, size * SS)
        try:
            f.set_variation_by_axes([400])
        except Exception:
            pass
        bb = dr.textbbox((0, 0), text, font=f, anchor='ls')
        w = bb[2] - bb[0]
        if w > (W - 8) * SS:
            probs.append('too wide (%d px on screen): %s' % (w // SS, text))
        dr.text(((W * SS - w) // 2 - bb[0], base * SS), text, font=f, fill=255, anchor='ls')
    a = np.asarray(big.resize((up.width, up.height), Image.LANCZOS)).astype(np.float32) / 255.0
    col = np.array((228, 228, 228), np.float32)
    rgb = (a[..., None] * col).round().astype(np.uint8)
    out = np.concatenate([rgb, np.full(a.shape + (1,), 255, np.uint8)], axis=-1)
    return Image.fromarray(out, 'RGBA')


def render_faction(job, up):
    """Faction name plates: big English name, then a gap, then a rule + the katakana reading.
    Everything below the first gap of >= 3 empty rows after the name is removed."""
    a = np.array(up).astype(np.int32)
    h = a.shape[0]
    rows = (a[..., 3] > 100).any(axis=1)
    seen, gap, cut = False, 0, None
    for y in range(h):
        if rows[y]:
            if seen and gap >= 3:
                cut = y - gap
                break
            seen, gap = True, 0
        elif seen:
            gap += 1
    if cut is None:   # tight layout (CROSSBONE VANGUARD): find the rule bar, cut at the empty row above it
        opq = a[..., 3] > 100
        rule = next((y for y in range(h - 1, 0, -1)
                     if max((len(r) for r in ''.join('#' if v else '.' for v in opq[y, :50]).split('.')), default=0) >= 12),
                    None)
        if rule is not None:
            def bar(y):
                return max((len(r) for r in ''.join('#' if v else '.' for v in opq[y, :50]).split('.')), default=0) >= 12
            top = rule
            while top > 0 and bar(top - 1):
                top -= 1
            cut = top - 7   # the reading starts 7 rows above the bar on every plate
        if cut is None:
            return up, ['no gap under the name']
    a[cut:, :] = (255, 255, 255, 0)
    return Image.fromarray(a.astype(np.uint8), 'RGBA').copy(), []


RANK_INTERIOR = (5, -6, 5, -6)   # y0, y1 (from bottom), x0, x1 (from right) of the plate's flat face


def render(job):
    """Return (upright RGBA image, problems list)."""
    probs = []
    _, raw = load(job['xts'], job['image'])
    up = raw.transpose(Image.FLIP_TOP_BOTTOM)
    st = job['style']
    if st in ('rank_plate', 'personality', 'stat_word'):
        return render_redraw(job, up)
    if st == 'ops':
        return render_ops(job, up)
    if st == 'faction':
        return render_faction(job, up)
    if st.startswith('stat_'):
        return render_stat(job, up)
    if st == 'title_sub':
        return render_title_sub(job, up, probs), probs
    if st == 'label3':
        img = Image.new('RGBA', up.size, (255, 255, 255, 0))
        for k, text in enumerate(job['en']):
            w = measure(text)
            if w > img.width - 1:
                probs.append('too wide (%d px): %s' % (w, text))
            draw(img, 1, k * 16 - 1, text, (127, 127, 127))
        return img, probs
    if st == 'plate':
        img = family_background(job['family'])
        text = job['en']
        avail = img.width - 6
        for bold, sp in ((True, 0), (False, 0), (False, -1)):
            w = measure(text, bold, sp)
            if w <= avail:
                break
        else:
            probs.append('too wide (%d px > %d): %s' % (w, avail, text))
        x = (img.width - w) // 2
        draw(img, x, 11, text, (248, 248, 248), bold=bold, spacing=sp, shadow=(1, 1, (24, 16, 16)))
        if not bold:
            probs.append('note: regular weight to fit: %s' % text)
        return img, probs
    raise ValueError(st)


def jobs():
    return json.load(open(JOBS, encoding='utf-8'))


def preview():
    os.makedirs(PREV, exist_ok=True)
    tiles = []
    for j in jobs():
        img, probs = render(j)
        name = (j['xts'].replace('/', '__').replace('.xts', '') + '__' + j['image'])
        img.save(os.path.join(PREV, name + '.png'))
        _, orig = load(j['xts'], j['image'])
        tiles.append((name, orig.transpose(Image.FLIP_TOP_BOTTOM), img, probs))
        for p in probs:
            print(name, p)
    S = 2
    W = 1400
    rows, x, y, rowh, pos = [], 0, 0, 0, []
    for n, a, b, _ in tiles:
        w = (a.width + b.width) * S + 16
        if x + w > W:
            x, y, rowh = 0, y + rowh + 16, 0
        pos.append((x, y))
        x += w
        rowh = max(rowh, max(a.height, b.height) * S)
    sheet = Image.new('RGB', (W, y + rowh + 16), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for (n, a, b, _), (px, py) in zip(tiles, pos):
        for k, im in enumerate((a, b)):
            bg = Image.new('RGBA', im.size, (70, 70, 80, 255))
            bg.alpha_composite(im)
            sheet.paste(bg.convert('RGB').resize((im.width * S, im.height * S), Image.NEAREST),
                        (px + k * (a.width * S + 4), py + 12))
        d.text((px, py), n.split('__')[-1][:30], fill=(200, 200, 120))
    sheet.save(os.path.join(PREV, '_contact_sheet.png'))
    print('preview:', len(tiles), 'textures ->', PREV)


def new_xts_bytes():
    """{xts relative path: new bytes} with all jobs of that file applied."""
    by = collections.defaultdict(list)
    for j in jobs():
        by[j['xts']].append(j)
    out = {}
    for xts, js in by.items():
        d = open(os.path.join(FPK, xts), 'rb').read()
        for j in js:
            img, _ = render(j)
            d = xts_tool.encode_image(d, j['image'], img.transpose(Image.FLIP_TOP_BOTTOM))
        out[xts] = d
    return out


def copies(xts):
    """Top-level GAME.MB entry names holding a byte-identical copy of FPK/xts."""
    src = open(os.path.join(FPK, xts), 'rb').read()
    base = os.path.basename(xts)
    tops = set()
    for p in glob.glob(os.path.join(FPK, '**', base), recursive=True):
        if open(p, 'rb').read() == src:
            rel = os.path.relpath(p, FPK).replace('\\', '/')
            tops.add(rel.split('/')[0][:-1])   # 'abilities.pack.fpk_' -> 'abilities.pack.fpk'
    return src, sorted(tops)


def _image_key(d, cl, im):
    """Identity of an image independent of the file it is packed in: name + pixel + CLUT bytes."""
    px = d[im['off']:im['off'] + im['size']]
    c = next((c for c in cl if c['name'] == im['clut']), None)
    pal = d[c['off']:c['off'] + c['size']] if c else b''
    return (im['name'], hashlib.md5(px).hexdigest(), hashlib.md5(pal).hexdigest())


def texture_index():
    """{image key: [(kind, path)]} over every XTS: kind 'nested' = file inside an FPK (path relative
    to work/source/fpk), 'top' = stand-alone GAME.MB entry (e.g. pause_ps_eibin.xts)."""
    idx = collections.defaultdict(list)
    files = [('nested', p) for p in glob.glob(os.path.join(FPK, '**', '*.xts'), recursive=True)]
    files += [('top', p) for p in glob.glob(os.path.join(GAME, '*.xts'))]
    for kind, p in files:
        d = open(p, 'rb').read()
        try:
            cl, ims = xts_tool.parse(d)
        except Exception:   # noqa
            continue
        for im in ims:
            try:
                idx[_image_key(d, cl, im)].append((kind, p))
            except Exception:   # noqa
                pass
    return idx


def apply(entries, report=None):
    """entries: {GAME.MB entry name: bytes} from insert_text; returns it with textures patched.

    Every translated image is written into every texture file (inside FPKs or stand-alone in
    GAME.MB) that contains the same image (same name, pixels and CLUT). File sizes never change."""
    rep = report if report is not None else []
    idx = texture_index()
    rendered = {}
    targets = collections.defaultdict(list)          # file path -> [(image name, upright image)]
    for j in jobs():
        d = open(os.path.join(FPK, j['xts']), 'rb').read()
        cl, ims = xts_tool.parse(d)
        im = next(x for x in ims if x['name'] == j['image'])
        key = _image_key(d, cl, im)
        if key not in rendered:
            rendered[key] = render(j)[0]
        for kind, p in idx[key]:
            targets[(kind, p)].append((j['image'], rendered[key]))
    n_nested = n_top = 0
    for (kind, p), edits in sorted(targets.items()):
        old = open(p, 'rb').read()
        new = old
        for name, img in edits:
            new = xts_tool.encode_image(new, name, img.transpose(Image.FLIP_TOP_BOTTOM))
        if kind == 'top':
            entries[os.path.basename(p)] = new
            n_top += 1
            continue
        top = os.path.relpath(p, FPK).replace(os.sep, '/').split('/')[0][:-1]
        data = entries.get(top)
        if data is None:
            data = open(os.path.join(GAME, top), 'rb').read()
        if old not in data:
            if new in data:   # an identical file under another name was already patched
                n_nested += 1
                continue
            rep.append('TEX source bytes not found in %s for %s' % (top, p))
            continue
        entries[top] = data.replace(old, new)
        n_nested += 1
    rep.append('TEX %d images -> %d files in FPKs + %d stand-alone files' % (len(rendered), n_nested, n_top))
    return entries


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'preview'
    if cmd == 'preview':
        preview()
    elif cmd == 'check':
        for j in jobs():
            _, probs = render(j)
            for p in probs:
                print(j['image'], p)
