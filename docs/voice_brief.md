# Voice subtitle brief — Mobile Suit Gundam: Climax U.C. (PS2)

Read `BASE_RULES.md` and `docs/translator_brief.md` first (glossary, spelling sources, ASCII-only
rules all apply). This file covers what is different for voiced lines.

## What these rows are
Spoken lines that have no on-screen text in the game. The Japanese is a **machine transcript**
(Whisper speech recognition), not the game script. It is usually right, but it mis-hears names and
rare words, e.g. 神湯ヴィラン for カミーユ・ビダン (Kamille Bidan), 総長 for 曹長, 小島 for コジマ,
磁気 for 自機. Fix the meaning from context; never translate a mis-hearing literally.

## Inputs
- Your slice: `work/translation/en/voice/slices/<slice>.json`, rows in scene order. Neighbouring
  slices may be read for context.
- Glossary excerpt: `<slice>.gloss.json` (entries whose Japanese appears in the slice). Mis-heard
  names will not be in it: Grep the full glossary (`work/glossary/characters.json`,
  `mobile_suits.json`, `terms.json`) for the character you believe is meant.
- Row fields:
  - `id` clip name, e.g. `evc009_sl1_ze.adi`. Families: `evt` tutorial (instructor talking to the
    player), `br_cNN_MM` Chronicle-mode briefing voice-over for stage NN (narrator / commanders),
    `evc` Chronicle in-mission lines, `evp` Progress-mode in-mission lines.
  - `speaker`: 3-letter character code from the clip name (amr = Amuro, chr = Char, brt = Bright,
    kam = Kamille, sir = Sayla, ...). Work them out from content; report your mapping in `speakers`.
    Codes like `sl1`, `p1a`, `op7`, `ag7` are generic soldiers / operators.
  - `sec`: length of the line in seconds. `missions`: trigger scripts that play it (`cn_fg01` =
    Chronicle, `pr_0a01` = Progress, `tu_to01` = tutorial, `db07` = other modes).
  - `asr: "low"`: Whisper was unsure; check extra carefully.

## How to write the subtitles
- Natural spoken English in the character's voice (Amuro earnest, Char composed and ironic, soldiers
  clipped). Keep the official names and ranks from the glossary.
- Subtitle length: readers need time. Aim for at most ~17 characters per second of `sec`
  (a 3-second line ≈ 50 characters); for longer text tighten the wording, never drop meaning.
  The tool wraps at ~70 characters per line, 2 lines per page, and pages long lines automatically.
- One row in, one row out. Do not merge rows.
- Battle cries, grunts and screams: short ("Take this!", "Argh!"). Empty or pure noise transcript:
  `en: ""` with `flag: "no speech"`.
- If the transcript is too garbled to be sure of the meaning, write your best reading and add a
  `note`; if you cannot get the meaning at all, leave `en` empty and set `flag`.
- When you fix a clear mis-hearing, put the corrected Japanese in `jp_fixed` (short, just the line).
- ASCII only (no curly quotes, no ellipsis character: use `...`).

## Output
`work/translation/en/voice/slices/out/<slice>.json` (UTF-8):
```json
{"slice": "v01", "rows_in_slice": 200, "rows_examined": 200,
 "rows": [{"id": "evt001_kam_zg.adi", "en": "So you're the new pilot? I'm Kamille Bidan.",
           "jp_fixed": "<corrected Japanese line>", "note": "..."},
          {"id": "...", "en": "", "flag": "why"}],
 "speakers": {"kam": "Kamille Bidan"},
 "decisions": ["notes that apply to several rows"],
 "uncertain": ["clip: what you were unsure of and what you chose"]}
```
Do not edit any other file.

## Report back (final message)
Rows examined vs rows in slice, flagged clips, and the `uncertain` list, one line each.

## Review stages (accuracy / editorial / proofread)
Read `BASE_RULES.md` ("Shared review workflow" and your stage) and `docs/review_brief.md` (output
format, `returned`, `uncertain`); this section adds the voice specifics.
- Input: `work/translation/en/voice/review/vr<N>.txt`, scene order, one clip per line:
  `clip | length | speaker code | JP: transcript (or the translator's corrected jp_fixed) | EN: subtitle`.
  The slice outputs in `work/translation/en/voice/slices/out/` hold each translator's `speakers`,
  `decisions`, `uncertain` and per-row `note`; read the notes for rows you question.
- The JP is a machine transcript: judge the English against what the line most plausibly says in
  its scene, not against an obvious mis-hearing. Change meaning only with evidence from context.
- Consistency across the whole corpus (slices were translated by different people): names and ranks
  per glossary (`Kamuna Tachibana`; Bright is Commander in the Zeta era). Decided: 隊長 used to
  address the player's unit leader is "Commander" everywhere (slice v03 wrote "Captain"; fix those);
  a ship's captain addressed as 艦長 stays "Captain". Also check
  recurring terms (Trojan Horse, GP02, Cyber Newtype). Report conflicts you find in `uncertain`.
- Subtitle length: about 17 characters per second of clip length; tighten rather than drop meaning.
- Output: `work/translation/en/voice/review/out/<stage>_vr<N>.json`, `id` = clip name, `en` = the
  complete new subtitle. Only list clips you change.

## Movies (Progress-mode cutscenes, endings, character events)
- Input: `work/translation/en/voice/movies/m<N>.json`, one row per Whisper segment, in playback order:
  `{"id": "cuc_pg_ca001.pss#03", "start": 12.4, "end": 15.9, "jp": "...", "asr": "low"?}`.
  `cuc_pg_ca*` are the Progress-mode story scenes (the player's unit: Kamuna Tachibana, Ellen
  Rochefil, Shirley Ramsey, Pamir McDamil; later the 2nd generation), `pg_ed*` are the Progress
  endings, `ham` / `qua_zg` / `sbk_91` short character events. The voice subtitle slices
  (`work/translation/en/voice/slices/out/v09-v12.json`) hold the same characters' in-mission lines.
- One row in, one row out; keep the segment timing. You may merge a sentence that Whisper split
  across two rows: put the whole English on the first row, set its `"end"` to the second row's end,
  and give the second row `en: ""` with `flag: "merged into #NN"`. Whisper sometimes hallucinates
  text over music or silence (e.g. "thanks for watching", repeated words): give such rows `en: ""`
  and `flag: "no speech"`.
- Reading speed: about 17 characters per second of the row's own length (end - start).
- Output: `work/translation/en/voice/movies/out/m<N>.json`, same format as the voice slices
  (`rows`: id, en, jp_fixed?, note?, flag?, start?/end?; plus speakers, decisions, uncertain).

## Sortie lines and card quotes (slices v13, v14)
- `s###` clips: short in-mission lines (launch calls such as "Amuro, Gundam, launching!", death
  screams, surprised shouts). Keep them short; screams can be "Aaagh!".
- `d_###` clips: the character-card voice quotes in the card gallery, mostly famous lines from the
  anime ("こいつ、動くぞ"). `speaker` is the character code with era (`amr_fg` = Amuro, 0079). When a
  quote is an iconic line with a well-known official English rendering, use the natural, recognisable
  wording; do not invent a citation. One quote per row.
