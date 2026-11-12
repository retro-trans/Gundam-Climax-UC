"""Player-facing Shift-JIS text inside the executable (SLPS_256.27).

Source list: work/source/scan/elf_strings.json (tools/elf_strings.py), limited to RANGES below
(skill / faction / rank tables, promotion messages, default pilot names, pilot history and
retirement endings, "no data" message). Everything else in the ELF is developer debug text.

Each string has a slot: its bytes plus the zero padding up to the next string. Insertion:
  * English fits the slot      -> written in place, rest zero-filled.
  * English is longer          -> written into the relocation POOL and every reference repointed:
      ptr_refs  : 32-bit pointers, rewritten.
      code_refs : the low instruction of a lui/addiu|ori pair; only its 16-bit immediate is
                  rewritten, so the new address must share the original %hi (the pool is
                  searched for space inside the same 64 KB page).
POOL = developer-only debug text (printf formats with ■■ markers, script-parser error
messages, animation-viewer key help). Retail code may still printf these to the IOP TTY;
overwriting them only changes that invisible log text. Documented in docs/elf_text.md.

python tools/elf_text.py list      -> print selected strings with slot sizes
python tools/elf_text.py pool      -> print pool capacity per 64 KB page
"""
import json
import re
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELF = os.path.join(ROOT, 'work', 'source', 'iso', 'SLPS_256.27')
SCAN = os.path.join(ROOT, 'work', 'source', 'scan', 'elf_strings.json')
BASE, FOFF = 0x100000, 0x80
INDENT_STR = '　' * 3 + '  '   # history-screen continuation indent: 3x18 px + 2x5 px = 64 px (see apply)

RANGES = [
    (0x323310, 0x323330),   # データがありません。
    (0x35F2D0, 0x35F2F0),   # 現在選択しているアビリティの
    (0x35F5E0, 0x35F6F0),   # parameter help lines (shooting / melee / armor / mobility / CP / psycommu)
    (0x35FF48, 0x360400),   # factions, ranks, skill names
    (0x361298, 0x3619A0),   # default original-pilot names
    (0x363B90, 0x363C40),   # promotion messages, ranks
    (0x363D10, 0x364F50),   # pilot history entries and retirement endings
]

# developer-only text usable as relocation space (start, end) - see module doc
POOL_RANGES = [
    (0x358CF0, 0x358D30),   # ■■通信ウィンドウ 同一キャラ...■■
    (0x358F80, 0x359000),   # R1/L1/R2/L2 anim viewer key help
    (0x359140, 0x3592F0),   # ■■インジケーター アニメーション情報表示■■ ...
    (0x35A740, 0x35A770),   # ■CHARGE SPPED UP...■
    (0x35AD30, 0x35AD60),   # ■■カットイン データ読み込み失敗■■
    (0x35CE90, 0x35CEC0),   # ■■オブジェクト名(%s)が見つかりません■■
    (0x35EAA0, 0x35EAD0),   # ■■搭乗ユニットによるスキル値ボーナス■■
    (0x35EE30, 0x35EED0),   # ■■スキル...■■ x3
    (0x35F130, 0x35F1B0),   # ■■スキルパネルデータ...■■ x2
    (0x362630, 0x362660),   # 無効なジャンプのとび先です
    (0x363070, 0x363180),   # <sel>/setCur errors
    (0x3637F0, 0x363A10),   # <%s>の定義限界 / 存在しないオブジェクト / <replace>
    (0x363A80, 0x363B90),   # same
    (0x363C60, 0x363C90),   # <bmes>テーブルの総数をオーバー
    (0x365050, 0x365080),   # <voice>テーブルの総数をオーバー
    (0x365140, 0x365190),   # <scroll>コマンド...
]


def load_elf(path=ELF):
    return bytearray(open(path, 'rb').read())


def slot_size(elf, addr, length):
    off = addr - BASE + FOFF
    end = off + length
    while end < len(elf) and elf[end] == 0:
        end += 1
    return end - off


def selected(elf=None):
    elf = elf or load_elf()
    out = []
    for s in json.load(open(SCAN, encoding='utf-8')):
        a = int(s['addr'], 16)
        if not any(lo <= a < hi for lo, hi in RANGES):
            continue
        out.append({'jp': s['jp'], 'addr': a, 'slot': slot_size(elf, a, s['len']),
                    'code_refs': [int(x, 16) for x in s['code_refs']],
                    'ptr_refs': [int(x, 16) for x in s['ptr_refs']]})
    return out


def occurrences():
    """For extract_text.py: [{'jp', 'file', 'addr', 'slot'}]."""
    return [{'jp': s['jp'], 'file': 'SLPS_256.27', 'addr': '%06X' % s['addr'], 'slot': s['slot']}
            for s in selected()]


def hi(a):
    return (a + 0x8000) >> 16


class Pool:
    def __init__(self, elf):
        self.free = []
        for lo, h in POOL_RANGES:
            # start on a 4-byte boundary after any string that precedes the range
            self.free.append([lo, h])

    def alloc(self, n, need_hi=None):
        for blk in self.free:
            a = (blk[0] + 3) & ~3
            if a + n <= blk[1] and (need_hi is None or (hi(a) == need_hi and hi(a + n) == need_hi)):
                blk[0] = a + n
                return a
        return None

    def left(self):
        return sum(max(0, h - l) for l, h in self.free)


def apply(elf, rows_by_jp, encode):
    """Write translations into the ELF image in place. rows_by_jp: {jp: en}. Returns report lines."""
    rep = []
    pool = Pool(elf)
    overflow = []
    for s in selected(elf):
        en = rows_by_jp.get(s['jp'])
        if not en:
            continue
        if re.search(r'\n {4,}', s['jp']):
            # Japanese continuation lines are indented to the history-screen text column. With the
            # VWF that column is at 65 px (date "0079.11" + 4 spaces = 67 px); written as 3 full-width
            # spaces (20 px each) + 1 space (5 px) = 7 bytes instead of 13 single spaces.
            en = re.sub(r'\n *', '\n' + INDENT_STR, en)
        b = encode(en) + b'\0'
        off = s['addr'] - BASE + FOFF
        if len(b) <= s['slot']:
            elf[off:off + s['slot']] = b + b'\0' * (s['slot'] - len(b))
        else:
            overflow.append((s, en, b))
    # every overflowing string is moved and all its references repointed, so its own slot is free
    # space too (zero-filled, then added to the pool). See docs/elf_text.md for the residual risk.
    for s, _, _ in overflow:
        off = s['addr'] - BASE + FOFF
        elf[off:off + s['slot']] = b'\0' * s['slot']
        pool.free.append([s['addr'], s['addr'] + s['slot']])
    for s, en, b in sorted(overflow, key=lambda x: -len(x[2])):
        his = {hi(s['addr'])} if s['code_refs'] else set()
        a = pool.alloc(len(b), next(iter(his)) if his else None)
        if a is None:
            rep.append('ELF NO SPACE %06X (%d > slot %d): %s' % (s['addr'], len(b), s['slot'], en))
            off = s['addr'] - BASE + FOFF
            elf[off:off + s['slot']] = encode(s['jp']) + b'\0' * (s['slot'] - len(encode(s['jp'])))
            continue
        po = a - BASE + FOFF
        elf[po:po + len(b)] = b
        for p in s['ptr_refs']:
            struct.pack_into('<I', elf, p - BASE + FOFF, a)
        for c in s['code_refs']:
            co = c - BASE + FOFF
            w = struct.unpack_from('<I', elf, co)[0]
            op = w >> 26
            lo = a & 0xFFFF if op == 0x0D else (a - (hi(a) << 16)) & 0xFFFF
            struct.pack_into('<I', elf, co, (w & 0xFFFF0000) | lo)
        rep.append('ELF relocated %06X -> %06X (%d bytes)' % (s['addr'], a, len(b)))
    rep.append('ELF pool left %d bytes' % pool.left())
    return rep


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    elf = load_elf()
    if cmd == 'list':
        S = selected(elf)
        for s in S:
            print('%06X slot %3d len %3d c%d p%d %s' % (s['addr'], s['slot'], len(s['jp'].encode('cp932')),
                  len(s['code_refs']), len(s['ptr_refs']), s['jp'].replace('\n', '/')))
        print('strings', len(S))
    elif cmd == 'pool':
        tot = {}
        for lo, h in POOL_RANGES:
            tot[hi(lo)] = tot.get(hi(lo), 0) + h - lo
        print({hex(k): v for k, v in tot.items()})
