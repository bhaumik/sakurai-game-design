"""Structural sidecar checks. Passing is not audiovisual or bibliographic verification."""
import hashlib
import math
import re
from urllib.parse import parse_qs, urlparse

try:
    from .contracts import KINDS, contained_file, integer, json_file, shape, string_list, text, unique
except ImportError:
    from contracts import KINDS, contained_file, integer, json_file, shape, string_list, text, unique

REVIEW = {"unreviewed_ocr", "retained_text_checked", "audiovisual_verified", "source_verified", "curator_interpretation", "unreviewed", "pending", "reviewed", "unresolved"}
CLAIM_TYPES = {"source_example", "source_statement", "source_paraphrase", "source_quote", "curator_interpretation", "application_hypothesis", "paraphrase", "quote", "interpretation", "application", "direct_statement", "example"}
RELATIONS = {"supports", "qualified_by", "qualifies", "limits", "contrasts", "complements", "depends_on", "related", "applies_to", "duplicate_of", "supersedes"}


def enum(value, allowed, loc, report):
    if not isinstance(value, str) or value not in allowed:
        report.error(loc, f"unsupported value {value!r}; allowed {sorted(allowed)}")


def number(value, loc, report, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        report.error(loc, f"expected finite number >= {minimum}")
        return False
    return True


def namespace(value, loc, report):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*:[^\s:]+(?:[:][^\s:]+)*", value):
        report.error(loc, "expected nonblank namespaced ID")
        return False
    return True


def digest(value, loc, report):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        report.error(loc, "expected lowercase SHA-256")
        return False
    return True


def collection(root, name, key, report, optional=()):
    path = root / "knowledge" / f"{name}.json"
    obj = json_file(path, report)
    if not shape(obj, ["schema_version", key], path, report, optional):
        return None
    if obj["schema_version"] not in (1, "1.0") or isinstance(obj["schema_version"], bool):
        report.error(path, "supported schema_version is 1 or string 1.0")
    return obj


def records(value, loc, report):
    if not isinstance(value, list):
        report.error(loc, "expected list of records")
        return []
    result = []
    for n, row in enumerate(value, 1):
        rloc = f"{loc}[{n}]"
        if not isinstance(row, dict):
            report.error(rloc, "expected object")
        else:
            result.append((row, rloc))
    return result


def validate_knowledge(root, legacy, report, require=True):
    names = ("catalogue", "segments", "claims", "annotations")
    if not require and not all((root / "knowledge" / f"{name}.json").is_file() for name in names):
        report.warnings.append({"location": "knowledge", "message": "incomplete sidecars skipped during migration; release validation requires all four"})
        return
    catalogue = collection(root, "catalogue", "sources", report, ("documents",))
    segments_obj = collection(root, "segments", "segments", report, ("provenance",))
    claims_obj = collection(root, "claims", "claims", report, ("provenance",))
    annotations = collection(root, "annotations", "items", report, ("corrections", "concept_groups", "provenance"))
    if catalogue is None:
        return
    if "documents" not in catalogue:
        report.error("knowledge/catalogue.json", "missing required field documents")
    source_rows = records(catalogue["sources"], "knowledge/catalogue.json:sources", report)
    document_rows = records(catalogue.get("documents"), "knowledge/catalogue.json:documents", report)
    unique(source_rows, "source_id", report)
    unique(document_rows, "document_id", report)
    sources, docs, document_paths = {}, {}, {}
    for row, loc in source_rows:
        if not shape(row, ["source_id", "author", "work", "kind", "language", "status", "url"], loc, report, ("source_family", "rights", "provenance")):
            continue
        namespace(row["source_id"], loc + ":source_id", report)
        for key in ("author", "work", "language"):
            text(row[key], loc + ":" + key, report)
        text(row["url"], loc + ":url", report, blank=row["status"] == "pending")
        enum(row["kind"], {"video_series", "book", "article", "paper", "course", "video", "other"}, loc + ":kind", report)
        enum(row["status"], {"available", "pending"}, loc + ":status", report)
        if isinstance(row["source_id"], str):
            sources[row["source_id"]] = row
    seen_episodes = set()
    for row, loc in document_rows:
        required = ["document_id", "source_id", "title", "url", "language", "translation_layer", "review_status"]
        optional = ["episode", "video_id", "duration_seconds", "notes_path", "transcript_path", "transcript_sha256", "provenance", "kind", "page_count", "text_path", "text_sha256"]
        if not shape(row, required, loc, report, optional):
            continue
        if not namespace(row["document_id"], loc + ":document_id", report):
            continue
        if not isinstance(row["source_id"], str) or row["source_id"] not in sources:
            report.error(loc, "unknown source_id")
        elif sources[row["source_id"]]["status"] == "pending":
            report.error(loc, "pending sources must have zero documents and claims")
        for key in ("title", "url", "language", "translation_layer"):
            text(row[key], loc + ":" + key, report)
        enum(row["review_status"], REVIEW, loc + ":review_status", report)
        is_video = row["document_id"].startswith("youtube:")
        if is_video:
            shape(row, required + ["episode", "video_id", "notes_path", "transcript_path", "transcript_sha256"], loc, report, optional)
            ep = integer(row.get("episode"), loc + ":episode", report, 1)
            video_id = row["document_id"].split(":", 1)[1]
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or row.get("video_id") != video_id:
                report.error(loc, "document_id must equal youtube:<video_id> with an 11-character video ID")
            url = urlparse(row["url"] if isinstance(row["url"], str) else "")
            url_id = url.path.strip("/") if url.hostname in {"youtu.be", "www.youtu.be"} else parse_qs(url.query).get("v", [None])[0]
            if url_id != video_id or url.hostname not in {"youtu.be", "www.youtu.be", "youtube.com", "www.youtube.com"}:
                report.error(loc, "video URL identity disagrees with document_id")
            if ep is not None:
                if ep in seen_episodes:
                    report.error(loc, "duplicate legacy episode alias")
                seen_episodes.add(ep)
                legacy_row = legacy["index"].get(str(ep))
                if not legacy_row or legacy_row["video_id"] != video_id:
                    report.error(loc, "legacy episode/video identity disagrees with index")
                elif row.get("transcript_path") != legacy_row["transcript"] or row.get("notes_path") != legacy_row["transcript"].replace("/transcripts/", "/notes/"):
                    report.error(loc, "explicit video paths disagree with legacy episode paths")
        elif "episode" in row:
            report.error(loc, "episode alias is only permitted for video documents")
        for key in ("notes_path", "transcript_path", "text_path"):
            if key in row:
                path = contained_file(root, row[key], loc + ":" + key, report)
                if key == "transcript_path" and path:
                    document_paths[row["document_id"]] = path
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if row.get("transcript_sha256") != actual:
                        report.error(loc, "retained transcript SHA-256 mismatch")
        for key in ("transcript_sha256", "text_sha256"):
            if key in row:
                digest(row[key], loc + ":" + key, report)
        if "duration_seconds" in row:
            number(row["duration_seconds"], loc + ":duration_seconds", report)
        if "page_count" in row:
            integer(row["page_count"], loc + ":page_count", report, 1)
        if "text_path" in row and "text_sha256" in row:
            path = contained_file(root, row["text_path"], loc + ":text_path", report)
            if path and hashlib.sha256(path.read_bytes()).hexdigest() != row["text_sha256"]:
                report.error(loc, "retained document text SHA-256 mismatch")
        docs[row["document_id"]] = row
    if seen_episodes != {int(x) for x in legacy["index"]}:
        report.error("knowledge/catalogue.json", "video document aliases must cover legacy episodes exactly")
    segments = {}
    if segments_obj:
        segment_rows = records(segments_obj["segments"], "knowledge/segments.json:segments", report)
        unique(segment_rows, "segment_id", report)
        lines_cache = {key: path.read_text(encoding="utf-8").splitlines() for key, path in document_paths.items()}
        for row, loc in segment_rows:
            required = ["segment_id", "document_id", "start_seconds", "next_start_seconds", "transcript_path", "line_start", "text_sha256", "review_status", "suspect"]
            if not shape(row, required, loc, report):
                continue
            if not isinstance(row["document_id"], str) or row["document_id"] not in docs:
                report.error(loc, "unknown segment document_id")
                continue
            namespace(row["segment_id"], loc + ":segment_id", report)
            start_ok = number(row["start_seconds"], loc + ":start_seconds", report)
            if row["next_start_seconds"] is not None:
                end_ok = number(row["next_start_seconds"], loc + ":next_start_seconds", report)
                if start_ok and end_ok and row["next_start_seconds"] <= row["start_seconds"]:
                    report.error(loc, "next segment start must be after current start")
            line = integer(row["line_start"], loc + ":line_start", report, 1)
            if type(row["suspect"]) is not bool:
                report.error(loc, "suspect must be boolean")
            enum(row["review_status"], REVIEW, loc + ":review_status", report)
            digest(row["text_sha256"], loc + ":text_sha256", report)
            doc = docs[row["document_id"]]
            if row["transcript_path"] != doc.get("transcript_path"):
                report.error(loc, "segment path differs from its document")
            lines = lines_cache.get(row["document_id"], [])
            match = re.fullmatch(r"\[(\d+):([0-5]\d)\]\([^)]*\) (.*)", lines[line-1]) if line and line <= len(lines) else None
            if not match:
                report.error(loc, "line_start does not point to retained timestamp paragraph")
            else:
                seconds = int(match[1])*60 + int(match[2])
                if seconds != row["start_seconds"]:
                    report.error(loc, "segment timestamp disagrees with retained text")
                if row["segment_id"] != f"{row['document_id']}:t{seconds:06d}":
                    report.error(loc, "segment identity must be document_id:tNNNNNN")
                next_seconds = None
                for following in lines[line:]:
                    next_match = re.fullmatch(r"\[(\d+):([0-5]\d)\]\([^)]*\) (.*)", following)
                    if next_match:
                        next_seconds = int(next_match[1])*60 + int(next_match[2])
                        break
                boundary_ok = row["next_start_seconds"] == next_seconds
                if next_seconds is None and row["next_start_seconds"] == doc.get("duration_seconds"):
                    boundary_ok = True
                if not boundary_ok:
                    report.error(loc, "next_start_seconds differs from retained next paragraph start or final document duration")
                if hashlib.sha256(match[3].encode("utf-8")).hexdigest() != row["text_sha256"]:
                    report.error(loc, "retained segment text SHA-256 mismatch")
            if isinstance(row["segment_id"], str):
                segments[row["segment_id"]] = row
        suspect_count = sum(bool(row.get("suspect")) for row, _ in segment_rows)
        if suspect_count:
            report.warnings.append({"location": "knowledge/segments.json", "message": f"{suspect_count} suspect retained OCR segments; not structural failures or verified corrections"})
    item_ids = {row["id"] for kind in ("principles", "techniques", "lenses") for row in legacy["parts"][kind] if isinstance(row.get("id"), str)}
    claims = {}
    if claims_obj:
        claim_rows = records(claims_obj["claims"], "knowledge/claims.json:claims", report)
        unique(claim_rows, "claim_id", report)
        for row, loc in claim_rows:
            if not shape(row, ["claim_id", "item_ids", "field", "text", "claim_type", "evidence", "review_status"], loc, report, ("provenance", "qualifiers", "context", "limitations")):
                continue
            text(row["claim_id"], loc + ":claim_id", report)
            if string_list(row["item_ids"], loc + ":item_ids", report):
                for item in row["item_ids"]:
                    if item not in item_ids:
                        report.error(loc, f"unknown claim item_id {item!r}")
            if "context" in row and not isinstance(row["context"], dict):
                report.error(loc, "context must be an object")
            if "limitations" in row:
                text(row["limitations"], loc + ":limitations", report, blank=True)
            if isinstance(row["field"], str) and row["field"] not in {k for fields in KINDS.values() for k in fields}:
                report.error(loc, "claim field must name an existing entity field")
            for key in ("field", "text"):
                text(row[key], loc + ":" + key, report)
            enum(row["claim_type"], CLAIM_TYPES, loc + ":claim_type", report)
            enum(row["review_status"], REVIEW, loc + ":review_status", report)
            evidence_rows = records(row["evidence"], loc + ":evidence", report)
            if not evidence_rows:
                report.error(loc, "claims require at least one evidence locator")
            for evidence, eloc in evidence_rows:
                if not shape(evidence, ["document_id", "locator"], eloc, report, ("review_status", "segment_ids", "note", "support_type")):
                    continue
                document_id = evidence["document_id"]
                if not isinstance(document_id, str) or document_id not in docs:
                    report.error(eloc, "unknown evidence document_id")
                    continue
                locator = evidence["locator"]
                if not isinstance(locator, dict):
                    report.error(eloc, "locator must be typed object")
                    continue
                if locator.get("kind") == "timestamp":
                    if not document_id.startswith("youtube:"):
                        report.error(eloc, "timestamp locator requires video document")
                    shape(locator, ["kind", "start_seconds"], eloc + ":locator", report, ("end_seconds", "segment_ids", "precision", "note"))
                    start = locator.get("start_seconds")
                    start_ok = number(start, eloc + ":start_seconds", report)
                    end = locator.get("end_seconds")
                    if end is not None:
                        end_ok = number(end, eloc + ":end_seconds", report)
                        if start_ok and end_ok and end < start:
                            report.error(eloc, "timestamp end precedes start")
                    duration = docs[document_id].get("duration_seconds")
                    if start_ok and isinstance(duration, (int, float)) and start > duration:
                        report.error(eloc, "timestamp exceeds document duration")
                elif locator.get("kind") == "page":
                    if document_id.startswith("youtube:"):
                        report.error(eloc, "page locator cannot cite video document")
                    shape(locator, ["kind", "page"], eloc + ":locator", report, ("end_page", "edition", "note"))
                    page = integer(locator.get("page"), eloc + ":page", report, 1)
                    if "end_page" in locator:
                        end = integer(locator["end_page"], eloc + ":end_page", report, 1)
                        if page and end and end < page:
                            report.error(eloc, "page range reversed")
                    page_count = docs[document_id].get("page_count")
                    if page and type(page_count) is int and page > page_count:
                        report.error(eloc, "page exceeds document page_count")
                else:
                    report.error(eloc, "locator kind must be timestamp or page")
                for ids in (evidence.get("segment_ids", []), locator.get("segment_ids", [])):
                    if string_list(ids, eloc + ":segment_ids", report):
                        for segment_id in ids:
                            if segment_id not in segments or segments[segment_id]["document_id"] != document_id:
                                report.error(eloc, f"unknown or mismatched segment {segment_id!r}")
            if isinstance(row["claim_id"], str):
                claims[row["claim_id"]] = row
    if annotations:
        items = annotations["items"]
        if not isinstance(items, dict):
            report.error("knowledge/annotations.json:items", "expected item ID mapping")
            items = {}
        groups = annotations.get("concept_groups", {})
        if isinstance(groups, list):
            group_rows = records(groups, "knowledge/annotations.json:concept_groups", report)
            unique(group_rows, "group_id", report)
            groups = {g["group_id"]: g for g, _ in group_rows if isinstance(g.get("group_id"), str)}
        if not isinstance(groups, dict):
            report.error("knowledge/annotations.json:concept_groups", "expected mapping or group record list")
            groups = {}
        for item, row in items.items():
            loc = f"knowledge/annotations.json:items:{item}"
            if item not in item_ids:
                report.error(loc, "unknown annotated item ID")
            if not shape(row, ["conditions", "applicability_basis", "evidence_claim_ids", "related"], loc, report, ("concept_group", "review_status", "application_experiments", "note")):
                continue
            condition = row["conditions"]
            if shape(condition, ["requires_any", "excludes_any"], loc + ":conditions", report):
                for key, value in condition.items():
                    string_list(value, loc + ":conditions:" + key, report)
            enum(row["applicability_basis"], {"curator_inference", "curator_interpretation", "source_grounded", "source_statement", "application_hypothesis"}, loc + ":applicability_basis", report)
            if string_list(row["evidence_claim_ids"], loc + ":evidence_claim_ids", report):
                for claim in row["evidence_claim_ids"]:
                    if claim not in claims:
                        report.error(loc, f"unknown evidence claim {claim!r}")
                    elif isinstance(claims[claim].get("item_ids"), list) and item not in claims[claim]["item_ids"]:
                        report.error(loc, "annotation evidence claim does not reference annotated item")
            for related, rloc in records(row["related"], loc + ":related", report):
                if shape(related, ["item_id", "relation"], rloc, report, ("note", "claim_ids")):
                    if not isinstance(related["item_id"], str) or related["item_id"] not in item_ids:
                        report.error(rloc, "unknown related item_id")
                    enum(related["relation"], RELATIONS, rloc + ":relation", report)
                    if "claim_ids" in related and string_list(related["claim_ids"], rloc + ":claim_ids", report):
                        for claim_id in related["claim_ids"]:
                            if claim_id not in claims:
                                report.error(rloc, "unknown relation claim_id")
            if "concept_group" in row:
                group = row["concept_group"]
                if not isinstance(group, str) or not group.strip():
                    report.error(loc, "concept_group must be nonblank text")
                elif groups and group not in groups:
                    report.error(loc, "unknown concept group")
        for group_id, group in groups.items():
            if not isinstance(group, dict):
                report.error("knowledge/annotations.json:concept_groups", "group must be object")
                continue
            members = group.get("item_ids", group.get("members", []))
            if string_list(members, "knowledge/annotations.json:concept_groups", report):
                for member in members:
                    if member not in item_ids:
                        report.error("knowledge/annotations.json:concept_groups", f"unknown group member {member!r}")
        if "corrections" not in annotations:
            report.error("knowledge/annotations.json", "missing required field corrections")
        correction_rows = records(annotations.get("corrections", []), "knowledge/annotations.json:corrections", report)
        unique(correction_rows, "correction_id", report)
        for correction, loc in correction_rows:
            if not shape(correction, ["correction_id", "document_id", "review_status", "proposed_text"], loc, report, ("segment_id", "raw_text", "raw_source_text", "status", "reason", "locator", "provenance")):
                continue
            text(correction["correction_id"], loc + ":correction_id", report)
            if "status" in correction:
                enum(correction["status"], {"unresolved", "proposed", "approved", "rejected", "resolved"}, loc + ":status", report)
            if "reason" in correction:
                text(correction["reason"], loc + ":reason", report)
            if not isinstance(correction.get("document_id"), str) or correction.get("document_id") not in docs:
                report.error(loc, "unknown correction document_id")
            if "segment_id" in correction and (not isinstance(correction["segment_id"], str) or correction["segment_id"] not in segments):
                report.error(loc, "unknown correction segment_id")
            elif "segment_id" in correction and segments[correction["segment_id"]]["document_id"] != correction["document_id"]:
                report.error(loc, "correction segment belongs to another document")
            if "raw_text" in correction or "raw_source_text" in correction:
                raw = correction.get("raw_text", correction.get("raw_source_text"))
                text(raw, loc + ":raw_text", report)
            elif "segment_id" not in correction:
                report.error(loc, "correction must preserve a retained segment pointer or raw text")
            enum(correction.get("review_status"), REVIEW, loc + ":review_status", report)
            if correction.get("proposed_text") is not None:
                text(correction["proposed_text"], loc + ":proposed_text", report)
    report.counts.update(sources=len(sources), documents=len(docs), segments=len(segments), claims=len(claims))
