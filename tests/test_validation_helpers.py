"""Small synthetic source fixture, never a fabricated Isbister claim."""
import hashlib
import json
from pathlib import Path
from tools.contracts import AREA_PREFIX, DATA_PATH, INDEX_FIELDS, KINDS, csv_text
from tools.build_data import build_areas, build_data


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def edit_json(path, fn):
    value = json.loads(path.read_text())
    fn(value)
    write_json(path, value)


def edit_jsonl(path, fn):
    values = [json.loads(line) for line in path.read_text().splitlines() if line]
    fn(values)
    path.write_text("".join(json.dumps(row) + "\n" for row in values))


def fixture(root):
    root = Path(root)
    transcript = "# Synthetic fixture\n\n[00:03](https://youtu.be/ABCDEFGHIJK?t=3) Synthetic retained text.\n"
    for directory in ("episodes/transcripts", "episodes/notes", "work/batches", "work/parts", "study-guide", "knowledge"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "episodes/transcripts/001-fixture.md").write_text(transcript)
    (root / "episodes/notes/001-fixture.md").write_text("# Fixture notes\n")
    index = {"ep": "1", "video_id": "ABCDEFGHIJK", "title": "Fixture", "category": "Synthetic", "duration_s": "30", "words": "3", "url": "https://www.youtube.com/watch?v=ABCDEFGHIJK", "transcript": "episodes/transcripts/001-fixture.md"}
    (root / "episodes/index.csv").write_text(csv_text(INDEX_FIELDS, [index]))
    write_json(root / "work/batches/ranges.json", [[1, 1]])
    candidate = {"principle": "Fixture principle", "domain": "essence", "why": "Fixture reason", "how": "Fixture action", "anti_pattern": "", "example": "", "quote": "", "tags": []}
    batch = {"ep": 1, "summary": "Fixture summary", "takeaways": ["Fixture takeaway"], "games": [], "tags": ["synthetic"], "principles": [candidate]}
    (root / "work/batches/batch-01.jsonl").write_text(json.dumps(batch) + "\n")
    parts = {}
    for kind, fields in KINDS.items():
        row = {key: "" for key in fields}
        row.update({"area": "essence", "episodes": "1"} if "area" in fields else {})
        if kind == "principles":
            row.update(id="ESS-01", priority="HIGH", principle="Fixture principle", why="Reason", how_to_apply="Action", review_question="Question?")
        elif kind == "techniques":
            row.update(id="ESS-T01", technique="Technique", what="What", how="How")
        elif kind == "lenses":
            row.update(id="ESS-L01", lens="Question?", principles="ESS-01")
        elif kind == "glossary":
            row.update(term="Term", meaning="Meaning", episodes="1")
        else:
            row.update(quote="Synthetic retained text.", ep=1, title="Fixture", time="00:03", theme="synthetic")
        (root / "work/parts" / f"essence-{kind}.jsonl").write_text(json.dumps(row) + "\n")
        parts[kind] = row
    source = {"source_id": "fixture:video", "author": "Synthetic", "work": "Synthetic fixture", "kind": "video_series", "language": "en", "status": "available", "url": index["url"]}
    document = {"document_id": "youtube:ABCDEFGHIJK", "source_id": "fixture:video", "episode": 1, "video_id": "ABCDEFGHIJK", "title": "Fixture", "url": index["url"], "language": "en", "translation_layer": "synthetic", "review_status": "unreviewed_ocr", "notes_path": "episodes/notes/001-fixture.md", "transcript_path": index["transcript"], "transcript_sha256": hashlib.sha256(transcript.encode()).hexdigest(), "duration_seconds": 30}
    write_json(root / "knowledge/catalogue.json", {"schema_version": "1.0", "sources": [source], "documents": [document]})
    segment = {"segment_id": "youtube:ABCDEFGHIJK:t000003", "document_id": document["document_id"], "start_seconds": 3, "next_start_seconds": None, "transcript_path": index["transcript"], "line_start": 3, "text_sha256": hashlib.sha256(b"Synthetic retained text.").hexdigest(), "review_status": "unreviewed_ocr", "suspect": False}
    write_json(root / "knowledge/segments.json", {"schema_version": "1.0", "segments": [segment]})
    claim = {"claim_id": "FIX-01", "item_ids": ["ESS-01"], "field": "why", "text": "Synthetic statement", "claim_type": "source_statement", "review_status": "retained_text_checked", "evidence": [{"document_id": document["document_id"], "locator": {"kind": "timestamp", "start_seconds": 3, "segment_ids": [segment["segment_id"]]}}]}
    write_json(root / "knowledge/claims.json", {"schema_version": "1.0", "claims": [claim]})
    annotation = {"conditions": {"requires_any": [], "excludes_any": []}, "applicability_basis": "curator_inference", "evidence_claim_ids": ["FIX-01"], "related": []}
    write_json(root / "knowledge/annotations.json", {"schema_version": "1.0", "items": {"ESS-01": annotation}, "corrections": []})
    for name in ("02-game-essence", "03-balance-and-difficulty", "04-planning-and-structure", "05-game-feel", "06-animation", "07-visuals-and-effects", "08-audio", "09-ui-and-clarity", "10-directing-and-teams", "11-work-ethic-and-creativity", "12-marketing-and-updates", "13-tech-and-tools", "14-case-studies"):
        (root / "study-guide" / f"{name}.md").write_text("# Authored fixture\n")
    build_areas(root)
    build_data(root)
    return root
