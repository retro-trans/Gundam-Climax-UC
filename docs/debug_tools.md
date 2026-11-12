# Debug tools — Mobile Suit Gundam: Climax U.C. (SLPS-25627)

General method: `debug_tools_guide.md`. This file holds this game's implementation,
addresses and savestates. All addresses are EE virtual addresses. Named constants live in
`tools/debug/addrs.py`.

## Tools

| Step | Tool | File | Status |
| --- | --- | --- | --- |
| 1 | Emulator control | `tools/debug/emu.py` (start/stop/status; only kills `work/emulator/pcsx2/pcsx2-qt.exe`) | done |
| 1 | Debugger link | `tools/debug/pine.py` — PINE IPC (PCSX2 2.8.2 has no GDB stub). Memory r/w, savestate save/load | done |
| 2 | Input injection + frame clock | `tools/debug/gdbg.py press/seq` — hook at the end of `scePadRead` | done |
| 2 | Screenshots | `tools/debug/gdbg.py shot` — saves state to slot 9 and pulls `Screenshot.png` out of the `.p2s` | done |
| 3 | Savestate reader | `tools/debug/savestate.py` (`ram`, `diff`, `shot`) | done |
| 4 | Function tracer | `Dbg.trace(addr, ...)` in `gdbg.py` — logs a0–a3, ra, sp, gp of the first 64 calls | done |
| 4 | String / stack tracer | `Dbg.trace_str(addr, reg, n, maxn)`; `gdbg.py tracestr <addr> [s] [reg]` logs the string a register points to (e.g. stream names at 0x177940) | done |
| 4 | Stack walker | `tools/debug/stackwalk.py <func> [s] [button]` — snapshots the stack at a function entry and unwinds with the ELF prologues | done |
| 4 | Draw experiment | `tools/debug/subtest.py install <func|jal site> x y scale [text]` — draws text with the game renderer from a hook | done |
| 5 | Safe halt | `gdbg.py halt/resume` — the pad hook spins while `MB_HALT_REQ != 0` | done (single game thread only; see limits) |
| 5 | Debug cheats | unlock all cards: write `01 01` × 423 at `*(0x36FE34) + 0x1D0` | done (manual, see below) |
| 6 | Hot reload | not yet | todo |
| 7 | Scene preview | not yet (no dialogue interpreter in this game — text is C2B/inf data) | todo |
| 8 | Coverage scan | `tools/extract_text.py` on the built GAME.MB vs the original | todo |
| — | Boot helper | `tools/debug/boot_to.py <iso> title|tutorial` | partial (intro skip timing is fragile) |

## Emulator

- Portable PCSX2 2.8.2 in `work/emulator/pcsx2/` (`portable.ini` present), config in `inis/PCSX2.ini`.
- BIOS `scph39001.bin` (copied from the user's PCSX2 folder).
- PINE enabled on port **28111** (`GUNDAM_PINE_PORT` overrides). Audio muted (volume 0).
- Savestate files are named by ELF CRC: original `E21D5682`, patched builds differ — `savestate.slot_path`
  picks the newest file for a slot.

## Addresses

| Name | Address | Meaning |
| --- | --- | --- |
| `SCE_PAD_READ` | `0x157558` | libpad `scePadRead(port, slot, rdata)`; `rdata` kept in `$s2` |
| `SCE_PAD_READ_EPILOGUE` | `0x157694` | `ld $ra,0x40($sp)` → replaced by `j DEBUG_CAVE` (delay slot `ld $s3` runs twice, harmless) |
| `DEBUG_CAVE` | `0x4AD000` | debug-only code cave (zero at runtime in intro/menus/gallery; installer checks) |
| `MAILBOX` | `0x4ADF00` | +0 buttons (u16, active-high), +4 pad-read counter, +8 halt request, +C halted, +10 magic `GDBG` |
| trace cave / buffer | `0x4AD400` / `0x4AD800` | function tracer |
| `$gp` | `0x3778F0` | read with the tracer |
| card ownership | `*(gp-0x7ABC)+0x1D0` = `*(0x36FE34)+0x1D0` | 423 × 2 bytes: [opened, owned]; `IsCardOwned` = `0x2D4CA0` |
| font file in RAM | `0x7B0890` (this session) | `s18rm04.ufm`; pointer kept in resident-file slot `0x32DD74` |
| `FONT_LOADER` | `0x1F4F50` | loads `s18rm04.ufm` via `0x16A700` |

Font class `CUmeStdFont` (vtable `0x36CE30`, subclass `ATetsuFont` vtable `0x36E2A0`):

| vtable slot | Address | Method |
| --- | --- | --- |
| 0x30 | `0x198350` | SJIS → JIS (ASCII b → `0x2900+b`, half-width kana b → `0x2980+b`) |
| 0x34 | `0x198260` | glyph pointer: map at `data+0x10`, index `(row-0x21)*96+(col-0x20)`; glyph size/offset from the header |
| 0x38 | `0x1981A0` | GetCharWidth(font, char*): 2-byte → `*(*(font+0x450)+4)` (20), 1-byte → `0x197BF0` |
| — | `0x197BF0` | HalfWidth(font, byte): originally `width/2` → **patched for VWF** (see `docs/vwf.md`) |
| — | `0x197C30` | glyph cache (`font+0x4C8`, keyed by JIS code) — why hot-reloading glyphs needs a reboot |

## Pad bits (libpad rdata[2..3], LE u16, raw active-low; mailbox is active-high)

select 0x0001, l3 0x0002, r3 0x0004, start 0x0008, up 0x0010, right 0x0020, down 0x0040,
left 0x0080, l2 0x0100, r2 0x0200, l1 0x0400, r1 0x0800, triangle 0x1000, circle 0x2000,
cross 0x4000, square 0x8000. Japanese layout: ○ confirm, × back.

## Savestates (`work/emulator/states/`)

| File | Build | Place |
| --- | --- | --- |
| `v000_tutorial_select.p2s` | original | first-boot tutorial stage select |
| `v001-vwftest_unit_viewer_all_cards.p2s` | 0.0.1-vwftest | Unit Viewer, all 423 cards unlocked (RAM only) |
| `v016_tutorial_confirm.p2s` | 0.1.6 (subtitle ELF, 1,190 clips) | tutorial Beginner, OK/Cancel confirm before the briefing |

## Limits / notes
- **Runtime code patches and PCSX2's EE recompiler:** code written over PINE is not always picked up
  by blocks the recompiler already compiled (worked for 0x218DB0 and new code, failed for the main
  loop and the task dispatcher). `Dbg.flush_rec()` (save + reload a savestate) is tried
  automatically by the tracers but did not fix every case. A trace with 0 calls therefore does not
  prove a function is idle; for patches that must run, build them into the ELF
  (`tools/build.py <ver> --elf-only` rewrites only the executable in an existing build).
- Savestates restore RAM including the ELF code: after an ELF change, boot fresh (states made with
  an older ELF run the old code).

- Safe halt stops only the thread that calls `scePadRead`. Patching code that another thread may be
  executing is not covered yet.
- The tracer patches two instructions at the function entry; they must not be branches.
- The first Start press after boot is sometimes swallowed by the intro movie; `boot_to.py` timing
  needs a scene detector (todo).
- Hot reload of font glyphs does not show until reboot because of the glyph cache.
- Menu confirm presses need a longer hold: `gdbg.py press circle 10 10` (the default 4 frames is
  sometimes ignored on the stage-select screens).
- A savestate taken during a load or movie has no `Screenshot.png`; `gdbg.py shot` then times out with
  "savestate not written" — wait and shoot again.
- Old savestates bring back their RAM: text loaded at boot (`card_info.inf`, the executable) stays the
  old version; screens entered after loading read the new disc (mission intros, menus). From
  `states/v001-vwftest_unit_viewer_all_cards.p2s`: Back x3 = main menu; ring: Right x3 + wait =
  Chronicle Mode; Circle (Amuro) / Circle (stage) / Circle (confirm) = first mission intro.
