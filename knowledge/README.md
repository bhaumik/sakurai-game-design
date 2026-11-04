# Context and evidence sidecars

The legacy CSVs remain searchable views of the inherited knowledge. These sidecars add stable provenance and contextual annotations without rewriting the original transcripts or renumbering published IDs.

`catalogue.json` defines source families and immutable documents. The Sakurai documents use `youtube:<video_id>` as their identity; `episode` is only a legacy display/lookup alias. Explicit source paths and hashes preserve the retained source revision. Isbister's book is pending, with no imported chapter text or book claims.

`segments.json` contains 3,950 paragraph pointers into the inherited OCR transcripts. Raw wording stays in the original file rather than being duplicated here. Each segment has a stable document/timestamp ID and text hash. `next_start_seconds` is the next paragraph's reading boundary, not an exact subtitle end or an original OCR segment time recovered from video.

`claims.json` contains a curated pilot of 24 claims. It covers the four oldest high-priority episodes, one qualifying source, and selected Smash impact/knockback examples. Each claim maps to existing item IDs and field-level evidence. A mapping supports the claim's own text, not every sentence of a consolidated CSV record.

`annotations.json` adds conditions, qualifier relations, and grouped concepts for selected records. `applicability_basis: curator_inference` means these are our retrieval judgments, not a verbatim author-defined taxonomy. Empty condition lists do not prove a rule universally applicable. Unannotated records remain conditional evidence candidates.

## Quality labels

`unreviewed_ocr` means the retained source was captured by OCR and has not been audiovisual-verified in this fork. `retained_text_checked` means a curated claim was compared against that retained text. It does not establish accurate OCR, complete visual evidence, or Japanese-to-English translation fidelity. Use `visually_verified` only after actually reviewing the relevant source, and document who/what verified it.

Seven explicit corruption flags are recorded in the correction queue. Their `proposed_text` is null and `status` is unresolved. Do not guess missing words or sales figures. Preserve the raw source, store an independently verified correction separately, and update dependent claims transparently. Passing structural validation is not proof of truth.

## Add a source without changing existing identities

Add a distinct source record with author, work, language/edition where available, family identity, kind, rights note, and available/pending status. Add immutable document IDs, explicit locations, and the appropriate locator kind. Video claims use timestamp ranges and segment IDs; book claims use actual page ranges. Keep direct reading separate from references quoted through another author.

Add new claims and namespaced item IDs instead of overwriting the inherited CSV entities. Include author attribution and modality. Connect sources only through evidenced support, qualification, or alternatives. Do not add a relationship merely because two titles sound similar.

`tools/build_catalogue.py` is a bootstrap/snapshot tool for the inherited channel index, not a universal importer or a routine way to overwrite curated metadata. It rejects changed published aliases, paths, or retained text hashes. A future document revision needs an explicit reviewed migration. Source-order changes and display-title edits must not renumber documents.

## Integration gates

Run `python3 tools/validate.py` and `python3 -m unittest discover -s tests -v`. Read `CONTRIBUTING.md` before editing authored inputs or rebuilding generated outputs. A second-source schema fixture is not a claim about that source, and an experiment template is not an empirical result.
