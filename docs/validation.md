# Offline validation and reliable builds

## Supported commands

The offline tools use only the Python standard library. Python 3.11 is the supported baseline; CI runs Python 3.11 and 3.12. No acquisition, OCR packages, installation, or network access is required.

```sh
python3 tools/validate.py --root .
python3 tools/validate.py --root . --json
python3 -m unittest discover -s tests
python3 tools/build_data.py areas --root .
python3 tools/build_data.py data --root .
python3 tools/build_guide.py --root .
```

`--root` is optional and defaults to the script's repository. Validation is read-only and returns exit status 0 on success or 1 on structural failure. JSON output contains `ok`, `errors`, `warnings`, and `counts`. Diagnostics identify the input file and JSONL line, CSV row, or JSON record where possible.

## Enforced input contracts

Validation requires the episode index, assigned batch files and range manifest, nonempty input collections for every part kind, all six CSV views, generated area projections, and the four knowledge sidecars. CSV column order and schemas remain compatible. JSON objects reject unexpected fields and duplicate keys. Missing required fields, invalid types, unknown areas or priorities, duplicate entity IDs, dangling episode references, and dangling lens-to-principle references fail rather than being dropped or filed under a fallback area.

Batch ranges must cover every indexed episode exactly once, without overlap. A batch may contain only its assigned episodes. Part area names must match their owning filename. Explicit note and transcript paths must exist inside the selected repository, including after symlink resolution. Optional empty anti-patterns, examples, pitfalls, episode lists, and similar legacy fields are allowed. Empty tag or game lists are valid, and a non-lesson episode may have no principle candidates.

Full read-only validation checks CSV and area projections against their authored batch and part inputs. Rebuilding uses a separate input preflight, not comparison with potentially stale exports. A guide build validates required CSVs and their references, and requires the authored chapters it links to. It does not silently substitute an empty dataset or omit unknown episode links.

## Additive evidence contracts

`knowledge/catalogue.json`, `claims.json`, `annotations.json`, and `segments.json` are required for release validation and builds. Supported schema versions are integer `1` and string `"1.0"`. Catalogue sources use namespaced IDs and `available` or `pending` status. Pending sources cannot own documents or claims. No accessible Isbister material is invented by the validators or fixtures.

Video documents join the immutable `youtube:<video_id>` identity to the legacy episode index, matching the video URL, explicit source paths, and retained transcript SHA-256. Non-video documents cannot have episode aliases. Evidence uses typed timestamp or page locators, with numeric range checks and document foreign keys. Book-page tests use clearly synthetic fixture documents, not fabricated source findings.

Retained segments point to timestamp paragraphs through document ID, timestamp, path, and line number. Validation checks paragraph text hashes, document hashes, segment identities, and evidence joins. Claims reference existing items and documents. Annotations reference existing items, evidence claims, related items, and declared concept groups where a group catalogue is supplied. Without a separate group catalogue, `concept_group` is an additive nonblank grouping label. Corrections retain a raw-text field or an immutable retained segment pointer; an unresolved correction may have `proposed_text: null`.

These are structural checks, not proof of subtitle fidelity, a bibliographically correct edition, an author's endorsement, audiovisual verification, or universal applicability. `retained_text_checked` means comparison with the retained text only. Suspect OCR segments generate warnings and do not structurally invalidate the corpus. Timestamp reading-range ends and next-paragraph starts are not promised to be exact subtitle end times.

## Generated output ownership

The `areas` build writes `skills/sakurai-game-design/data/episodes.csv` and known `work/areas/<area>.jsonl` files. It retires obsolete known generated area files, never an unknown filename or authored Markdown file. The `data` build writes the five entity CSVs. The guide build writes only `study-guide/checklists.md`, `glossary.md`, `episode-index.md`, and the skill's `references/quick-reference.md` and `techniques.md`.

Builders do not rewrite notes, transcripts, authored chapters, source records, claims, annotations, corrections, or segments. Additional metadata belongs in validated sidecars rather than undeclared CSV or part fields. Unexpected keys fail preflight, preventing silent data loss.

Glossary merge behavior is retained: case-insensitive terms keep the first meaning and merge episode references in stable order. Quotes deduplicate only when normalized text, episode, and timestamp all match, merging themes in stable order. Equal text at different source locators remains separate, preserving citation provenance. Full validation accepts the legacy duplicated quote view by comparing its normalized merge, while rebuilding publishes the deduplicated view.

## Publication guarantees and limits

All generated content is prepared and staged before replacement. A normal rendering or validation exception leaves existing published artifacts unchanged. Publication uses atomic replacement per file and restores already-replaced files on ordinary publication exceptions. Tests inject a replacement failure to verify rollback.

This is not a whole-tree atomic transaction under power loss, process termination, concurrent builders, a permanently failing filesystem, or a failed rollback. Run shared-output builds serially through the integration owner. Staging or rollback failures may leave newly created empty directories, but do not intentionally remove authored content. Snapshotting and content-addressed generations would be required for stronger crash consistency.

## Regression fixtures

Tests construct small reproducible corpora in temporary directories. They mutate required fields, unexpected fields, IDs, priorities, domains, types, batch ownership, references, paths, hashes, source status, and locators. Builder tests assert byte-for-byte preservation on failures, repeatable output, sidecar preservation, glossary merging, quote provenance, and safe stale-area retirement. They do not rebuild the shared checkout.
