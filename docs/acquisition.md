# Optional acquisition and OCR

## Scope and provenance boundary

The committed notes, batches, parts, index and raw transcripts are the retained inputs for offline knowledge work. Offline validation, catalogue metadata migration and derived-data rebuilding do not require yt-dlp, Node, FFmpeg, NumPy, ONNX Runtime or RapidOCR. Use the repository's offline validation and rebuilding instructions for that work, not the acquisition commands below.

The original videos, original channel listing, exact original OCR outputs, original model assets and original dependency versions have not been recovered. **No current original acquisition provenance has been reconstructed.** Hashing an existing transcript establishes its retained bytes, not its audiovisual accuracy, original download identity or original OCR model. Catalogue and segment metadata for inherited text are offline migration metadata, not a retroactive acquisition manifest.

This optional pipeline records observations for future runs and adds safety controls. It does not establish complete reproducibility. No network acquisition, actual video decode, actual OCR, dependency installation or model download was performed to test this change. Local synthetic fixtures were tested with Python 3.12.3. The declared standard-library baseline is Python 3.10 or later; other baselines remain untested.

## Owned inputs and outputs

`profiles/sakurai-english.json` names the existing English channel and inherited OCR assumptions: scale to 1280 by 720, crop the bottom 108 pixels starting at y=612, sample four frames per second, and identify white subtitle text on a dark bar. These assumptions are source-specific and have not been newly visually verified. A changed profile is a changed OCR fingerprint. This is not an arbitrary-source ingestion contract; new sources still require curator-reviewed source and evidence metadata.

Acquisition and OCR work directories are external working artifacts, not committed evidence or authored notes. They may contain frozen TSV snapshots, videos, yt-dlp info JSON, logs, raw OCR JSON, an acquisition manifest and an OCR completion manifest. Keep large video/model assets out of the repository. Preserve these artifacts independently if later reproducibility matters.

`episodes/index.csv` remains authoritative for existing video-to-episode aliases and transcript paths. Transcript publication does not edit notes, knowledge sidecars, claims, catalogue data or correction annotations. Existing raw Markdown transcripts are retained by default. A proposed correction sidecar is never read into or applied to raw OCR or raw transcripts.

## Frozen listing and explicit refresh

The existing shell entry point is retained:

```sh
tools/fetch_videos.sh /path/to/work --listing /path/to/frozen-videos.tsv
```

A TSV has exactly three tab-separated columns: video ID, title and numeric duration in seconds. It uses the original yt-dlp flat-playlist format. Duplicate IDs, invalid durations and empty eligible listings fail validation. Compilation exclusions come from the source profile.

Without `--listing`, the command requires an existing `/path/to/work/videos.tsv`. It never refreshes the live listing implicitly. To explicitly request a new listing and download its eligible assets:

```sh
tools/fetch_videos.sh /path/to/new-work --refresh --jobs 3
```

These commands perform network acquisition and are examples only, not commands run during implementation. A failed or malformed refresh leaves the previous `videos.tsv` untouched. Every validated listing is frozen as `listings/<sha256>.tsv`; historical snapshots are not deleted. A supplied legacy TSV is marked as having unknown original acquisition provenance. A live refresh records that it was explicitly requested, not that it reproduces the inherited listing.

Both commands accept `--profile PATH` and positive `--jobs N`. Worker commands avoid error-ignoring download options. Each child must exit successfully and produce the expected nonempty `<video_id>.mp4`, remuxing to MP4 if needed. FFprobe must identify a valid video stream. Only then may a completion manifest be published. Expected asset paths, SHA-256 hashes, sizes, observed dimensions, available selected-format metadata and CLI version outputs are recorded. A pre-existing asset can be observed and hashed, but its original acquisition remains unknown. A changed hash relative to a previous acquisition manifest is rejected; use a new work directory for a reviewed source revision.

A failed batch may leave independently acquired assets and logs for inspection. It does not publish a new successful completion manifest. A pre-existing completion manifest is historical and must be matched against the current listing/profile/assets before treating it as current. Concurrent acquisition processes using the same work directory are unsupported.

## OCR and validated caches

The two-positional-argument OCR CLI and shell wrapper are retained:

```sh
python -I tools/ocr_subs.py /path/to/work/video/VIDEO_ID.mp4 /path/to/work/ocr/VIDEO_ID.json
tools/run_ocr.sh /path/to/work /path/to/ocr-environment/bin/python --jobs 3
```

Optional arguments are `--profile PATH`, `--rec-model PATH`, and `--force`. The shell wrapper also accepts `--listing TSV` to specify the frozen expected-video set. It rejects missing expected videos before starting any workers and validates every expected result after checking every child exit status.

The dependencies are imported only when actual OCR is requested. A cache inspection imports no NumPy, RapidOCR or ONNX Runtime:

```sh
python -I tools/ocr_subs.py VIDEO.mp4 OUTPUT.json --check-cache --rec-model /path/to/local-recognition.onnx
```

This exits zero only when the cache is structurally valid, has matching integrity and provenance fingerprints, has an identified local recognition model, and has resolved package and FFmpeg/FFprobe version observations. It does not decode video or recognize text, although hashing video/model files and obtaining installed CLI version outputs require local I/O.

Fingerprints include video bytes, explicit recognition model bytes when supplied, the full source profile, Python/platform information, installed optional package versions, FFmpeg/FFprobe outputs and OCR/helper code hashes. Changed inputs, configuration, model, tool versions or code invalidate the cache. Malformed/truncated JSON, legacy unversioned segment lists, invalid segments, mismatched raw-segment integrity hashes and stale fingerprints are not accepted as reusable caches. Cache inspection uses absolute local model selection paths, so moving an asset can cause a conservative miss.

Without `--rec-model`, the RapidOCR default model identity and hash are explicitly unresolved. Output may still be produced by an explicitly requested OCR run, but it is never reused as a pinned cache. Default RapidOCR initialization may fetch model assets; that optional operation requires an authorized environment and is not part of offline validation. An explicit local model is configured through RapidOCR's `Rec.model_path` parameter, with detection/classification disabled for recognition-only crops. Installed API compatibility and the loaded model path must be verified before claiming a selected model is pinned. This configuration still needs a real OCR integration test with a supported dependency version.

For an explicit model, the implementation observes the recognizer's ONNX Runtime session model path and compares its file hash with the configured asset. A matching configuration field alone is not accepted as evidence of use. A mismatched loaded asset or an installed release that does not expose this observation fails closed without replacing OCR output. This runtime introspection is covered by synthetic objects, not yet by a real installed OCR integration.

FFmpeg exit status is checked after reading all frames. Failed decoding, partial frames and zero-frame output fail clearly. A generator closed early terminates its child. Stderr uses a temporary file to avoid a blocked stdout/stderr pipe. Output is serialized and validated before a same-directory temporary file is fsynced and atomically replaced. A failed decode or recognition never replaces the prior OCR JSON.

Before a changed OCR output is replaced, its previous bytes are preserved as `ocr/raw-revisions/<video_id>/<old_sha256>.json`. These historical bytes may themselves be malformed or have unknown legacy provenance; archival retention does not validate them, and they are never considered current caches. Reacquisition or changed recognition can therefore create an observable source revision without deleting the prior raw result. Concurrent writers in one work directory are unsupported.

New OCR JSON uses an envelope with `schema_version`, `fingerprint`, `provenance`, `segments`, `segments_sha256`, `raw_segment_preservation` and `review_status`. Segments retain timestamps, recognition text and original engine text-line strings. Consecutive recognized segments are not editorially merged or corrected. Blank recognition and one-frame transition samples are omitted by the inherited heuristic; “raw preservation” refers to retained recognized segments, not lossless preservation of every source frame or subtitle. The review status is `unreviewed_ocr_not_visually_verified`, never “verified”. This envelope intentionally replaces the unsafe unversioned OCR-list output format. The transcript builder still reads retained legacy lists but labels their provenance unknown, and cache reuse never accepts them.

## Transcript planning and stable aliases

The existing three positional arguments are retained:

```sh
python tools/build_transcripts.py /path/to/work/videos.tsv /path/to/work/ocr /path/to/staging-repository --plan-only
```

`--plan-only` validates inputs and prints additive plan metadata without writing files. The builder maps videos through the authoritative `episodes/index.csv`, sorts by retained episode IDs, and keeps each indexed transcript path even when a fresh listing is reordered or a title changes. Unknown or absent indexed videos fail with an identity mismatch instead of renumbering or silently dropping episodes. A curator must review additions and extend the authoritative index separately; no automatic source-addition contract is invented here.

A genuinely new, empty output tree requires `--initialize-index` to explicitly bootstrap the original oldest-first aliases from a frozen listing. It is refused when raw transcripts already exist without an authoritative index. Do not use it to recreate IDs for the current repository.

Without `--replace-existing`, raw transcripts already present at authoritative paths are retained byte-for-byte. The index can adopt a fresh title/category/duration while keeping its old path and retained word count. The generation manifest marks such documents `existing_raw_retained_not_regenerated`; the incoming OCR pointer and proposed projection hash are candidates, not a claim that the current transcript was newly regenerated from that OCR. This is also why title edits do not silently relocate source files.

Use a copied staging repository for reviewed reacquisition. `--replace-existing` is an explicit raw source revision, not a mechanism for applying editorial corrections. Previous bytes are first archived under `episodes/transcript-revisions/<video_id>/<old_sha256>.md`. Integration must review the source revision and update dependent metadata deliberately; catalogue tools that reject changed source hashes are expected to block an unreviewed replacement. Never publish this directly over the inherited repository merely to test the pipeline.

All OCR inputs are validated before any output publication. Unindexed OCR JSON files, mismatched video identity and versioned OCR profiles differing from the requested source profile are rejected. Missing OCR and legitimately empty OCR are errors unless the video has an explicit reviewed empty-source decision:

```json
{
  "schema_version": 1,
  "decisions": [
    {
      "video_id": "SYNTHETIC_EXAMPLE",
      "status": "reviewed_empty_source",
      "reviewed_by": "Reviewer identity",
      "reason": "Specific reviewed reason why no source text is expected"
    }
  ]
}
```

Supply that file with `--empty-source-decisions PATH`. The example is synthetic, not a decision about an actual episode. Decisions require a reviewer and reason, reject unknown/duplicate IDs, and cannot hide malformed OCR. They authorize an explicitly marked empty projection, not inferred audiovisual verification. Raw OCR JSON is never modified by this builder, and correction annotations remain separate.

The CSV columns remain unchanged. Additive `episodes/transcript-generation.json` records stable `youtube:<video_id>` document IDs, retained episode aliases and paths, candidate OCR hashes/fingerprints, proposed/current transcript hashes, preservation status, source profile, builder hash and explicit provenance/review limits. Nothing in it claims original inherited acquisition has been reconstructed.

Publication validates and prepares the complete set first. Files are individually atomically replaced, with rollback on ordinary write exceptions and the generation manifest written last. **This is not a cross-file power-loss transaction.** Inspect a staging tree and the final manifest before integration; interrupted processes, concurrent writers and filesystem failure during rollback still require recovery. No indiscriminate stale-file deletion occurs, and authored notes are never cleaned.

## Dependencies and remaining work

`profiles/versions-manifest.template.json` is a manifest template, not a lockfile. Optional tested versions, dependency artifact hashes, model identity/origin/license/hash and frozen asset references remain explicitly null or pending. Installed version observations during a future run are evidence about that run, not a claim of full tested dependency pinning. Network dependency locking requires actual tested versions and verified distribution/model artifacts; inventing pins would make the claim less reliable.

Remaining integration work includes real acquisition/decode/OCR tests in an authorized environment, confirmation of RapidOCR model-selection introspection for the chosen release, model and recognition-dictionary artifact retention, tested dependency pins, audiovisual subtitle/crop review, and durable external video/listing/model storage. The safety fixtures cannot establish subtitle accuracy, download availability, end-to-end reproducibility, or complete runtime compatibility.

## Local fixture checks

Run only the dependency-free synthetic tests and shell syntax checks:

```sh
python3 -m unittest discover -s tests -p 'test_pipeline*.py' -v
bash -n tools/fetch_videos.sh tools/run_ocr.sh
```

The fixtures use temporary directories and mocked decoder/download/worker processes. They cover reorder-stable IDs, title-stable paths, failed FFmpeg without publication, malformed caches, video/model/config/tool/code changes, missing OCR, reviewed empty-source gates, raw-versus-correction separation and ordinary write rollback. They do not regenerate the repository's existing raw transcripts.
