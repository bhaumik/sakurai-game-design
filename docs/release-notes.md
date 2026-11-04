# Contextual reliability release

This fork's 1.1.0 update improves the use of Sakurai's existing library for a particular game's goals. It preserves the inherited raw transcripts, episode identities, notes, narrative chapters, and upstream attribution. The implementation plan was published before code changes.

## Shipped

Search and review now accept a game brief, treat explicit exclusions as exclusions, and return `applicable`, `needs_context`, or `not_applicable` rather than mandatory fixes. Per-field lexical ranking avoids using paths and IDs as design evidence. Review honors its area/domain filters and displayed limits. Invalid arguments and missing data fail explicitly. Unsupported authors, pending sources, documented topic gaps, and genuine no-match results have distinct statuses.

Versioned JSON output joins source identity, URLs, note/transcript paths, matched fields, curated claim locators, uncertainty, and relevant qualifier/group links. Markdown remains available. Exact quote duplicates are suppressed in retrieval and the rebuilt quote view contains 126 rows instead of 130. Distinct source locations remain distinct.

The evidence sidecars register all 261 source documents with immutable video-based IDs and 3,950 retained-paragraph pointers. The curated pilot contains 24 claims, 31 item annotations, and seven unresolved OCR flags. Its coverage includes the four oldest high-priority lessons, a risk/reward qualification, and selected Smash hitstop/knockback examples. `retained_text_checked` means compared to retained OCR only, not audiovisual verification.

Read-only contracts enforce schemas, ID uniqueness, ownership, coverage, references, safe paths, source hashes, and typed locators. Offline builders preflight their inputs, prepare outputs before publication, and support rollback on ordinary exceptions. Fixture tests and GitHub CI cover the dependency-free runtime. The optional acquisition/OCR tools add frozen listing controls, checked workers/FFmpeg, provenance-aware cache validation, raw-revision retention, and stable transcript planning.

The README, roadmap, contribution guide, and agent-facing guidance describe scope and authored/generated ownership. The existing agent skill now requires project fit and evidence boundaries instead of a universal risk/combat hierarchy. A chronological Smash study path and two unrun experiment templates support practical learning. No skill has been installed into a user's account.

## Verification performed

All 162 local unit tests passed on Python 3.12.3. Strict corpus validation passed; its warning preserves seven suspect OCR spans. The existing skill passed its validator. Shell syntax and Git whitespace checks passed.

An isolated full rebuild preserved 620 source and authored files byte-for-byte and produced deterministic output on a repeat build. Its only generated-view change was quote deduplication. The checked source set includes the inherited episode index, all transcripts and notes, authored chapters, synthesis inputs, and the new knowledge sidecars. Serial publication of the generated views then passed validation. Raw transcripts and the episode index have no Git diff from upstream.

Regression cases include weak-hit wording variants, beginner/non-fighting requests, a gardening narrative with no combat/time pressure, positive sword-impact retrieval, source mismatch, unsupported concepts, genuine negatives, invalid CLI values, corrupt inputs, and builder/pipeline failures. An integration boundary test ensures generic single-hit combat does not establish the scope of a fixed multi-hit knockback recipe.

CI is configured for Python 3.11 and 3.12. The local environment tested 3.12; a CI configuration is not itself proof of remote success. Fixture-based pipeline tests are not a real download, video-decode, or OCR integration test.

## Still pending

Full audiovisual source review and verified correction of the flagged OCR passages remain open. Most consolidated records do not yet have curated claim-level evidence. Applicability rules are conservative lexical heuristics, not comprehensive expert judgment. No prototype or participant experiment has been run.

Isbister's How Games Move Us is registered as pending. No book chapters or takeaways have been invented or imported. An accessible copy or excerpts, actual edition/page locators, and a small attributed pilot are needed. A synthetic book-page fixture establishes only schema behavior.

The optional pipeline still needs real integration with tested external package/model versions and retained assets. Historical acquisition/OCR provenance was not reconstructed. Publication has per-file atomicity and ordinary-exception rollback, not a power-loss-safe whole-tree transaction or support for concurrent writers.

Inherited code/analysis/source-text permissions still need clarification before new redistribution or licensing claims. The plugin remains UNLICENSED, preserves flossbud's authorship, and grants no new rights over inherited material. No rights holder has been contacted in this update.
