# Sakurai game-design knowledge, with context

A contextual game-design reference for developers and AI collaborators, based on the 261 non-compilation episodes of [Masahiro Sakurai on Creating Games](https://www.youtube.com/@sora_sakurai_en/videos). This is a fork of [flossbud/sakurai-game-design](https://github.com/flossbud/sakurai-game-design), whose transcripts, notes, study guide, and searchable synthesis provide the foundation.

The inherited library includes 302 principles, 291 techniques, 114 review lenses, 230 glossary terms, and attributed quote records. It already has examples, rationales, technique conditions, and contextual tensions. This fork adds provenance, applicability checks, machine-readable retrieval, validation/tests, and a safe contribution path. It does not claim to be Sakurai or to replace playtesting.

## Start reading

Read the [study guide](study-guide/README.md) for the existing 14-chapter synthesis. Start with [how Sakurai thinks](study-guide/01-how-sakurai-thinks.md), and keep its tensions in view. For a platform fighter, follow the [chronological Smash study path](study-guide/smash-study-path.md): original concept, attack structure, Melee's tradeoffs, hitstop, knockback, then balance/testing candidates.

For exact attribution, open the linked episode and inspect its source context. The retained transcripts are third-party OCR captures of the official English on-screen subtitles. They contain known defects and have not all been audiovisually verified. A polished takeaway is not proof of exact wording.

## Quickstart for any agent or developer

Use Python 3.11 or newer. Search, validation, and the offline builders use the standard library; optional video acquisition/OCR dependencies are separate.

```bash
git clone https://github.com/bhaumik/sakurai-game-design.git
cd sakurai-game-design
python3 tools/validate.py
python3 -m unittest discover -s tests -v

S=skills/sakurai-game-design/scripts/search.py
python3 "$S" "hitstop sword" --area feel -n 3
python3 "$S" --review "sword impact and launch" --context examples/platform-fighter.json --json
python3 "$S" --episode 47
python3 "$S" --transcript 145
```

The sample game brief is illustrative, not a specification for your project. Replace its audience, mechanics, exclusions, intended experience, platform/input, and stage with your own. Review results are evidence candidates: inspect their applicability status and reason before proposing a change. `needs_context` is not permission to apply the rule blindly.

The JSON response separates source identity, query status, ranked results, applicability, and resolved evidence. Unsupported authors/topics and missing data must not silently become unrelated recommendations. Context checks are conservative heuristics over a curated subset, not an expert judgment guarantee. See the [search contract](docs/search-contract.md) for flags, response fields, limits, and examples.

## Optional Claude Code plugin

The plain Python route above does not require Claude Code. To use the inherited plugin packaging with this fork:

```text
/plugin marketplace add bhaumik/sakurai-game-design
/plugin install sakurai-game-design@sakurai-game-design
```

No plugin or Manus skill is installed by cloning or by this update. Keep the full repository layout for episode source lookup; copying only the skill directory loses its sibling evidence paths.

## What is where

```text
README.md, ROADMAP.md       purpose, quickstart, completed and remaining work
AGENTS.md, CONTRIBUTING.md  worker boundaries, authored/generated ownership, safe handoffs
study-guide/               existing chapters, derived references, Smash study path
episodes/                  inherited index, episode notes, retained raw OCR transcripts
knowledge/                 stable sources/documents, paragraph pointers, curated evidence and conditions
skills/sakurai-game-design/ agent instructions, dependency-free retrieval, legacy CSV views
examples/                  illustrative game briefs for contextual queries
experiments/               unrun application-test templates, not empirical findings
tools/                     validation, offline generation, optional acquisition/OCR
profiles/                  explicit acquisition/OCR source configuration
work/batches/, work/parts/  authored extraction/synthesis inputs, not disposable build debris
tests/, .github/workflows/  regression fixtures and CI gates
```

## Evidence and context pilot

[Knowledge sidecars](knowledge/README.md) attach immutable video IDs to all 261 source documents and index 3,950 retained-text paragraphs. The curated pilot maps 24 claims to passages from the four oldest high-priority videos, one source qualification, and selected Smash impact/knockback examples. It annotates 31 existing records and tracks seven unresolved OCR flags.

`retained_text_checked` means the pilot claim was compared with inherited OCR text, not with the original video or Japanese narration. The raw transcripts remain unchanged. Source statements, source examples, synthesis, and application hypotheses have distinct labels. Most inherited consolidated records still lack curated claim-level locators; retrieval must make that precision limit visible.

The context layer links selected rules to their qualifications and groups overlapping concerns. It cannot infer every design intent from a few words. Read existing `when`/`pitfalls` fields and ask for missing context rather than imposing risk, combat, or time pressure on a game whose appeal lies elsewhere.

## Add other sources without blending authors

Katherine Isbister's [How Games Move Us: Emotion by Design](https://direct.mit.edu/books/book/3115/How-Games-Move-UsEmotion-by-Design) is registered as pending. No chapter text or book takeaways have been imported. An accessible copy or supplied excerpts are needed for a real pilot.

Source IDs, document IDs, and typed timestamp/page locators distinguish authors and source families. A synthetic book fixture tests structure, not the book's findings. Read the [roadmap](ROADMAP.md) and [contribution guide](CONTRIBUTING.md) before extending the corpus. Keep author disagreements and alternative goals visible.

## Rebuild and contribute safely

Edit authored JSONL inputs, not only generated CSVs. For a synthesis edit:

```bash
python3 tools/build_data.py data
python3 tools/build_guide.py
python3 tools/validate.py
python3 -m unittest discover -s tests -v
```

Batch edits additionally need the areas stage and explicit re-synthesis of affected areas. Authored notes and chapters do not regenerate automatically. The [contribution guide](CONTRIBUTING.md) explains ownership and invalidation. Validate before publishing, and exercise builders in a temporary copy when changing them.

The source-catalogue bootstrap is not an everyday overwrite command. Existing aliases, paths, and source hashes are preserved; reviewed revisions need explicit migrations. Optional reacquisition should not be confused with rebuilding existing structured data. See [acquisition documentation](docs/acquisition.md) and [validation documentation](docs/validation.md).

## Provenance and rights

Upstream built this library by downloading non-compilation videos, OCR-reading on-screen English subtitles, writing parallel episode notes, and synthesizing chapters and structured records. The original schemas are in [NOTES_SPEC](tools/NOTES_SPEC.md) and [SYNTHESIS_SPEC](tools/SYNTHESIS_SPEC.md). Checking quotations against retained OCR is different from independently checking source video.

Inherited content remains attributed to its creators. The plugin is `UNLICENSED`; this fork does not grant a blanket permissive license or claim that full transcript redistribution is authorized. See [rights and provenance](docs/rights-and-provenance.md). Quote briefly, summarize originally, and link exact evidence rather than copying long passages into public output.
