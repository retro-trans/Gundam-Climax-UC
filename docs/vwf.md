# Variable-width font

## How the game draws text

- Font file: `s18rm04.ufm` in GAME.MB (format in `tools/ufm_tool.py`): 7,864 glyphs,
  20×18 px, 2 bpp, map indexed by JIS code. Loaded once and kept resident.
- Text is Shift-JIS. Single-byte ASCII is drawn with the font's half-width glyphs
  (JIS row 0x29 = SJIS 0x85xx), which sit centred-left in the 20 px cell.
- Advance per character comes from `CUmeStdFont::GetCharWidth` (vtable slot 0x38, `0x1981A0`):
  20 px for 2-byte characters, `HalfWidth()` (`0x197BF0`) = 10 px for any single byte ≥ 0x20.
  On screen a full-width character advances 18 px (measured 2026-11-10 on the briefing header and the
  stage-select title against the original game); `textenc.FULL_PX` uses 18.

## Patch

1. Font file (`vwf.build_font`):
   - every ASCII glyph 0x21–0x7E is shifted left so its ink starts at column 0;
   - a 256-byte width table is appended (ink width + 1 px; space = 5; control bytes 0;
     bytes ≥ 0x80 keep 10);
   - header `+6` = `'VW'` (0x5756), header `+8` = table offset. The header bytes 5–15 were
     zero and unused (the game only reads bytes 0–5).
   - Size grows 723,904 → 724,160 bytes; the entry's sector allocation is 724,992 bytes.
2. ELF (`vwf.halfwidth_patch`), 16 words at `0x197BF0` (the old function + its padding):
   ```
   andi v0,a1,0xff ; lw v1,0x484(a0)        ; font data pointer
   beqz v1,fallback ; nop
   lhu t0,6(v1) ; ori t1,zero,0x5756
   bne t0,t1,fallback ; lw t2,8(v1)
   addu v1,v1,t2 ; addu v1,v1,v0 ; jr ra ; lbu v0,0(v1)
   fallback: lw v0,0x450(a0) ; lw v0,4(v0) ; jr ra ; sra v0,v0,1
   ```
   Fonts without the magic (e.g. `ATetsuFont`/`NEC_FONT`) keep the old 10 px advance.

## Real-hardware notes

- No disc layout change: the font keeps its sector, the ELF its size.
- Behaviour change: the original returned 0 for bytes < 0x20; the fallback path now returns
  `width/2` for them. With our font the table returns 0. Only fonts without the magic could
  see a difference, and only if they are asked to measure a control byte.

## Verified

- Build 0.0.1-vwftest: tutorial stage-select strings injected as ASCII render proportionally
  (`work/ui/shots/vwf_test_iso.png`, `vwf_zoom.png`).

## Bold Latin glyphs (0.1.1)
The original half-width Latin glyphs are 1 px strokes and read thin at 1x. `vwf.embolden_halfwidth`
(enabled by `vwf.BOLD`) copies every ink pixel one column to the right after left-alignment, so vertical
stems become 2 px and horizontals stay 1 px — the same construction as the Skies of Arcadia Latin font
used by the Seireiki Rayblade patch (compared in `work/ui/font_compare/`). Level 2 is full ink in this
font (kanji use 0..2 as well), so no level change is needed. The width table is measured after
emboldening (about +1 px per letter). The 'j' hook is shortened to 1 px left of the stem, because
left-aligned glyphs cannot overhang the previous letter.
Alternatives tried and rejected: the font's full-width Latin set (bold but ~30% wider lines and
squashed descenders) and a soft-edge bold (stripy at 1x).
Reverted in 0.1.2 by request (`vwf.BOLD = False`); the code stays available. The 'j' fix is now a
separate step, `vwf.fix_j_hook` (hook 2 px left of the stem, `vwf.J_HOOK`), applied in every build.
