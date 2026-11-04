---
name: sakurai-game-design
description: "Search attributed local game-design evidence derived from Masahiro Sakurai on Creating Games. Use when designing, tuning, reviewing or planning player-facing mechanics, controls, difficulty, hit feel, pacing, UI, visual/audio clarity, scope, playtests or production; also use for questions about the indexed Sakurai material. Retrieve contextual principles, techniques, lenses and short quotes with source locators. Establish project fit before recommending changes; this is not a universal checklist or an emulation of Sakurai."
---

# Sakurai Game Design

Use this local reference as evidence for a particular project, not as authority to replace its premise. The existing datasets cover principles, techniques, review lenses, quotes, glossary terms and episode notes/transcripts. Notes and design records are synthesis. Retained English transcript text came through third-party OCR of on-screen subtitles; do not assert that every transcript or quote is accurate or audiovisually verified.

## Establish context and source

Ask for the target player's experience, genre, active and excluded mechanics, intended tension, core appeal, platform/input and development stage when these affect the decision. Preserve the user's intended experience. A non-combat gardening story does not need danger, escalating pressure or hitstop merely because a general design rule mentions them.

Select the requested corpus with `--source`. The imported legacy records belong to `sakurai:creating-games`. Pending sources, including Isbister material without supplied/imported chapters, cannot support author-specific findings. Treat `source_mismatch` as a limitation, not permission to answer another author's question using Sakurai material. Do not claim to speak as Sakurai or predict what he personally would do.

Read `study-guide/01-how-sakurai-thinks.md` for tensions and source context before open-ended application. Use its caveats, not a universal hierarchy of mandatory checks. In particular, audience and core appeal can qualify risk/reward advice; not every game seeks challenge.

## Run local retrieval

Use the full path to `<skill-base>/scripts/search.py`, or the repository path below. Python 3 is sufficient; no runtime installation is needed.

```bash
S=skills/sakurai-game-design/scripts/search.py
python3 "$S" "hits feel weak" --context examples/context-sword.json -n 2 --json
python3 "$S" "beginner difficulty" --domain techniques --area balance
python3 "$S" --review "dialogue skip pause" --context examples/context-cozy.json --area ui -n 2
python3 "$S" "hit stop" --domain quotes --source sakurai
python3 "$S" --episode 47 --source sakurai
python3 "$S" --transcript 47 --source sakurai
python3 "$S" --areas
```

Pass `--context FILE` with a JSON object whose allowed keys are `audience`, `genre`, `mechanics`, `excluded_mechanics`, `desired_tension`, `core_appeal`, `platform`, `input` and `stage`; values are strings or arrays of strings. Consult `docs/search-contract.md` from the repository for complete validation, JSON fields and command behavior.

Select one dataset with `--domain principles|techniques|lenses|episodes|quotes|glossary`. Review honors the same selector. Use `--area essence|balance|planning|feel|animation|visuals|audio|ui|team|craft|marketing|tech|case-study` only with principles, techniques or lenses. Quote, glossary and episode area filters are explicitly unsupported. `-n` is a positive displayed limit per dataset, including review. Do not combine positional queries with review/document/list modes.

## Query and interpretation

Query one concern in a few plain words, such as `hitstop sword`, `beginner difficulty` or `menu help text`. Keep explicit exclusions in the brief. Explicit `no combat`, `non-fighting` and `no time pressure` text is also safely recognized; genre labels alone are not exclusions.

Inspect status, matched fields, scope reason and supporting documents. Warning-only matches are not recipes for the current game. Scores rank lexical evidence within a dataset; do not compare scores across datasets as calibrated confidence. Retry once with narrower words or an appropriate area when results miss the intent. If evidence remains insufficient, report the limitation. Do not substitute a universal priority table, a combat example or invented numbers.

Treat `applicable` as an established limited scope, not proof that a change is desirable. Treat `needs_context` as a question or conditional option. Treat `not_applicable` as a skipped finding with its reason. Never require changes from conditional/skipped lenses. Missing metadata is a data error, not a genuine no-match result.

Recognize `source_mismatch`, `unsupported_topic`, `partial_match` and `no_match` separately. The index has documented gaps for input buffering and coyote time. Do not fill these gaps with generic lag advice or attribute an outside technical recipe to Sakurai. Do not assume this means every source lacks the topic. The library is not a comprehensive source of tuning constants; use only constants actually supported by a cited passage and label all other values as experimental starting points.

## Apply evidence to a design

For a new feature, establish audience and intended experience, query only relevant concerns, check conditions and read cited evidence. Identify the observed design problem before selecting a technique. Specify tunable parameters and verification appropriate to the platform and mechanic. Cite entity IDs and document links alongside decisions.

For a review, retrieve a contextual brief and evaluate applicable findings before static priority. Summarize the observed behavior, source-grounded point, project-specific synthesis and proposed test separately. Rank accepted findings by impact on this player and goal. Group UI-01/PLAN-21 and BAL-01/CASE-01 when they address one underlying concern; preserve exceptions and do not count overlapping synthesis as independent confirmation. Scope any study-guide checklist to the game rather than requiring every item.

For tuning, compare one change at a time against a baseline. Consider accessibility and readability costs as well as the intended effect. A sword-hit experiment may test hitstop; a dialogue experience may instead test text pacing, player-controlled skipping or clarity. Do not require impact stop/shake/flash, risk/reward or failure pressure for every genre.

For an attributed answer, retrieve the relevant principles or short quotes, then inspect the linked note and transcript passage. Use claim-level locators when available. If only episode-level sources are joined, explicitly state that passage-level precision is unavailable. Inspect original audiovisual material when needed for exact wording or unresolved OCR defects. Keep public quotations short and link the original source.

## Preserve evidence boundaries

Distinguish **source statement**, **retrieved synthesis**, **curator applicability interpretation** and **proposed experiment** in the response. Retain qualifiers and linked counterpoints. `retained_text_checked` validates agreement with inherited text, not video, original OCR output or Japanese narration. Read document/segment review statuses and suspect flags before making stronger claims. Do not guess corrections to defective retained text.

Before delivery, verify that the recommendation serves the supplied audience and core appeal, respects exclusions, has adequate source support and can be tested. State unresolved context or source gaps instead of inventing a mandatory fix.

## References

| Repository-relative file | Use |
|---|---|
| `docs/search-contract.md` | CLI modes, contextual scope checks, failure states and JSON contract |
| `study-guide/01-how-sakurai-thinks.md` | Interpretive habits, tensions and contextual caveats |
| `study-guide/02-*.md` through `14-*.md` | Area chapters, examples and exercises |
| `study-guide/checklists.md` | Optional questions to select only after establishing fit |
| `skills/sakurai-game-design/references/quick-reference.md` | Principle index |
| `skills/sakurai-game-design/references/techniques.md` | Existing technique synthesis |
| `episodes/notes/NNN-*.md`, `episodes/transcripts/NNN-*.md` | Notes and retained OCR transcript text |
| `knowledge/catalogue.json`, `claims.json`, `annotations.json`, `segments.json` | Source identity, limited claim evidence, context interpretations and retained-text pointers |

Respect source rights. No new permission over inherited content is granted. Do not redistribute long transcript passages or present a pending book as an imported corpus.
