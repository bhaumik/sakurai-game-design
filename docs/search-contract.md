# Attributed contextual search contract

Use Python 3 with no third-party runtime dependencies. Invoke `skills/sakurai-game-design/scripts/search.py` from the repository, or use its absolute path. Retrieval reads the existing CSVs and all four versioned `knowledge/*.json` sidecars. It never rewrites the corpus.

## Commands

```bash
S=skills/sakurai-game-design/scripts/search.py
python3 "$S" "hits feel weak" -n 2 --context examples/context-sword.json --json
python3 "$S" --review "dialogue skip pause" --area ui -n 2 --context examples/context-cozy.json
python3 "$S" "beginner difficulty" --domain techniques --area balance
python3 "$S" "hit stop" --domain quotes --source sakurai --json
python3 "$S" --episode 47 --source sakurai
python3 "$S" --transcript 47 --source sakurai --json
python3 "$S" --areas --source sakurai
```

Supply exactly one positional query, `--review TEXT`, `--episode N`, `--transcript N`, or `--areas`. Episode numbers and `-n` must be positive. Empty queries, unknown domains/areas, conflicting modes and malformed context files are argument errors. `-n` is the maximum displayed result count **per selected dataset**, in both search and review, not a candidate budget. Group members are supporting records, not additional ranked results or independent confirmations.

`--domain` selects principles, techniques, lenses, episodes, quotes, or glossary and is honored in review. By default search and review select principles, techniques and lenses. `--area` filters only these three area-bearing datasets, including review. Quote, glossary and episode area combinations are explicitly rejected rather than silently returning empty results. Document and area-list modes accept `--source` and `--json`, but reject domain, area, context and custom result limits.

`--source` defaults to `sakurai:creating-games`. `sakurai`, `Masahiro Sakurai`, exact source IDs and exact catalogue author/work names resolve through the catalogue. An unknown selector or a pending source returns `source_mismatch`. A registered source does not acquire legacy CSV records merely by being registered. Legacy CSV records remain Sakurai-derived; future authored item records must carry their actual source ID. A query naming a known incompatible author, such as Raph Koster or Katherine Isbister, also returns `source_mismatch`, even when generic topic words match. Name recognition is a limited guard, not proof of comprehensive author identification.

Requests for `input buffering` or `coyote time` return `unsupported_topic`. These are documented gaps in this index, not evidence that no such source could exist elsewhere. No generic priority table or combat query is substituted.

## Project brief

Pass a local UTF-8 JSON object with `--context FILE`. Allowed keys are `audience`, `genre`, `mechanics`, `excluded_mechanics`, `desired_tension`, `core_appeal`, `platform`, `input`, and `stage`. Each supplied value is a nonempty string or an array of nonempty strings; empty arrays can represent no listed mechanics/exclusions. Unknown keys, null values, scalar numbers and malformed JSON are rejected.

Use explicit positive mechanics and explicit exclusions. The narrowly recognized phrases `no combat`, `non-fighting`, and `no time pressure` remove those phrases from positive query routing and establish exclusions. A cozy genre alone does not establish exclusions. The original query and supplied brief are retained in output.

Applicability uses additive curator condition tags, explicit project exclusions and conservative recognition of selected technique `when` fields. `requires_any` means at least one listed scope must be established; `excludes_any` is a context conflict. Supported scope vocabulary includes combat, fighting, reversal, anti_air, action, impact, hitstop, knockback, beginner, novice, casual, challenge, risk_reward, competitive, time_pressure, no_combat and no_pressure. Conditions can also use `context_field:value` or `context_field=value` for literal field matching. These checks are lexical scope checks, not a semantic guarantee of suitability.

## Ranking and review

Keep dependency-free BM25 with independent field normalization. Title weight is 5, keywords 3, condition/theme/tag fields 1.5, explanatory/application fields 1, examples 0.35 and warning fields 0.25. Source IDs, area labels, priorities, episode numbers, paths, URLs and linked item IDs do not contribute design-intent evidence. Query and area hints share the same lightweight stemming pipeline. A small novice/newcomer to beginner vocabulary is used. A transparent 1.4 hinted-area preference is a score multiplier, never a hard area gate. Matches below 0.25 of the best score in a domain are omitted. Scores from different domains are not calibrated.

Ordinary search ranks lexical relevance. Review ranks applicable findings first, then uses static priority within applicable findings. Conditional findings retain relevance order; priority cannot promote them above established scope. Results have one of these scope statuses:

- `applicable`: a stated limited precondition is present. Verify the actual design before proposing an experiment.
- `needs_context`: fit has not been established. Ask the included scope question; a generic item is not assumed universal.
- `not_applicable`: explicit context conflicts with its scope. Skip it with the reason.

No result carries a mandatory change. The caller still decides whether an applicable finding addresses an observed project problem. Grouped skip/pause concerns preserve UI-01's online-pause exception and PLAN-21's speed/line-skip detail. Audience-risk grouping preserves BAL-01 and CASE-01 as related interpretations/examples, not independent confirmations. Exact quotes are deduplicated by normalized text plus episode and timestamp, retaining `themes` and `duplicate_count`.

## JSON response

`--json` emits a single JSON document with `schema_version: "1.0"` and no Markdown. Search/review responses contain:

| Field | Contract |
|---|---|
| `mode`, `query` | Search or review and original text |
| `filters` | Selected domains, area, source selector/resolved source ID and displayed limit |
| `context`, `inferred_exclusions`, `hinted_areas` | Supplied context and explicit lexical routing diagnostics |
| `status` | `ok`, `partial_match`, `no_match`, `source_mismatch`, `unsupported_topic`, or `data_error` |
| `messages`, `unsupported_terms` | Limitations and unmatched normalized query terms; unmatched is not proof a concept is absent from all sources |
| `results` | Object keyed by selected domain, each containing ranked result arrays |
| `concern_groups` | Supporting principle members with individual application detail, conditions and sources; count concern once |

Each result includes `id`, `title`, `domain`, `rank`, `score`, `area`, `priority`, `source_id`, `author`, `matched_fields` with normalized tokens/role weights/field scores, `matched_tokens`, `area_boost`, `status`, `applicability`, `evidence_type`, `record`, `sources`, `claims`, `claim_locator_status`, `qualifiers` and `concept_group`. Legacy entity IDs remain unchanged. Episode IDs resolve to immutable catalogue document IDs; quotes have deterministic local hash IDs, glossary IDs use their normalized term.

`applicability` contains its status, reason, context question, conditions, basis, explicit exclusions, matched conditions and `mandatory_change: false`. Claims retain their source-versus-interpretation type, review status, limitations and context. Claim evidence joins its immutable document and segment pointers. Timestamp claims receive time-linked source URLs. `retained_text_checked` means checked against the inherited text only, not audiovisual verification. Segment `suspect` flags and unreviewed OCR statuses remain visible.

Every indexed episode reference joins catalogue documents even for uncurated items. Each document provides author, work, immutable document/source IDs, original URL, source URL, notes/transcript paths, availability flags, language, translation layer and review status. Quotes additionally preserve their stored timestamp and `time_url`. A result without curated claims has `claim_locator_status: "unavailable"`; episode-level links must not be presented as precise passage evidence. No timestamp is borrowed from a different quote.

Document JSON responses provide `content` and resolved `sources`; the area-list response provides `areas`. Successful empty, unsupported-topic and source-mismatch responses exit 0 with machine-distinguishable statuses. Argument errors exit 2. Missing/corrupt required CSVs or sidecars, broken claim-document/segment joins, and missing requested document files exit 1 with `data_error` (JSON if requested, otherwise stderr). A nonexistent positive episode number exits 1 with a clean `episode N not found` error. No traceback is printed for these expected failures.

## Evidence limits

The index is lexical, not an exhaustive source interpretation. Original retained transcripts came through third-party OCR of official English on-screen subtitles. Their existence, hashes and current source links do not prove subtitle accuracy, completeness or agreement with Japanese narration. Keep retrieved synthesis, attributed source statements and proposed project experiments separate. Inspect the relevant notes, retained passage and original video when wording or nuance matters. Keep public quotations short and link the original source.
