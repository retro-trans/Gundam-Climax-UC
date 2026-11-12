# Review brief — Climax U.C. English translation

Read `BASE_RULES.md` (the "Shared review workflow" and your stage's section) and
`docs/translator_brief.md` (text rules: ASCII only, placeholders, byte budgets). This file adds how
the review stages run in this project.

## Input
`work/translation/en/review/<part>.txt` — the translated text in scene order (mission intros: one
`=== file` block per intro, lines in display order). Each line:

    S01750 | JP: <source> | EN: <current English>  [shared, also in: <other files>]

`\n` inside a row is shown as ` / `. A row marked **shared** is displayed in every file listed: any
edit must read correctly in all of them (Grep the other `review/*.txt` parts for the row id when the
other file is outside your part). Glossary: `work/glossary/characters.json`, `mobile_suits.json`,
`terms.json` (Grep for names; `en_game` wins over `en` when present). Do not change a glossary
spelling; report it instead.

## Stages
- **accuracy** — compare EN with JP, per BASE_RULES "When reviewing translation accuracy". Pay special
  attention to sentences that run across rows: the joins between rows (and between slices — rows
  were translated in batches of 80 by different people) must form correct English with nothing
  lost, duplicated or contradicted.
- **editorial** — per BASE_RULES "When doing an editorial pass". Narration register: documentary
  voice, **past tense** for the background; the closing line(s) that lead straight into the mission
  may switch to present tense only where the Japanese marks it as now (今、いよいよ、〜しようとしている).
  Never switch tense inside one sentence. Consistent terms across intros ("Federation Forces", not
  "EFF", in narration; one of "the Titans fleet" / "the Titans' main fleet" when the Japanese is the
  same). Also read `work/translation/en/review/editorial_notes_<group>.txt` — items the accuracy
  stage passed to you.
- **proofread** — per BASE_RULES "When proofreading".

## Output
`work/translation/en/review/out/<stage>_<part>.json` (UTF-8):

```json
{"stage": "accuracy", "part": "mission_intro_1", "rows_examined": 177,
 "edits": [{"id": "S01750", "en": "<full new English for the row>", "reason": "short reason"}],
 "returned": [{"id": "S01800", "to": "accuracy|editorial", "why": "..."}],
 "uncertain": ["S01766: ..."]}
```
- `en` is the complete replacement for the row (use `\n` for line breaks, as in the original row).
- Only list rows you change. Do not edit any other file; the orchestrator applies edits with a script.
- Keep line widths reasonable: mission-intro lines up to ~50 characters, nothing much wider than the
  current longest line in the same intro.

## Report back (final message)
rows examined, number of edits, the ids of substantive meaning changes with one-line reasons, and the
uncertain list. Keep it short.
