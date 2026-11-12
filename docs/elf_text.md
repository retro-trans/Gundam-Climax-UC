# Executable text (SLPS_256.27)

`tools/elf_text.py` handles the player-facing Shift-JIS strings that live in the game executable
rather than in GAME.MB. `tools/extract_text.py` adds them to `strings.json` as group `elf`
(occurrence `{"file": "SLPS_256.27", "addr", "slot"}`); `tools/build.py` writes the translations.

## What is included (`RANGES`)
| Address range | Content |
|---|---|
| 0x323310 | "No data" message |
| 0x35F2D0, 0x35F5E0–0x35F6EF | ability / parameter help lines |
| 0x35FF48–0x3603FF | faction names, ranks, skill names (pointer table at 0x33FA..) |
| 0x361298–0x36199F | default names for the original pilot (Tachibana family, epithet names) |
| 0x363B90–0x363C3F | promotion messages, ranks |
| 0x363D10–0x364F4F | pilot history entries and retirement endings |

Everything else in the executable is developer text (task names, printf formats, debug menus) and
is left alone. Not included yet, unverified whether players see them: 0x326C60 プログレス,
0x327C90 リザルトのシャッフル, 0x3326D0 部分再生, 0x332A40 表示ＯＮ, 0x332DB0 再生モード選択.

## How it is written
- **Slot** = the string's bytes plus the zero padding up to the next string. English that fits is
  written in place and the rest of the slot is zero-filled.
- **Longer English** is copied into the relocation pool and every reference is repointed:
  - `ptr_refs`: absolute 32-bit pointers (found by scanning every word of the image) are rewritten;
  - `code_refs`: the low instruction (`addiu`/`ori`/load/store) of a `lui` pair gets a new 16-bit
    immediate. The `lui` is not touched, so the new address must have the same `%hi`; the pool is
    searched only for space in the same 64 KB page.
- **Pool** (`POOL_RANGES`, ~2.4 KB, all in page 0x36): developer-only text — `■■…■■` debug printf
  formats, script-parser error messages, animation-viewer key help. Retail code can still pass these
  to `printf` (IOP TTY); after the patch it prints English text instead, without `%` conversions
  (so no argument mismatch). No visible effect.
- The build writes `work/build/elf_text_report.txt`: every relocation and any string that did not
  fit (`ELF NO SPACE`, left in Japanese).

## Real-hardware notes
- File size and every segment stay unchanged; only bytes inside the existing `.rodata` strings and
  16-bit immediates / data pointers change. Nothing depends on emulator behaviour.
- Risk: a reference the scanners did not find (an address built some other way than `lui` + low
  instruction within 24 instructions, or a computed offset into a table). Such a reference would
  still point at the old slot (see the next point for what it would show). Check skill / ending
  screens in game after each change to this list.
- The original slots of relocated strings **are** reused as pool space (zero-filled first). Needed:
  the history / retirement texts keep their indented continuation lines and would not fit
  otherwise. Consequence of a missed reference: it would show another string's English, or an empty
  string — visible, not a crash (the slot always holds a NUL-terminated string or zeros). Check the
  pilot history, skill list and ending screens in game.
- Continuation-line indent (strings whose Japanese has `\n` + spaces): written as 3 full-width spaces
  + 1 space = 65 px, the history-screen text column with the VWF (date `0079.11` + 4 spaces = 67 px).
  The GAME.MB history templates use 13 ASCII spaces for the same 65 px.
