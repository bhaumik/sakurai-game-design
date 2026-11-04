"""Build optional transcript projections, preserving existing episode IDs and paths.

Usage: python tools/build_transcripts.py LISTING OCR_DIR ROOT [--plan-only]
The inherited episodes/index.csv is authoritative. No catalogue or corrections are edited.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (DEFAULT_PROFILE, PipelineError, atomic_bytes, fingerprint, load_profile,
                             read_json, read_listing, sha256_file, validate_ocr, validate_segments)

CATEGORY_FIX = {"Planning & Design": "Planning & Game Design"}
PARA_GAP = 2.0
PARA_LINES = 4
SENTENCE_END = (".", "!", "?", "\u201d", '"', "…")
FIELDS = ["ep", "video_id", "title", "category", "duration_s", "words", "url", "transcript"]


def parse_title(raw):
    match = re.match(r"^(.*?)\s*\[([^\]]+)\]\s*$", raw)
    title, category = (match.group(1).strip(), match.group(2).strip()) if match else (raw.strip(), "Special")
    return title, CATEGORY_FIX.get(category, category)


def slugify(text, n=60):
    text = re.sub(r"[’']", "", text.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:n].rstrip("-") or "episode"


def mmss(time):
    seconds = int(time)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def paragraphs(lines):
    paras, current = [], []
    for line in lines:
        long_enough = len(current) >= PARA_LINES and current[-1]["text"].endswith(SENTENCE_END)
        if current and (line["start"] - current[-1]["end"] > PARA_GAP or long_enough):
            paras.append(current)
            current = []
        current.append(line)
    if current:
        paras.append(current)
    return paras


def contained_transcript(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".md" or path.parts[:2] != ("episodes", "transcripts"):
        raise PipelineError(f"unsafe authoritative transcript path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to((root / "episodes" / "transcripts").resolve()):
        raise PipelineError(f"escaping authoritative transcript path: {relative}")
    return root / path


def authoritative_index(root):
    path = root / "episodes" / "index.csv"
    if not path.exists():
        return {}, None
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise PipelineError(f"{path}: unsupported index header, expected {','.join(FIELDS)}")
        rows = list(reader)
    if not rows:
        raise PipelineError(f"{path}: empty authoritative index")
    result, episodes, paths = {}, set(), set()
    for row in rows:
        try:
            ep = int(row["ep"])
            if ep < 1 or ep in episodes or row["video_id"] in result or row["transcript"] in paths:
                raise ValueError("duplicate/nonpositive identity")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", row["video_id"]):
                raise ValueError("invalid video ID")
            if any(value is None for value in row.values()) or None in row:
                raise ValueError("malformed row")
            if int(row["words"]) < 0 or int(row["duration_s"]) < 0:
                raise ValueError("negative count")
            contained_transcript(root, row["transcript"])
        except (TypeError, ValueError) as exc:
            raise PipelineError(f"{path}: invalid authoritative index row: {exc}") from exc
        row["ep"] = ep
        result[row["video_id"]] = row
        episodes.add(ep)
        paths.add(row["transcript"])
    return result, sha256_file(path)


def empty_decisions(path):
    if path is None:
        return {}
    value = read_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("decisions"), list):
        raise PipelineError(f"{path}: expected versioned reviewed empty-source decisions")
    result = {}
    for decision in value["decisions"]:
        if (not isinstance(decision, dict) or decision.get("status") != "reviewed_empty_source"
                or not all(isinstance(decision.get(key), str) and decision[key].strip()
                           for key in ("video_id", "reviewed_by", "reason"))):
            raise PipelineError(f"{path}: each decision needs video_id, reviewed_by, reason and reviewed_empty_source status")
        if decision["video_id"] in result:
            raise PipelineError(f"{path}: duplicate empty-source decision")
        result[decision["video_id"]] = decision
    return result


def ocr_source(ocr, video_id, decisions, expected_profile=None):
    if ocr.exists():
        value = read_json(ocr)
        if isinstance(value, list):
            lines = validate_segments(value, ocr)
            metadata = {"status": "legacy_retained_ocr_original_provenance_unknown",
                        "review_status": "unreviewed_not_visually_verified", "fingerprint": None}
        else:
            value = validate_ocr(value, ocr)
            if Path(value["provenance"]["video"]["name"]).stem != video_id:
                raise PipelineError(f"{ocr}: OCR video identity mismatch")
            if expected_profile is not None and value["provenance"]["profile"] != expected_profile:
                raise PipelineError(f"{ocr}: OCR source profile mismatch; recompute or review the source revision")
            lines = value["segments"]
            metadata = {"status": "versioned_raw_ocr", "review_status": value["review_status"],
                        "fingerprint": value["fingerprint"]}
        metadata["raw_ocr_sha256"] = sha256_file(ocr)
    else:
        lines, metadata = [], {"status": "missing_ocr", "raw_ocr_sha256": None, "fingerprint": None}
    if not lines:
        decision = decisions.get(video_id)
        if not decision:
            raise PipelineError(f"{ocr}: {'empty' if ocr.exists() else 'missing'} OCR; explicit reviewed empty-source decision required")
        metadata.update({"status": "reviewed_empty_source", "empty_source_decision": decision,
                         "review_status": "empty_source_decision_only_not_visual_transcript_verification"})
    return lines, metadata


def render(row, lines, reviewed_empty=False):
    video_id = row["video_id"]
    body = []
    for paragraph in paragraphs(lines):
        time = paragraph[0]["start"]
        body.append(f"[{mmss(time)}](https://youtu.be/{video_id}?t={int(time)}) " + " ".join(line["text"] for line in paragraph))
    return "\n".join([
        f"# {int(row['ep']):03d} · {row['title']}", "", f"- **Category:** {row['category']}",
        f"- **Video:** {row['url']}", f"- **Length:** {mmss(row['duration_s'])}",
        "- **Source:** burned-in English subtitles read by OCR; retained raw recognition, not visually verified. Original legacy acquisition provenance is unknown.",
        "", "---", "", "\n\n".join(body) if body else "_Empty source explicitly reviewed; this is not proof of audiovisual verification._", ""]).encode()


def publish(outputs):
    """Prevalidated, atomic per-file writes with rollback for ordinary exceptions.

    This is not a cross-file filesystem transaction against power loss. Manifest is last.
    """
    previous = {path: path.read_bytes() if path.exists() else None for path in outputs}
    written = []
    try:
        for path, content in outputs.items():
            if previous[path] == content:
                continue
            atomic_bytes(path, content)
            written.append(path)
    except Exception:
        for path in reversed(written):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_bytes(path, previous[path])
        raise


def build(tsv, ocr_dir, root, profile_path=DEFAULT_PROFILE, decisions_path=None,
          initialize=False, replace_existing=False, plan_only=False):
    tsv, ocr_dir, root = Path(tsv), Path(ocr_dir), Path(root).resolve()
    profile = load_profile(profile_path)
    listing_hash = sha256_file(tsv)
    listed = read_listing(tsv, profile)
    known, old_index_hash = authoritative_index(root)
    if not known:
        if not initialize:
            raise PipelineError("authoritative episodes/index.csv missing; --initialize-index required for a genuinely new output tree")
        if any((root / "episodes" / "transcripts").glob("*.md")):
            raise PipelineError("cannot initialize IDs over pre-existing raw transcripts")
        ordered = listed[::-1] if profile["listing"].get("order") == "newest_first" else listed
        for episode, item in enumerate(ordered, 1):
            title, _ = parse_title(item["title"])
            known[item["video_id"]] = {"ep": episode, "transcript": f"episodes/transcripts/{episode:03d}-{slugify(title)}.md"}
    else:
        actual, expected = {item["video_id"] for item in listed}, set(known)
        if actual != expected:
            raise PipelineError(f"listing/index identity mismatch: unknown={sorted(actual - expected)}, missing={sorted(expected - actual)}; curator must extend/review authoritative index, never renumber from listing order")
    decisions = empty_decisions(decisions_path)
    if set(decisions) - set(known):
        raise PipelineError(f"empty-source decisions contain unknown videos: {sorted(set(decisions) - set(known))}")
    unknown_ocr = {path.stem for path in ocr_dir.glob("*.json")} - set(known)
    if unknown_ocr:
        raise PipelineError(f"{ocr_dir}: unknown OCR documents not in authoritative index: {sorted(unknown_ocr)}")
    outputs, index, records = {}, [], []
    for item in sorted(listed, key=lambda row: known[row["video_id"]]["ep"]):
        video_id, identity = item["video_id"], known[item["video_id"]]
        title, category = parse_title(item["title"])
        lines, source = ocr_source(ocr_dir / f"{video_id}.json", video_id, decisions, profile)
        row = {"ep": identity["ep"], "video_id": video_id, "title": title, "category": category,
               "duration_s": int(item["duration_s"]), "words": sum(len(line["text"].split()) for line in lines),
               "url": f"https://www.youtube.com/watch?v={video_id}", "transcript": identity["transcript"]}
        target = contained_transcript(root, row["transcript"])
        proposed = render(row, lines)
        previous_hash = sha256_file(target) if target.exists() else None
        if old_index_hash and not target.is_file():
            raise PipelineError(f"{target}: authoritative raw transcript missing; repair in a reviewed staging tree")
        status = "new_projection"
        if target.exists() and not replace_existing:
            content = target.read_bytes()
            row["words"] = int(identity["words"])
            status = "existing_raw_retained_not_regenerated"
        else:
            content = proposed
            if target.exists() and content != target.read_bytes():
                archive = root / "episodes" / "transcript-revisions" / video_id / f"{previous_hash}.md"
                if archive.exists() and archive.read_bytes() != target.read_bytes():
                    raise PipelineError(f"{archive}: existing revision archive does not match its hash")
                outputs[archive] = target.read_bytes()
                status = "explicit_replacement_previous_raw_archived"
            outputs[target] = content
        records.append({"document_id": f"youtube:{video_id}", "legacy_episode": row["ep"],
                        "transcript_path": row["transcript"], "transcript_sha256": fingerprint_bytes(content),
                        "proposed_projection_sha256": fingerprint_bytes(proposed), "previous_transcript_sha256": previous_hash,
                        "projection_status": status, "ocr_source": source})
        index.append(row)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(index)
    outputs[root / "episodes" / "index.csv"] = buffer.getvalue().encode()
    plan = {"schema_version": 1, "source_id": profile["source_id"], "listing_sha256": listing_hash,
            "authoritative_index_sha256": old_index_hash, "profile": profile,
            "builder_sha256": sha256_file(__file__), "documents": records,
            "corrections_applied": False, "original_inherited_provenance_reconstructed": False,
            "publication": "per_file_atomic_with_exception_rollback_manifest_last_not_power_loss_transaction"}
    if plan_only:
        return plan
    # Validate the complete input set before any publication. Corrections are never build inputs.
    if sha256_file(tsv) != listing_hash:
        raise PipelineError("listing changed during planning")
    for record in records:
        source = record["ocr_source"]
        raw_path = ocr_dir / f"{record['document_id'].split(':', 1)[1]}.json"
        if source.get("raw_ocr_sha256") is not None and sha256_file(raw_path) != source["raw_ocr_sha256"]:
            raise PipelineError(f"{raw_path}: OCR changed during planning")
        target = root / record["transcript_path"]
        if record["previous_transcript_sha256"] is not None and sha256_file(target) != record["previous_transcript_sha256"]:
            raise PipelineError(f"{target}: raw transcript changed during planning")
    if old_index_hash and sha256_file(root / "episodes" / "index.csv") != old_index_hash:
        raise PipelineError("authoritative index changed during planning")
    outputs[root / "episodes" / "transcript-generation.json"] = (json.dumps(plan, ensure_ascii=False,
                                                                 sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    publish(outputs)
    return plan


def fingerprint_bytes(content):
    import hashlib
    return hashlib.sha256(content).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("listing", type=Path)
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--empty-source-decisions", type=Path)
    parser.add_argument("--initialize-index", action="store_true")
    parser.add_argument("--replace-existing", action="store_true", help="Explicit reviewed replacement; archive previous raw bytes first")
    parser.add_argument("--plan-only", action="store_true", help="Read-only plan, no source or output writes")
    args = parser.parse_args(argv)
    try:
        plan = build(args.listing, args.ocr_dir, args.root, args.profile, args.empty_source_decisions,
                     args.initialize_index, args.replace_existing, args.plan_only)
        if args.plan_only:
            print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"{len(plan['documents'])} episodes; existing IDs/paths retained; no corrections applied")
        return 0
    except (PipelineError, OSError, csv.Error) as exc:
        print(f"Transcript build error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
