# Mobile Suit Gundam: Climax U.C. — translation project

An open toolchain for translating **Mobile Suit Gundam: Climax U.C.** (PlayStation 2,
SLPS-25627), plus the English translation built with it.

## Contribute

This is an early release. The menus, briefings, mission intros, card gallery and pilot histories are
translated, and the voiced scenes have English subtitles, but most of the game has only been checked
by automated tests and a few in-emulator spot checks. If you want to contribute to this project or the
next in any way — be it bug reports, proofreading or playtesting — please join my Discord:

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)** · [Report an issue](https://github.com/retro-trans/Gundam-Climax-UC/issues)

## Play it

The latest release is **[v0.8.0](https://github.com/retro-trans/Gundam-Climax-UC/releases/tag/v0.8.0)**,
one patch for the Japanese release (**SLPS-25627**). It adds English subtitles to the voiced
scenes and Progress-mode cutscenes on top of the translated text, menus and graphics.

### Apply

Use [Retro Trans](https://github.com/retro-trans/retro-trans-tools), or apply the `.xdelta` with
DeltaPatcher or xdelta3. You need your own unpacked Japanese disc image.

| Your source image | Patch |
|---|---|
| Japanese release, SLPS-25627 | `GundamClimaxUC-English-v0.8.0.xdelta` |

The source must be this exact image (`Mobile Suit Gundam - Climax U.C. (Japan).iso`,
4,416,110,592 bytes, SHA-1 `d2bec2bc57201a43394790be120245f1cdc42439`). Check the hashes in
`README-v0.8.0.txt` if your patcher reports a mismatch; keep checksum verification enabled.

For example:

```
xdelta3 -d -s "Mobile Suit Gundam - Climax U.C. (Japan).iso" GundamClimaxUC-English-v0.8.0.xdelta "Mobile Suit Gundam - Climax U.C. (English v0.8.0).iso"
```

For manual patching of a CHD, extract it to an ISO first; Retro Trans Automatic supports compatible
CHD inputs.

**Boot the new image fresh.** Old emulator save states keep the previous executable and graphics;
memory-card saves are fine.

## What is translated

| Part | |
|---|---|
| Text | 2,921 strings: menus, help lines, briefings, stage names, mission intros, pilot histories, endings, system messages |
| Executable text | 322 strings: skill, faction and rank names, promotion messages, default pilot names |
| Card gallery | 423 cards (names, labels, models, descriptions) |
| Graphics | 178 images: title menu, briefing labels, skill / stat / rank / personality / faction plates, result screens |
| Voice subtitles | 2,324 voiced lines: tutorials, Chronicle briefing voice-over, Chronicle and Progress missions |
| Movie subtitles | 144 lines in 30 movies: Progress-mode cutscenes and endings, character events |
| Font | variable-width English in the game's own font |

Not translated yet: the series title logos on the Chronicle stage select and MS select, and the battle
voice barks (3,192 short clips, left out by design).

## How the subtitles work

The game has no subtitles of its own. The voiced lines were transcribed from the game's audio with
Whisper, translated and reviewed, and a small patch in the executable draws them with the game's own
text renderer while a clip or movie plays. Details: [docs/subtitles.md](docs/subtitles.md).

## Build it yourself

You need your own copy of the game. This repository contains no disc image, no game data and no dump
of the original Japanese script; the working files that hold Japanese text stay on your machine.

1. Put your image at the repository root as `Mobile Suit Gundam - Climax U.C. (Japan).iso`.
2. Copy `SLPS_256.27` and the `MB` folder from the image to `work/source/iso/`.
3. Unpack the archives:
   ```sh
   python tools/mb_tool.py extract work/source/iso/MB/GAME.MB work/source/game
   python tools/fpk_tool.py extract_all work/source/game work/source/fpk
   ```
4. Recreate the working files from your disc and the committed English:
   ```sh
   python tools/restore_work.py            # dry run
   python tools/restore_work.py --write
   ```
5. Build: `python tools/build.py 0.8.0` writes `work/output/Gundam_Climax_UC_EN_v0.8.0.iso`.

Python 3 with `numpy`, `Pillow`, `keystone-engine` and `capstone`. The title-menu text uses the
Noto Sans JP font (SIL OFL) from the Windows font folder.

## Translate it

Fork it to fix the English, or to take the game into another language. Each translation file has an
English copy in git (`*.en.json`); after `restore_work.py`, edit the working file and run
`python tools/strip_jp.py` before committing.

| Path | Contents |
|---|---|
| `work/translation/en/strings.en.json` | game text, keyed by permanent row id |
| `work/translation/en/cards.en.json` | card gallery |
| `work/translation/en/subtitles.en.json` | voice and movie subtitles |
| `work/glossary/` | names and terms with sources (Gundam Official first) |
| `tools/` | extraction, insertion, font, texture, subtitle and build tools |
| `docs/` | formats, the text engine, VWF, textures, subtitles, review briefs |
| `BASE_RULES.md` | portable rules for running a project like this |
| `CHANGELOG.md` | every build, what changed, and what broke |

## Do not sell this

This patch is free. Do not sell it, and do not sell anything made with it -
no pre-patched discs or images, no loaded memory cards or consoles, no
paywalled or ad-gated downloads.

It is an unofficial fan translation of a game Bandai Namco owns. Selling it
takes money for work that was given away, and it is the surest way to get a
project like this shut down.

## Credits

| Role | |
|---|---|
| Project lead | pow |
| Playtesting | pow |

Translation passes, subtitle transcription, tooling and reverse engineering were done with Claude
(Anthropic), directed by pow. The translation is machine-produced and then edited - see the release
notes for what that means in practice.

Names and terminology follow [Gundam Official](https://en.gundam-official.com/), then the Gundam
Wiki. Title-menu text is drawn with [Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP)
(SIL Open Font License). Speech was transcribed with OpenAI Whisper (faster-whisper).

## Status

The translation is in progress. `CHANGELOG.md` is the honest record, including what has and has not
been checked in game. No human proofreading has been done yet; every line is machine-translated and
then reviewed in accuracy, editorial and proofreading passes.
