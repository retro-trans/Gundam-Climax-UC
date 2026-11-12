"""Voice subtitles: build the subtitle blob (MIPS hook code + clip table) and patch it into the ELF.

How it works (see docs/subtitles.md):
  * The ELF's first load segment stores the whole .bss (0x36FB00-0x4B3180) as zeros in the file; crt0
    clears that range at boot anyway. The segment's file size is cut to end at 0x36FB00 and the freed
    file space (same file size, nothing moves on disc) is loaded by the ELF's second program header
    (previously empty) at SUB_BASE, right after the program's end. crt0's SetupHeap start (and the
    libkernel `end` word) move past the blob, so the C heap starts after it.
  * Hook 1, entry of the stream-start function 0x177940(name, channel): look the clip name up
    (case-insensitive) in the table; on a hit start that clip's subtitle (clips with no text clear it).
  * Hook 2, entries of two tasks that run every frame (menu-scene task 0x2FCEE0, mission voice-trigger
    task 0x218DB0): advance the subtitle clock (COP0 Count) and draw the current page with the game's
    own text renderer (context *(gp-0x7AB8); 0x196B90 colour, 0x196D00 printf-style draw) with a black
    outline. A Count-based guard draws at most once per frame if both tasks run.

Input: work/translation/en/subtitles.json  {clip: {"en": text or [page, ...], ...}}
Timing: work/source/voice/transcripts.jsonl (clip length, Whisper segments).

python tools/subtitles.py check        build the blob, print size / problems (dry run)
"""
import json
import os
import struct
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import textenc  # noqa: E402
from asm import asm  # noqa: E402

SUBS_JSON = os.path.join(ROOT, 'work', 'translation', 'en', 'subtitles.json')
TRANSCRIPTS = os.path.join(ROOT, 'work', 'source', 'voice', 'transcripts.jsonl')

ELF_BASE, ELF_FOFF = 0x100000, 0x80
BSS_START, PROG_END = 0x36FB00, 0x4B3180          # crt0 clears [BSS_START, PROG_END)
SUB_BASE = 0x4B3200                               # blob load address (16-aligned, after PROG_END)
BLOB_FOFF = ELF_FOFF + (BSS_START - ELF_BASE)     # freed file space: 0x26FB80 ...
BLOB_MAX = ELF_FOFF + (PROG_END - ELF_BASE) - BLOB_FOFF
HEAP_LIMIT = 0x5F0000                             # the game's own heap starts at 0x600000

VOICE_FN = 0x177940          # stream start (name, channel)
VOICE_FN_ORIG = (0x27BDFFC0, 0xFFBF0030)
# per-frame draw points: entries of tasks that run every frame (both are reached through vtables)
DRAW_HOOKS = (
    # (function, original first two instructions, glyphs reserved for game text drawn after us)
    (0x2FCEE0, (0x27BDFA50, 0xFFBF0030), 60, 0),    # menu-scene task (briefings, menus): cap 400
    (0x218DB0, (0x27BDFFE0, 0xFFBF0010), 10, 0),    # mission voice-trigger task: cap 200, no HUD text
    (0x1F2EE0, (0x27BDFFC0, 0xFFBF0030), 10, 1),    # CHiMovie task: draws the movie frame; while a
)                                                    # movie plays only this hook draws (on top of it)
SAME_FRAME = 0x200000        # COP0 cycles (~7 ms): a second draw point in the same frame is skipped
CRT0_HEAP_HI, CRT0_HEAP_LO = 0x1001D0, 0x1001D8   # lui $a0,0x4b / addiu $a0,$a0,0x3180
KERNEL_END_WORD = 0x31F774                         # libkernel data word holding PROG_END

# movies (CHiMpeg, MOVIE3.MB *.pss): three call sites of empty debug loggers are redirected
MOVIE_REQ_FN = 0x3181E0      # scene-script movie request (name, arg): copies the name to 0x4B2FF0
MOVIE_REQ_ORIG = (0x27BDFFE0, 0x0080102D)
MOVIE_START_CALL = 0x199B44  # jal 0x198B30 ("Start Movie") in the CHiMpeg state machine
MOVIE_STOP_CALL = 0x199CD8   # jal 0x198B30 ("Stop Movie")
MOVIE_CALLS_ORIG = {MOVIE_START_CALL: 0x0C0662CC, MOVIE_STOP_CALL: 0x0C0662CC}
MOVIE_TRANSCRIPTS = os.path.join(ROOT, 'work', 'source', 'voice', 'movie_transcripts.jsonl')
MOVIE_GAP = 0.15             # blank the subtitle when the next line starts this much later

TEXT_CTX_GP = -0x7AB8
SET_COLOR = 0x196B90         # (ctx, r, g, b, a)
DRAW_FMT = 0x196D00          # (ctx, matrix*, fmt, ...)
MAT_COPY = 0x1396E8          # (dst, src)
MAT_TRANS = 0x18DDD0         # (m) f12 x, f13 y, f14 z
BASE_MAT = 0x70003F10        # scratchpad: 2D base matrix (as used by the help-bar text)

UNITS_PER_SEC = 294912000 // 4096    # COP0 Count >> 12
TAIL_SEC = 0.4               # keep the last page up a little after the voice ends

# layout (screen is 640 x 448 in these units; y is the top of the glyphs)
MAX_PX = 560
LINE_H = 22
BOTTOM_Y = 362               # top of the last line (scenes shift the display by up to ~30 units: keep 2 lines in the safe area)
MAX_LINES = 2
MAX_PAGE_CHARS = 90          # glyph budget: the text renderer draws at most ctx+0x48C glyphs per frame
                             # (200 in missions, 400 elsewhere; set at 0x1AB750), shared with game text
OUTLINE4 = ((-1, 0), (1, 0), (0, -1), (0, 1))   # full outline = these + shadow + white (6 passes)
SHADOW = (1, 1)
CTX_GLYPH_CAP, CTX_GLYPH_USED = 0x48C, 0x530      # text context: cap, glyphs drawn this frame
CTX_PRIO = 0x4B4             # text context: draw-list priority (0x121EA0(group, prio), list = group*8+prio;
SUB_PRIO = 7                 # lists draw in ascending order: game text 5, movie frame 6 -> subtitles 7

RN = {n: i for i, n in enumerate(
    'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}


def hi(a):
    return ((a + 0x8000) >> 16) & 0xFFFF


def lo(a):
    v = a & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def la(reg, a):
    return ['lui $%s, 0x%X' % (reg, hi(a)), 'addiu $%s, $%s, %d' % (reg, reg, lo(a))]


def sd(rt, off, base='sp'):
    return '.word 0x%08X' % ((0x3F << 26) | (RN[base] << 21) | (RN[rt] << 16) | (off & 0xFFFF))


def ld(rt, off, base='sp'):
    return '.word 0x%08X' % ((0x37 << 26) | (RN[base] << 21) | (RN[rt] << 16) | (off & 0xFFFF))


def mfc0_count(rt):
    return '.word 0x%08X' % (0x40000000 | (RN[rt] << 16) | (9 << 11))


def f32(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


# ------------------------------------------------------------------ data
def load_subs():
    if not os.path.exists(SUBS_JSON):
        return {}
    return json.load(open(SUBS_JSON, encoding='utf-8'))


def load_timing():
    t = {}
    if not os.path.exists(TRANSCRIPTS):
        return t
    for line in open(TRANSCRIPTS, encoding='utf-8'):
        x = json.loads(line)
        t[x['clip'].lower()] = x
    if os.path.exists(MOVIE_TRANSCRIPTS):
        for line in open(MOVIE_TRANSCRIPTS, encoding='utf-8'):
            x = json.loads(line)
            t[x['movie'].lower()] = x
    return t


def movie_pages(cues, probs, clip):
    """cues [[start, end, en], ...] -> [(start_sec, [lines])]; empty pages blank the gaps."""
    out = []
    cues = sorted(c for c in cues if c[2])
    for k, (a, b, en) in enumerate(cues):
        for st, lines in paginate(en, max(b - a, 0.5), probs, clip):
            out.append((a + st, lines))
        nxt = cues[k + 1][0] if k + 1 < len(cues) else None
        if nxt is None or nxt - b > MOVIE_GAP:
            out.append((b + 0.3, []))
    return out


def split_pages(text):
    """Split text at word boundaries into the fewest near-equal chunks of <= MAX_PAGE_CHARS
    characters, preferring breaks after sentence punctuation."""
    words = text.split()
    if not words:
        return []
    n = -(-len(text) // MAX_PAGE_CHARS)
    while True:
        target = len(text) / n
        chunks, cur = [], []
        for k, w in enumerate(words):
            cand = ' '.join(cur + [w])
            if cur and len(cand) > MAX_PAGE_CHARS:
                chunks.append(' '.join(cur))
                cur = [w]
                continue
            cur.append(w)
            left = len(words) - k - 1
            # close a chunk near the target, earlier at a sentence end when one is close
            if len(chunks) < n - 1 and left:
                c = len(' '.join(cur))
                if c >= target or (c >= target * 0.7 and w[-1] in '.!?,'):
                    chunks.append(' '.join(cur))
                    cur = []
        if cur:
            chunks.append(' '.join(cur))
        if all(len(c) <= MAX_PAGE_CHARS for c in chunks) and len(chunks) <= n + 1:
            return chunks
        n += 1


def split_lines(chunk):
    """One line if it fits MAX_PX, else two lines balanced by pixel width."""
    if textenc.px(chunk) <= MAX_PX:
        return [chunk]
    words = chunk.split(' ')
    best = None
    for k in range(1, len(words)):
        a, b = ' '.join(words[:k]), ' '.join(words[k:])
        cost = max(textenc.px(a), textenc.px(b))
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1]


def paginate(en, seconds, probs, clip):
    """-> [(start_sec, [line, ...]), ...]. en is a string or a list of explicit pages."""
    pages = en if isinstance(en, list) else [en]
    out_pages = []
    for p in pages:
        for chunk in split_pages(textenc.fold(p)):
            out_pages.append(split_lines(chunk))
    for pg in out_pages:
        if len(''.join(pg)) > MAX_PAGE_CHARS:
            probs.append('%s: page over %d characters: %s' % (clip, MAX_PAGE_CHARS, ' / '.join(pg)))
    for ln in (l for pg in out_pages for l in pg):
        if textenc.px(ln) > MAX_PX:
            probs.append('%s: line too wide (%d px): %s' % (clip, textenc.px(ln), ln))
    # page start times proportional to text length
    total = sum(len(' '.join(pg)) for pg in out_pages) or 1
    res, acc = [], 0
    for pg in out_pages:
        res.append((seconds * acc / total, pg))
        acc += len(' '.join(pg))
    return res


def build_data(base, subs, timing, probs):
    """-> (bytes placed at base, table address)."""
    clips = []
    for clip, row in sorted(subs.items()):
        en = row.get('en') if isinstance(row, dict) else row
        tm = timing.get(clip.lower())
        if tm is None and isinstance(row, dict) and row.get('sec'):     # fresh clone: no transcripts
            tm = {'seconds': row['sec']}
        if tm is None:
            probs.append('%s: no timing (not in transcripts)' % clip)
            continue
        if isinstance(row, dict) and row.get('cues') is not None:      # movie: timed cues
            pages = movie_pages(row['cues'], probs, clip)
        else:
            pages = paginate(en, tm['seconds'], probs, clip) if en else []
        clips.append((clip.lower(), tm['seconds'], pages))

    strings = bytearray()
    str_off = {}

    def s_add(b):
        if b not in str_off:
            str_off[b] = len(strings)
            strings.extend(b + b'\0')
        return str_off[b]

    # layout: [table][records][strings]
    n = len(clips)
    table_size = 4 + 8 * n
    recs = bytearray()
    rec_fix = []        # (offset in recs, string offset) -> pointer fixups
    rec_off = []
    name_off = []
    for clip, secs, pages in clips:
        name_off.append(s_add(clip.encode('ascii')))
        rec_off.append(len(recs))
        total = int((secs + TAIL_SEC) * UNITS_PER_SEC)
        recs += struct.pack('<2I', total, len(pages))
        for start, lines in pages:
            glyphs = sum(len(textenc.encode(ln)) for ln in lines)
            recs += struct.pack('<IHH', int(start * UNITS_PER_SEC), len(lines), glyphs)
            nl = len(lines)
            for i, ln in enumerate(lines):
                x = (640 - textenc.px(ln)) // 2
                y = BOTTOM_Y - (nl - 1 - i) * LINE_H
                rec_fix.append((len(recs) + 8, s_add(textenc.encode(ln))))
                recs += struct.pack('<ffI', float(x), float(y), 0)
    rec_base = base + table_size
    str_base = rec_base + len(recs)
    for o, so in rec_fix:
        struct.pack_into('<I', recs, o, str_base + so)
    table = bytearray(struct.pack('<I', n))
    for no, ro in zip(name_off, rec_off):
        table += struct.pack('<2I', str_base + no, rec_base + ro)
    return bytes(table + recs + strings), n


# ------------------------------------------------------------------ code
def code_lines(state, fmt, table):
    """state: +0 cur_rec, +4 elapsed_units, +8 last_count, +12 last_draw_count, +16 pending movie
    record, +20 movie active flag."""
    L = []
    # ---- hook 1: stream start --------------------------------------------------------------
    L += ['voice_hook:',
          'addiu $sp, $sp, -0x20', sd('ra', 0), sd('a0', 8), sd('a1', 0x10),
          'jal lookup', 'nop',
          'beqz $v0, vh_out', 'nop']
    L += la('t0', state)
    L += ['sw $v0, 0($t0)', 'sw $zero, 4($t0)', mfc0_count('t1'), 'sw $t1, 8($t0)',
          'vh_out:',
          ld('ra', 0), ld('a0', 8), ld('a1', 0x10), 'addiu $sp, $sp, 0x20',
          '.word 0x%08X' % VOICE_FN_ORIG[0], '.word 0x%08X' % VOICE_FN_ORIG[1],
          'j 0x%X' % (VOICE_FN + 8), 'nop']
    # ---- movie hooks (replace calls to empty loggers; return 1 like them) --------------------
    L += ['movie_open:',                       # entry of MOVIE_REQ_FN: a0 = file name (may carry a path)
          'addiu $sp, $sp, -0x20', sd('ra', 0), sd('a0', 8), sd('a1', 0x10),
          'move $t0, $a0',
          'mo_scan:', 'lbu $t1, 0($t0)', 'beqz $t1, mo_look', 'nop',
          'addiu $t2, $t1, -47', 'beqz $t2, mo_cut', 'nop',          # '/'
          'addiu $t2, $t1, -92', 'beqz $t2, mo_cut', 'nop',          # '\\'
          'addiu $t2, $t1, -58', 'bnez $t2, mo_next', 'nop',         # ':'
          'mo_cut:', 'addiu $a0, $t0, 1',
          'mo_next:', 'b mo_scan', 'addiu $t0, $t0, 1',
          'mo_look:', 'jal lookup', 'nop']
    L += la('t0', state)
    L += ['sw $v0, 16($t0)',
          ld('ra', 0), ld('a0', 8), ld('a1', 0x10), 'addiu $sp, $sp, 0x20',
          '.word 0x%08X' % MOVIE_REQ_ORIG[0], '.word 0x%08X' % MOVIE_REQ_ORIG[1],
          'j 0x%X' % (MOVIE_REQ_FN + 8), 'nop']
    L += ['movie_start:']
    L += la('t0', state)
    L += ['lw $t1, 16($t0)', 'beqz $t1, ms_out', 'nop',
          'sw $t1, 0($t0)', 'sw $zero, 4($t0)', mfc0_count('t2'), 'sw $t2, 8($t0)',
          'sw $zero, 16($t0)', 'addiu $t3, $zero, 1', 'sw $t3, 20($t0)',
          'ms_out:', 'jr $ra', 'addiu $v0, $zero, 1']
    L += ['movie_stop:']
    L += la('t0', state)
    L += ['lw $t1, 20($t0)', 'beqz $t1, mt_out', 'nop',
          'sw $zero, 0($t0)', 'sw $zero, 20($t0)',
          'mt_out:', 'sw $zero, 16($t0)', 'jr $ra', 'addiu $v0, $zero, 1']
    # ---- lookup(a0 = name) -> v0 = record or 0 (case-insensitive) ---------------------------
    L += ['lookup:']
    L += la('t0', table)
    L += ['lw $t1, 0($t0)', 'addiu $t0, $t0, 4',
          'lk_loop:', 'beqz $t1, lk_none', 'nop',
          'lw $t2, 0($t0)', 'move $t3, $a0',
          'lk_cmp:',
          'lbu $t4, 0($t2)', 'lbu $t5, 0($t3)',
          'addiu $t6, $t5, -65', 'sltiu $t6, $t6, 26', 'beqz $t6, lk_c2', 'nop', 'addiu $t5, $t5, 32',
          'lk_c2:',
          'bne $t4, $t5, lk_next', 'nop',
          'beqz $t4, lk_found', 'nop',
          'addiu $t2, $t2, 1', 'b lk_cmp', 'addiu $t3, $t3, 1',
          'lk_next:', 'addiu $t0, $t0, 8', 'b lk_loop', 'addiu $t1, $t1, -1',
          'lk_found:', 'jr $ra', 'lw $v0, 4($t0)',
          'lk_none:', 'jr $ra', 'move $v0, $zero']
    # ---- hook 2: per-frame draw points. The entry of each task jumps to a wrapper that first runs
    # the whole task (trampoline: the two replaced instructions, then the rest of the function,
    # which returns to the wrapper) and then draws, so the subtitle lands on top of what the task
    # drew (full-screen event pictures in Progress mode would otherwise cover it). The tasks take
    # register arguments only (checked: no reads above their own frame).
    for k, (fn, orig, reserve, is_movie) in enumerate(DRAW_HOOKS):
        L += ['draw_hook%d:' % k,
              'addiu $sp, $sp, -0x20', sd('ra', 0x10),
              'jal draw_tramp%d' % k, 'nop',
              sd('v0', 0x08),
              'addiu $a1, $zero, %d' % is_movie,
              'jal draw_core', 'addiu $a0, $zero, %d' % reserve,
              ld('v0', 0x08), ld('ra', 0x10),
              'jr $ra', 'addiu $sp, $sp, 0x20',
              'draw_tramp%d:' % k,
              '.word 0x%08X' % orig[0], '.word 0x%08X' % orig[1],
              'j 0x%X' % (fn + 8), 'nop']
    # ---- draw_core: advance the clock, draw the current page (once per frame) --------------------
    L += ['draw_core:',
          'addiu $sp, $sp, -0x60', sd('ra', 0x50), sd('s0', 0x40), sd('s1', 0x38),
          sd('s2', 0x30), sd('s3', 0x28), sd('s4', 0x20), sd('s5', 0x18), sd('s6', 0x10), sd('s7', 0x08),
          'move $s6, $a0']                                                # s6 = reserve
    L += la('s0', state)
    L += ['lw $s1, 0($s0)', 'beqz $s1, dh_out', 'nop',
          'lw $t0, 20($s0)', 'bne $t0, $a1, dh_out', 'nop',             # movie playing <=> movie hook
          mfc0_count('t0'),
          'lw $t1, 12($s0)', 'subu $t1, $t0, $t1', 'lui $t2, 0x%X' % (SAME_FRAME >> 16),
          'sltu $t1, $t1, $t2', 'bnez $t1, dh_out', 'nop',                # already drawn this frame
          'sw $t0, 12($s0)',
          'lw $t1, 8($s0)', 'sw $t0, 8($s0)',
          'subu $t2, $t0, $t1', 'srl $t2, $t2, 12',
          'lw $s3, 4($s0)', 'addu $s3, $s3, $t2', 'sw $s3, 4($s0)',     # s3 = elapsed
          'lw $t3, 0($s1)', 'sltu $t4, $s3, $t3', 'bnez $t4, dh_page', 'nop',
          'sw $zero, 20($s0)', 'b dh_out', 'sw $zero, 0($s0)',
          # pick the last page whose start <= elapsed
          'dh_page:',
          'lw %s, %d($gp)' % ('$t0', TEXT_CTX_GP), 'beqz $t0, dh_out', 'nop',
          'addiu $t0, $s1, 8', 'lw $t1, 4($s1)', 'move $s2, $zero',
          'pg_loop:', 'beqz $t1, pg_done', 'nop',
          'lw $t2, 0($t0)', 'sltu $t3, $s3, $t2', 'bnez $t3, pg_done', 'nop',
          'move $s2, $t0', 'lhu $t4, 4($t0)',
          'sll $t5, $t4, 3', 'sll $t6, $t4, 2', 'addu $t5, $t5, $t6',
          'addiu $t0, $t0, 8', 'addu $t0, $t0, $t5', 'b pg_loop', 'addiu $t1, $t1, -1',
          'pg_done:', 'beqz $s2, dh_out', 'nop',
          'lhu $s4, 4($s2)', 'addiu $s5, $s2, 8',                      # s4 = lines left, s5 = line
          # passes from the glyph budget: avail = cap - used - reserve
          'lw $t0, %d($gp)' % TEXT_CTX_GP,
          'lw $t1, %d($t0)' % CTX_GLYPH_CAP, 'lw $t2, %d($t0)' % CTX_GLYPH_USED,
          'subu $t1, $t1, $t2', 'subu $t1, $t1, $s6',                     # t1 = avail
          'lhu $t3, 6($s2)',                                              # t3 = glyphs on the page
          'sll $t4, $t3, 2', 'sll $t5, $t3, 1', 'addu $t4, $t4, $t5',    # t4 = 6 * glyphs
          'slt $t6, $t1, $t4', 'beqz $t6, ln_prio', 'addiu $s7, $zero, 6',
          'slt $t6, $t1, $t5', 'beqz $t6, ln_prio', 'addiu $s7, $zero, 2',
          'slt $t6, $t1, $t3', 'beqz $t6, ln_prio', 'addiu $s7, $zero, 1',
          'b dh_out', 'nop',
          # draw above everything else in group 0 (movie frames use priority 6); restored at ln_done
          'ln_prio:',
          'lw $t0, %d($gp)' % TEXT_CTX_GP, 'lw $t1, %d($t0)' % CTX_PRIO, 'sw $t1, 0($sp)',
          'addiu $t1, $zero, %d' % SUB_PRIO, 'sw $t1, %d($t0)' % CTX_PRIO,
          'ln_loop:', 'beqz $s4, ln_done', 'nop',
          'addiu $t0, $zero, 6', 'bne $s7, $t0, ln_shadow', 'nop']
    for dx, dy in OUTLINE4:
        L += ['move $a0, $s5', 'addiu $a1, $zero, %d' % dx, 'addiu $a2, $zero, %d' % dy,
              'jal draw_line', 'move $a3, $zero']
    L += ['ln_shadow:',
          'addiu $t0, $zero, 1', 'beq $s7, $t0, ln_white', 'nop',
          'move $a0, $s5', 'addiu $a1, $zero, %d' % SHADOW[0], 'addiu $a2, $zero, %d' % SHADOW[1],
          'jal draw_line', 'move $a3, $zero',
          'ln_white:']
    L += ['move $a0, $s5', 'move $a1, $zero', 'move $a2, $zero',
          'jal draw_line', 'addiu $a3, $zero, 255',
          'addiu $s5, $s5, 12', 'b ln_loop', 'addiu $s4, $s4, -1',
          'ln_done:',
          'lw $t0, %d($gp)' % TEXT_CTX_GP, 'lw $t1, 0($sp)', 'sw $t1, %d($t0)' % CTX_PRIO,
          'dh_out:',
          ld('ra', 0x50), ld('s0', 0x40), ld('s1', 0x38), ld('s2', 0x30),
          ld('s3', 0x28), ld('s4', 0x20), ld('s5', 0x18), ld('s6', 0x10), ld('s7', 0x08),
          'jr $ra', 'addiu $sp, $sp, 0x60']
    # ---- draw_line(a0 = line {f32 x, f32 y, char* text}, a1 = dx, a2 = dy, a3 = grey) --------
    L += ['draw_line:',
          'addiu $sp, $sp, -0x80', sd('ra', 0x70), sd('s0', 0x68), sd('s1', 0x60), sd('s2', 0x58),
          'move $s0, $a0', 'move $s1, $a1', 'move $s2, $a2',
          'lw $a0, %d($gp)' % TEXT_CTX_GP, 'move $a1, $a3', 'move $a2, $a3',
          'jal 0x%X' % SET_COLOR, 'addiu $t0, $zero, 255',
          'addiu $a0, $sp, 0x10']
    L += la('a1', BASE_MAT)
    L += ['jal 0x%X' % MAT_COPY, 'nop',
          'lwc1 $f12, 0($s0)', 'mtc1 $s1, $f0', 'cvt.s.w $f0, $f0', 'add.s $f12, $f12, $f0',
          'lwc1 $f13, 4($s0)', 'mtc1 $s2, $f1', 'cvt.s.w $f1, $f1', 'add.s $f13, $f13, $f1',
          'mtc1 $zero, $f14',
          'jal 0x%X' % MAT_TRANS, 'addiu $a0, $sp, 0x10',
          'lw $a0, %d($gp)' % TEXT_CTX_GP, 'addiu $a1, $sp, 0x10']
    L += la('a2', fmt)
    L += ['jal 0x%X' % DRAW_FMT, 'lw $a3, 8($s0)',
          ld('ra', 0x70), ld('s0', 0x68), ld('s1', 0x60), ld('s2', 0x58),
          'jr $ra', 'addiu $sp, $sp, 0x80']
    return L


def build_blob(subs=None, timing=None):
    """-> (blob bytes, {'voice_hook': addr, 'draw_hook': addr}, problems, clip count)."""
    probs = []
    subs = load_subs() if subs is None else subs
    timing = load_timing() if timing is None else timing
    # pass 1: code size with dummy addresses
    code = asm(code_lines(SUB_BASE, SUB_BASE, SUB_BASE), SUB_BASE)
    code_size = (len(code) + 15) & ~15
    state = SUB_BASE + code_size
    fmt = state + 32
    table = fmt + 16
    data, n = build_data(table, subs, timing, probs)
    lines = code_lines(state, fmt, table)
    code = asm(lines, SUB_BASE)
    assert len(code) <= code_size
    blob = bytearray(code.ljust(code_size, b'\0'))
    blob += b'\0' * 32                       # state
    blob += b'%s'.ljust(16, b'\0')           # fmt
    blob += data
    labels = {}
    addr = SUB_BASE
    for ln in lines:
        ln = ln.split('#')[0].strip()
        if ln.endswith(':'):
            labels[ln[:-1]] = addr
        elif ln:
            addr += 4
    return bytes(blob), labels, probs, n


def patch_elf(elf, blob, labels):
    """Patch a bytearray SLPS_256.27 in place. -> report lines."""
    rep = []

    def off(va):
        return va - ELF_BASE + ELF_FOFF

    def w32(va, v):
        struct.pack_into('<I', elf, off(va), v)

    def r32(va):
        return struct.unpack_from('<I', elf, off(va))[0]

    assert len(blob) <= BLOB_MAX, 'subtitle blob too large'
    end = (SUB_BASE + len(blob) + 0xFF) & ~0xFF
    assert end <= HEAP_LIMIT
    # the freed file range must still be zero (it is the .bss image)
    assert not any(elf[BLOB_FOFF:BLOB_FOFF + BLOB_MAX]), '.bss image not zero'
    phoff = struct.unpack_from('<I', elf, 0x1C)[0]
    ph0 = list(struct.unpack_from('<8I', elf, phoff))
    ph1 = list(struct.unpack_from('<8I', elf, phoff + 32))
    assert ph0[:6] == [1, 0x80, ELF_BASE, ELF_BASE, PROG_END - ELF_BASE, PROG_END - ELF_BASE], ph0
    assert ph1[0] == 1 and ph1[4] == 0 and ph1[5] == 0, ph1
    ph0[4] = BSS_START - ELF_BASE                                  # file part ends at .bss
    ph1 = [1, BLOB_FOFF, SUB_BASE, SUB_BASE, len(blob), len(blob), 7, 16]
    struct.pack_into('<8I', elf, phoff, *ph0)
    struct.pack_into('<8I', elf, phoff + 32, *ph1)
    elf[BLOB_FOFF:BLOB_FOFF + len(blob)] = blob
    # C heap starts after the blob
    assert r32(CRT0_HEAP_HI) == 0x3C04004B and r32(CRT0_HEAP_LO) == 0x24843180
    w32(CRT0_HEAP_HI, 0x3C040000 | hi(end))
    w32(CRT0_HEAP_LO, 0x24840000 | (lo(end) & 0xFFFF))
    assert r32(KERNEL_END_WORD) == PROG_END
    w32(KERNEL_END_WORD, end)
    # hooks
    assert (r32(VOICE_FN), r32(VOICE_FN + 4)) == VOICE_FN_ORIG
    w32(VOICE_FN, (2 << 26) | ((labels['voice_hook'] >> 2) & 0x3FFFFFF))
    w32(VOICE_FN + 4, 0)
    for k, (fn, orig, _, _) in enumerate(DRAW_HOOKS):
        assert (r32(fn), r32(fn + 4)) == orig, hex(fn)
        w32(fn, (2 << 26) | ((labels['draw_hook%d' % k] >> 2) & 0x3FFFFFF))
        w32(fn + 4, 0)
    for va, orig in MOVIE_CALLS_ORIG.items():
        assert r32(va) == orig, hex(va)
    assert (r32(MOVIE_REQ_FN), r32(MOVIE_REQ_FN + 4)) == MOVIE_REQ_ORIG
    w32(MOVIE_REQ_FN, (2 << 26) | ((labels['movie_open'] >> 2) & 0x3FFFFFF))
    w32(MOVIE_REQ_FN + 4, 0)
    w32(MOVIE_START_CALL, (3 << 26) | ((labels['movie_start'] >> 2) & 0x3FFFFFF))
    w32(MOVIE_STOP_CALL, (3 << 26) | ((labels['movie_stop'] >> 2) & 0x3FFFFFF))
    rep.append('subtitles: blob %d bytes at 0x%X-0x%X, heap from 0x%X' % (len(blob), SUB_BASE,
                                                                           SUB_BASE + len(blob), end))
    return rep


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'check':
        blob, labels, probs, n = build_blob()
        print('clips %d, blob %d bytes (max %d), hooks %s' % (
            n, len(blob), BLOB_MAX, {k: hex(v) for k, v in labels.items() if k.endswith('hook')}))
        for p in probs[:50]:
            print(' ', p)
        print('%d problems' % len(probs))
