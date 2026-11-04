"""Read-only joins for the versioned knowledge sidecars.

These checks protect retrieval from silently treating unavailable metadata as no matches.
Full corpus validation remains the responsibility of the offline validator.
"""
import json
import re
from pathlib import Path


class DataError(ValueError):
    """Required local corpus data is missing, corrupt, or inconsistent."""


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict) or not value.get("schema_version"):
        raise DataError(f"{path}: expected an object with schema_version")
    if isinstance(value["schema_version"], bool) or value["schema_version"] not in ("1.0", 1):
        raise DataError(f"{path}: unsupported schema_version {value['schema_version']!r}")
    return value


def records(value, key, path):
    rows = value.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DataError(f"{path}: {key} must be an array of objects")
    return rows


def unique(rows, key, label):
    result = {}
    for row in rows:
        identifier = row.get(key)
        if not isinstance(identifier, str) or not identifier or identifier in result:
            raise DataError(f"{label}: missing or duplicate {key}: {identifier!r}")
        result[identifier] = row
    return result


def episode_numbers(row):
    value = row.get("episodes", row.get("ep", ""))
    return [int(part) for part in re.findall(r"\d+", str(value))]


class EvidenceStore:
    def __init__(self, knowledge_dir, root):
        self.root = Path(root)
        catalogue = read_json(Path(knowledge_dir) / "catalogue.json")
        self.sources = unique(records(catalogue, "sources", "catalogue"), "source_id", "sources")
        self.documents = unique(records(catalogue, "documents", "catalogue"), "document_id", "documents")
        self.by_episode = {}
        for source in self.sources.values():
            for field in ("author", "work", "kind", "language", "status", "url"):
                if not isinstance(source.get(field), str) or not source[field]:
                    raise DataError(f"source {source['source_id']}: missing {field}")
        for document in self.documents.values():
            if not isinstance(document.get("source_id"), str) or document["source_id"] not in self.sources:
                raise DataError(f"document {document['document_id']}: unknown source")
            for field in ("title", "url", "language", "translation_layer", "review_status"):
                if not isinstance(document.get(field), str) or not document[field]:
                    raise DataError(f"document {document['document_id']}: missing {field}")
            for field in ("notes_path", "transcript_path"):
                if document.get(field) is not None and not isinstance(document[field], str):
                    raise DataError(f"document {document['document_id']}: invalid {field}")
            if document.get("episode") is not None:
                ep = document["episode"]
                if not isinstance(ep, int) or isinstance(ep, bool) or ep <= 0:
                    raise DataError(f"document {document['document_id']}: invalid episode")
                self.by_episode.setdefault(ep, []).append(document)
        claims = read_json(Path(knowledge_dir) / "claims.json")
        self.claims = unique(records(claims, "claims", "claims"), "claim_id", "claims")
        self.by_item = {}
        for claim in self.claims.values():
            if not isinstance(claim.get("item_ids"), list) or not claim["item_ids"] or any(not isinstance(x, str) for x in claim["item_ids"]):
                raise DataError(f"claim {claim['claim_id']}: invalid item_ids")
            for field in ("field", "text", "claim_type", "review_status"):
                if not isinstance(claim.get(field), str) or not claim[field]:
                    raise DataError(f"claim {claim['claim_id']}: missing {field}")
            if not isinstance(claim.get("evidence"), list):
                raise DataError(f"claim {claim['claim_id']}: evidence must be an array")
            for evidence in claim["evidence"]:
                if not isinstance(evidence, dict) or not isinstance(evidence.get("document_id"), str) or evidence["document_id"] not in self.documents:
                    raise DataError(f"claim {claim['claim_id']}: unknown evidence document")
                locator = evidence.get("locator")
                if not isinstance(locator, dict) or not isinstance(locator.get("kind"), str):
                    raise DataError(f"claim {claim['claim_id']}: invalid locator")
                for key in ("start_seconds", "end_seconds", "timestamp_seconds"):
                    if key in locator and (not isinstance(locator[key], (int, float)) or isinstance(locator[key], bool) or locator[key] < 0):
                        raise DataError(f"claim {claim['claim_id']}: invalid {key}")
            for item_id in claim["item_ids"]:
                self.by_item.setdefault(item_id, []).append(claim)
        annotations = read_json(Path(knowledge_dir) / "annotations.json")
        self.annotations = annotations.get("items")
        if not isinstance(self.annotations, dict) or not isinstance(annotations.get("corrections"), list):
            raise DataError("annotations: expected items object and corrections array")
        for item_id, annotation in self.annotations.items():
            if not isinstance(annotation, dict):
                raise DataError(f"annotation {item_id}: expected object")
            conditions = annotation.get("conditions", {})
            if not isinstance(conditions, dict):
                raise DataError(f"annotation {item_id}: invalid conditions")
            for field in ("requires_any", "excludes_any"):
                if not isinstance(conditions.get(field, []), list) or any(not isinstance(x, str) for x in conditions.get(field, [])):
                    raise DataError(f"annotation {item_id}: {field} must be an array of strings")
            related = annotation.get("related", [])
            if not isinstance(related, list) or any(not isinstance(x, dict) or not isinstance(x.get("item_id"), str) or not isinstance(x.get("relation"), str) for x in related):
                raise DataError(f"annotation {item_id}: invalid related items")
            if not isinstance(annotation.get("evidence_claim_ids", []), list) or any(not isinstance(x, str) for x in annotation.get("evidence_claim_ids", [])):
                raise DataError(f"annotation {item_id}: invalid evidence_claim_ids")
            if annotation.get("concept_group") is not None and not isinstance(annotation["concept_group"], str):
                raise DataError(f"annotation {item_id}: invalid concept_group")
            for claim_id in annotation.get("evidence_claim_ids", []):
                if claim_id not in self.claims:
                    raise DataError(f"annotation {item_id}: unknown claim {claim_id}")
        segments = read_json(Path(knowledge_dir) / "segments.json")
        segment_rows = records(segments, "segments", "segments")
        self.segments = unique(segment_rows, "segment_id", "segments")
        for segment in self.segments.values():
            if not isinstance(segment.get("document_id"), str) or segment["document_id"] not in self.documents:
                raise DataError(f"segment {segment['segment_id']}: unknown document")
        for claim in self.claims.values():
            for evidence in claim["evidence"]:
                ids = evidence["locator"].get("segment_ids", [])
                if not isinstance(ids, list) or any(not isinstance(x, str) or x not in self.segments for x in ids):
                    raise DataError(f"claim {claim['claim_id']}: unknown segment")

    def source_for_query(self, selector):
        aliases = {"sakurai": "sakurai:creating-games", "masahiro sakurai": "sakurai:creating-games"}
        candidate = aliases.get(selector.lower(), selector)
        if candidate in self.sources:
            return candidate
        matches = [key for key, source in self.sources.items() if selector.lower() in (source["author"].lower(), source["work"].lower())]
        return matches[0] if len(matches) == 1 else None

    def resolve_document(self, document, timestamp=None):
        source = self.sources[document["source_id"]]
        result = dict(document)
        result["author"] = source["author"]
        result["work"] = source["work"]
        result["source_url"] = source["url"]
        for field in ("notes_path", "transcript_path"):
            relative = document.get(field)
            result[field.replace("_path", "_available")] = bool(relative and (self.root / relative).is_file())
        if timestamp:
            parts = str(timestamp).split(":")
            try:
                seconds = sum(int(part) * 60 ** index for index, part in enumerate(reversed(parts)))
            except ValueError as exc:
                raise DataError(f"invalid quote timestamp {timestamp!r}") from exc
            result["timestamp"] = timestamp
            result["time_url"] = document["url"] + ("&" if "?" in document["url"] else "?") + f"t={seconds}s"
        return result

    def joins(self, row, item_id, source_id):
        documents = []
        for episode in episode_numbers(row):
            matches = [d for d in self.by_episode.get(episode, []) if d["source_id"] == source_id]
            if not matches:
                raise DataError(f"{item_id}: episode {episode} has no catalogue document for {source_id}")
            documents.extend(matches)
        claims = list(self.by_item.get(item_id, []))
        for claim_id in self.annotations.get(item_id, {}).get("evidence_claim_ids", []):
            if self.claims[claim_id] not in claims:
                claims.append(self.claims[claim_id])
        resolved_claims = []
        for claim in claims:
            relevant = [e for e in claim["evidence"] if self.documents[e["document_id"]]["source_id"] == source_id]
            if not relevant:
                continue
            resolved = dict(claim)
            resolved["evidence"] = []
            for evidence in relevant:
                document = self.documents[evidence["document_id"]]
                documents.append(document)
                locator = evidence["locator"]
                seconds = locator.get("start_seconds", locator.get("timestamp_seconds"))
                resolved["evidence"].append({**evidence, "document": self.resolve_document(document, str(int(seconds)) if seconds is not None else None), "segments": [self.segments[key] for key in locator.get("segment_ids", [])]})
            resolved_claims.append(resolved)
        unique_documents = {d["document_id"]: d for d in documents}
        if episode_numbers(row) and not unique_documents:
            raise DataError(f"{item_id}: episode references have no catalogue document for {source_id}")
        return ([self.resolve_document(d, row.get("time")) for d in unique_documents.values()], resolved_claims)
