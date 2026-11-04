# Contextual knowledge reliability implementation

Approved goal: improve this fork as an attributed, context-sensitive game-design reference for AI collaborators. Preserve the existing study guide and source files. Do not claim to emulate Sakurai personally or convert his examples into universal commandments.

## Delivery scope

Add dependency-free schema and relation validation with mutation fixtures and CI. Harden builders against silent data loss. Preserve stable legacy IDs and introduce immutable source/document IDs and typed evidence locators.

Add context-aware search and review, JSON output, source restriction, honest unsupported-topic/no-match statuses, explicit argument validation, deduplication, and evidence joins. Keep the existing Markdown commands working where their contracts are valid. Add regression tests for hit feel, beginner games, non-combat/no-pressure designs, source mismatch, and invalid CLI arguments.

Curate a small evidence pilot for the four oldest high-priority episodes, preserving original retained text and correction boundaries. Add qualifier relationships and application experiment templates. Include a chronological Smash study path distinguishing core mechanics from history and production.

Improve README, roadmap, contribution/ownership guidance, and the existing agent skill. Do not silently install a skill. Harden the optional OCR pipeline without downloading or processing the whole channel again.

## Evidence data contract

`knowledge/catalogue.json` has `schema_version`, `sources`, and `documents`. Sources contain `source_id`, `author`, `work`, `kind`, `language`, `status`, and `url`. The current source ID is `sakurai:creating-games`. Documents contain immutable `document_id` of `youtube:<video_id>`, `source_id`, legacy integer `episode`, `title`, `url`, explicit `notes_path`, `transcript_path`, `language`, `translation_layer`, `review_status`, and `transcript_sha256`. A future book uses its own namespace and page locators. Pending sources contain no invented documents or claims.

`knowledge/claims.json` has `schema_version` and `claims`. Claims contain stable `claim_id`, `item_ids`, `field`, `text`, `claim_type`, `evidence`, and `review_status`. Evidence includes `document_id`, `locator` with `kind`, timestamp seconds and segment IDs where known. Retained-text checking is distinct from audiovisual verification.

`knowledge/annotations.json` has `schema_version`, `items`, and `corrections`. `items` maps existing entity IDs to additive records: `conditions` with `requires_any` and `excludes_any`, `applicability_basis`, `evidence_claim_ids`, `related` with `item_id` and `relation`, and optional `concept_group`. Conditions and relationships are curator interpretations unless explicitly source-grounded. Corrections must preserve raw source text and review status. CSV schemas remain backward compatible; new metadata lives in this validated sidecar.

`knowledge/segments.json` retains stable document/timestamp-based segment IDs and raw transcript text with its hash. It is a migration snapshot of retained OCR text, not recovered original OCR output or proof of subtitle accuracy.

## Work ownership

The integration owner owns source metadata, curated evidence, study paths, README/roadmap/contribution guidance, and release commits. The retrieval worker owns the search utility, agent skill, query fixtures/examples, and retrieval tests. The validation worker owns contracts/validators, offline builders, validation/build tests, and CI. The acquisition worker owns optional OCR/acquisition safety tools, source profiles, and pipeline tests. Workers do not commit, push, or edit each other's files.

## Completion gates

Run read-only validation, the complete unit suite, skill validation, JSON and Markdown CLI smoke tests, and an offline rebuild in a temporary copy. Confirm existing identities and raw transcripts remain unchanged. Push to `bhaumik/sakurai-game-design` only, not upstream. Report implemented features separately from remaining work.

## Explicit boundaries

No accessible Isbister chapters have been supplied. Register that source as pending and test page-locator support using clearly synthetic fixtures, not fabricated book takeaways. OCR defects can be flagged and linked without guessing corrections. Full audiovisual verification remains a later source-review task. Do not grant a new license over inherited content or contact rights holders without a separate request. Public output should use concise summaries and source locators, not new transcript redistribution.
