"""Dependency-free corpus contracts, projections, and safe generated-file publication."""
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AREA_PREFIX = {"essence": "ESS", "balance": "BAL", "planning": "PLAN", "feel": "FEEL",
               "animation": "ANIM", "visuals": "VIS", "audio": "AUD", "ui": "UI",
               "team": "TEAM", "craft": "CRAFT", "marketing": "MKT", "tech": "TECH", "case-study": "CASE"}
KINDS = {
    "principles": ["id", "area", "priority", "principle", "why", "how_to_apply", "anti_pattern", "example", "review_question", "episodes", "keywords"],
    "techniques": ["id", "area", "technique", "what", "how", "when", "pitfalls", "episodes", "keywords"],
    "lenses": ["id", "area", "lens", "look_for", "red_flags", "principles", "episodes", "keywords"],
    "glossary": ["term", "meaning", "episodes"],
    "quotes": ["quote", "ep", "title", "time", "theme"],
}
INDEX_FIELDS = ["ep", "video_id", "title", "category", "duration_s", "words", "url", "transcript"]
EPISODE_FIELDS = ["ep", "title", "category", "url", "summary", "takeaways", "games", "tags", "notes"]
BATCH_FIELDS = ["ep", "summary", "takeaways", "games", "tags", "principles"]
CANDIDATE_FIELDS = ["principle", "domain", "why", "how", "anti_pattern", "example", "quote", "tags"]
PRIORITY = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
DATA_PATH = Path("skills/sakurai-game-design/data")
OPTIONAL_BLANK = {"anti_pattern", "example", "quote", "pitfalls", "when", "look_for", "red_flags", "principles", "episodes", "keywords", "time", "theme", "games", "tags"}


class ContractError(ValueError):
    pass


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.counts = {}

    @property
    def ok(self):
        return not self.errors

    def error(self, location, message):
        self.errors.append({"location": str(location), "message": message})

    def require(self):
        if self.errors:
            raise ContractError("\n".join(f"{e['location']}: {e['message']}" for e in self.errors))

    def as_dict(self):
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "counts": self.counts}


def flat(value):
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    return " ".join(str(value if value is not None else "").split())


def tokens(value):
    return [x.strip() for x in str(value).replace(",", ";").split(";") if x.strip()]


def json_file(path, report):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as exc:
        report.error(path, str(exc))
        return None


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ContractError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def read_jsonl(path, report=None):
    own = report is None
    report = report or Report()
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.error(path, str(exc))
        lines = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(row, dict):
                raise ContractError("expected JSON object")
            out.append((row, f"{path}:{number}"))
        except ValueError as exc:
            report.error(f"{path}:{number}", str(exc))
    if own:
        report.require()
        return [row for row, _ in out]
    return out


def read_csv(path, fields, report):
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != fields:
                report.error(path, f"expected CSV headers {fields!r}, found {reader.fieldnames!r}")
                return []
            rows = []
            for number, row in enumerate(reader, 2):
                if None in row or None in row.values():
                    report.error(f"{path}:{number}", "CSV row has incorrect field count")
                else:
                    rows.append((row, f"{path}:{number}"))
            if not rows:
                report.error(path, "required dataset is empty")
            return rows
    except (OSError, csv.Error, UnicodeError) as exc:
        report.error(path, str(exc))
        return []


def shape(row, fields, loc, report, optional=()):
    if not isinstance(row, dict):
        report.error(loc, "expected object")
        return False
    missing = set(fields) - row.keys()
    extra = row.keys() - set(fields) - set(optional)
    if missing:
        report.error(loc, f"missing required fields: {sorted(missing)}")
    if extra:
        report.error(loc, f"unexpected fields: {sorted(extra)}; additive metadata belongs in knowledge sidecars")
    return not missing and not extra


def text(value, loc, report, blank=False):
    if not isinstance(value, str) or (not blank and not value.strip()):
        report.error(loc, "expected text" + ("" if blank else " that is not blank"))
        return False
    return True


def integer(value, loc, report, minimum=0, csv_value=False):
    valid = isinstance(value, int) and not isinstance(value, bool)
    if csv_value:
        valid = isinstance(value, str) and bool(re.fullmatch(r"[0-9]+", value))
    if not valid or int(value) < minimum:
        report.error(loc, f"expected integer >= {minimum}")
        return None
    return int(value)


def string_list(value, loc, report):
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        report.error(loc, "expected list of nonblank strings")
        return False
    return True


def contained_file(root, value, loc, report):
    if not isinstance(value, str) or not value.strip():
        report.error(loc, "expected nonblank relative file path")
        return None
    path = root / value
    if Path(value).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        report.error(loc, "path must remain within repository root (including symlinks)")
        return None
    if not path.is_file():
        report.error(loc, f"missing file {value!r}")
        return None
    return path


def references(value, valid, loc, report):
    if not isinstance(value, str):
        report.error(loc, "references must be semicolon-separated text")
        return
    for ref in tokens(value):
        if ref not in valid:
            report.error(loc, f"dangling reference {ref!r}")


def unique(rows, field, report):
    seen = set()
    for row, loc in rows:
        value = row.get(field)
        if not isinstance(value, (str, int)):
            continue
        if value in seen:
            report.error(loc, f"duplicate {field} {value!r}")
        seen.add(value)


def validate_entities(rows, kind, episodes, report, csv_mode=False, owner=None):
    for row, loc in rows:
        if not shape(row, KINDS[kind], loc, report):
            continue
        for field, value in row.items():
            if field == "ep":
                ep = integer(value, loc + ":ep", report, 1, csv_mode)
                if ep is not None and str(ep) not in episodes:
                    report.error(loc, f"unknown episode {ep}")
            else:
                text(value, loc + ":" + field, report, field in OPTIONAL_BLANK)
        if "area" in row:
            if not isinstance(row["area"], str) or row["area"] not in AREA_PREFIX:
                report.error(loc, f"unknown area {row['area']!r}")
            elif owner and row["area"] != owner:
                report.error(loc, f"part owned by {owner!r}, not {row['area']!r}")
        if "priority" in row and (not isinstance(row["priority"], str) or row["priority"] not in PRIORITY):
            report.error(loc, f"unknown priority {row['priority']!r}")
        if "episodes" in row:
            references(row["episodes"], episodes, loc + ":episodes", report)
        if kind == "quotes" and isinstance(row["time"], str) and row["time"]:
            if not re.fullmatch(r"\d+:[0-5]\d(?:\.[0-9]+)?", row["time"]):
                report.error(loc, "quote time must be MM:SS (optional fractional seconds)")
    if "id" in KINDS[kind]:
        unique(rows, "id", report)


def projected_data(parts):
    result = {}
    for kind, fields in KINDS.items():
        rows = [{k: flat(v) for k, v in r.items()} for r in parts[kind]]
        if kind == "principles":
            rows.sort(key=lambda r: (list(AREA_PREFIX).index(r["area"]), PRIORITY[r["priority"]], r["id"]))
        elif kind == "glossary":
            merged = {}
            for row in rows:
                key = row["term"].strip().lower()
                if key in merged:
                    merged[key]["episodes"] = ";".join(dict.fromkeys(tokens(merged[key]["episodes"]) + tokens(row["episodes"])))
                else:
                    merged[key] = row.copy()
            rows = sorted(merged.values(), key=lambda r: r["term"].lower())
        elif kind == "quotes":
            merged = {}
            for row in rows:
                # Text alone is not provenance: keep distinct episode/time citations.
                key = (row["quote"], row["ep"], row["time"])
                if key in merged:
                    merged[key]["theme"] = "; ".join(dict.fromkeys(tokens(merged[key]["theme"]) + tokens(row["theme"])))
                else:
                    merged[key] = row.copy()
            rows = sorted(merged.values(), key=lambda r: int(r["ep"]))
        result[kind] = rows
    return result


def projected_areas(index, batches):
    episodes, areas = [], defaultdict(list)
    for row in batches:
        meta = index[str(row["ep"])]
        episodes.append({"ep": str(row["ep"]), "title": meta["title"], "category": meta["category"], "url": meta["url"],
                         "summary": flat(row["summary"]), "takeaways": flat(row["takeaways"]), "games": flat(row["games"]),
                         "tags": " ".join(row["tags"]), "notes": meta["transcript"].replace("/transcripts/", "/notes/")})
        for candidate in row["principles"]:
            areas[candidate["domain"]].append({"ep": row["ep"], "title": meta["title"], "category": meta["category"], **candidate})
    return sorted(episodes, key=lambda r: int(r["ep"])), dict(areas)


def validate_legacy(root, report, check_outputs=True, compare_outputs=True):
    entries = read_csv(root / "episodes/index.csv", INDEX_FIELDS, report)
    unique(entries, "ep", report)
    unique(entries, "video_id", report)
    index = {}
    for row, loc in entries:
        ep = integer(row["ep"], loc + ":ep", report, 1, True)
        integer(row["duration_s"], loc + ":duration_s", report, 0, True)
        integer(row["words"], loc + ":words", report, 0, True)
        for field in ("video_id", "title", "category", "url"):
            text(row[field], loc + ":" + field, report)
        contained_file(root, row["transcript"], loc + ":transcript", report)
        contained_file(root, row["transcript"].replace("/transcripts/", "/notes/"), loc + ":notes", report)
        if ep is not None:
            index[str(ep)] = row
    ranges = json_file(root / "work/batches/ranges.json", report)
    assigned = set()
    batches = []
    if not isinstance(ranges, list) or not ranges:
        report.error("work/batches/ranges.json", "expected nonempty list of [start, end] ranges")
        ranges = []
    expected_batches = set()
    for number, pair in enumerate(ranges, 1):
        loc = f"work/batches/ranges.json:{number}"
        if not isinstance(pair, list) or len(pair) != 2:
            report.error(loc, "expected [start, end]")
            continue
        start = integer(pair[0], loc, report, 1)
        end = integer(pair[1], loc, report, 1)
        if start is None or end is None or start > end:
            report.error(loc, "invalid range")
            continue
        owned = set(str(x) for x in range(start, end + 1))
        if assigned & owned:
            report.error(loc, "overlapping batch ranges")
        assigned |= owned
        name = f"batch-{number:02d}.jsonl"
        expected_batches.add(name)
        records = read_jsonl(root / "work/batches" / name, report)
        found = set()
        for row, rowloc in records:
            if not shape(row, BATCH_FIELDS, rowloc, report):
                continue
            ep = integer(row["ep"], rowloc + ":ep", report, 1)
            if ep is not None:
                found.add(str(ep))
                if str(ep) not in owned:
                    report.error(rowloc, "episode outside owning batch range")
            text(row["summary"], rowloc + ":summary", report)
            for field in ("takeaways", "games", "tags"):
                string_list(row[field], rowloc + ":" + field, report)
            if not isinstance(row["principles"], list):
                report.error(rowloc, "principles must be a list")
                continue
            for n, candidate in enumerate(row["principles"], 1):
                cloc = f"{rowloc}:principles[{n}]"
                if not shape(candidate, CANDIDATE_FIELDS, cloc, report):
                    continue
                for key, value in candidate.items():
                    if key == "tags":
                        string_list(value, cloc + ":tags", report)
                    else:
                        text(value, cloc + ":" + key, report, key in OPTIONAL_BLANK)
                if not isinstance(candidate["domain"], str) or candidate["domain"] not in AREA_PREFIX:
                    report.error(cloc, f"unknown domain {candidate['domain']!r}")
            batches.append(row)
        unique(records, "ep", report)
        if found != owned:
            report.error(root / "work/batches" / name, f"batch coverage differs: missing {sorted(owned-found)}, extra {sorted(found-owned)}")
    if assigned != set(index):
        report.error("work/batches/ranges.json", "ranges must cover indexed episodes exactly")
    for path in (root / "work/batches").glob("*.jsonl"):
        if path.name not in expected_batches:
            report.error(path, "unexpected batch file with no assigned range")
    parts = {kind: [] for kind in KINDS}
    part_records = {kind: [] for kind in KINDS}
    for path in sorted((root / "work/parts").glob("*.jsonl")):
        match = next((kind for kind in KINDS if path.name.endswith(f"-{kind}.jsonl")), None)
        if not match:
            report.error(path, "unknown part kind")
            continue
        owner = path.name[:-len(f"-{match}.jsonl")]
        if owner not in AREA_PREFIX:
            report.error(path, "unknown part owner area")
        records = read_jsonl(path, report)
        validate_entities(records, match, set(index), report, owner=owner)
        part_records[match].extend(records)
        parts[match].extend(row for row, _ in records)
    for kind, records in part_records.items():
        if not records:
            report.error(root / "work/parts", f"missing nonempty {kind} input dataset")
        if "id" in KINDS[kind]:
            unique(records, "id", report)
    unique([record for kind in ("principles", "techniques", "lenses") for record in part_records[kind]], "id", report)
    principle_ids = {r.get("id") for r, _ in part_records["principles"] if isinstance(r.get("id"), str)}
    for row, loc in part_records["lenses"]:
        references(row.get("principles", ""), principle_ids, loc + ":principles", report)
    csvs = {}
    if check_outputs:
        for kind, fields in {"episodes": EPISODE_FIELDS, **KINDS}.items():
            records = read_csv(root / DATA_PATH / f"{kind}.csv", fields, report)
            csvs[kind] = [r for r, _ in records]
            if kind != "episodes":
                validate_entities(records, kind, set(index), report, csv_mode=True)
            else:
                unique(records, "ep", report)
                for row, loc in records:
                    references(row["ep"], set(index), loc + ":ep", report)
                    for field, value in row.items():
                        text(value, loc + ":" + field, report, field in OPTIONAL_BLANK)
                    contained_file(root, row["notes"], loc + ":notes", report)
        output_principles = {r.get("id") for r in csvs.get("principles", [])}
        for row in csvs.get("lenses", []):
            references(row.get("principles", ""), output_principles, "data/lenses.csv:principles", report)
    if report.ok and check_outputs and compare_outputs:
        projected_eps, areas = projected_areas(index, batches)
        if csvs["episodes"] != projected_eps:
            report.error(DATA_PATH / "episodes.csv", "generated episode projection differs from batch inputs; rebuild areas")
        expected = projected_data(parts)
        normalized_csvs = dict(csvs)
        normalized_csvs["quotes"] = projected_data({**parts, "quotes": csvs["quotes"]})["quotes"]
        for kind in KINDS:
            if Counter(json.dumps(r, sort_keys=True) for r in normalized_csvs[kind]) != Counter(json.dumps(r, sort_keys=True) for r in expected[kind]):
                report.error(DATA_PATH / f"{kind}.csv", "generated projection differs from part inputs; rebuild data")
        actual_names = {p.stem for p in (root / "work/areas").glob("*.jsonl")}
        if actual_names != set(areas):
            report.error("work/areas", "generated areas missing or stale; rebuild areas")
        for area, rows in areas.items():
            actual = read_jsonl(root / "work/areas" / f"{area}.jsonl", report)
            if [r for r, _ in actual] != rows:
                report.error(f"work/areas/{area}.jsonl", "area projection differs from batches; rebuild areas")
    report.counts.update(episodes=len(index), batches=len(ranges), **{kind: len(rows) for kind, rows in parts.items()})
    return {"index": index, "batches": batches, "parts": parts, "csvs": csvs}


def csv_text(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: flat(v) for k, v in row.items()})
    return buffer.getvalue()


def publish(root, outputs, stale=()):
    """Stage all bytes first; rollback ordinary replacement failures. Not crash-atomic."""
    root = Path(root).resolve()
    targets = {Path(key): value for key, value in outputs.items()}
    removals = {Path(key) for key in stale} - targets.keys()
    for relative in set(targets) | removals:
        if relative.is_absolute() or not (root / relative).resolve().is_relative_to(root):
            raise ContractError(f"unsafe generated target {relative}")
    old = {}
    with tempfile.TemporaryDirectory(prefix=".build-stage-", dir=root) as directory:
        stage = Path(directory)
        for n, (relative, content) in enumerate(targets.items()):
            (stage / str(n)).write_text(content, encoding="utf-8", newline="")
        for relative in set(targets) | removals:
            path = root / relative
            old[relative] = path.read_bytes() if path.exists() else None
        changed = []
        try:
            for n, relative in enumerate(targets):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / str(n), path)
                changed.append(relative)
            for relative in removals:
                (root / relative).unlink(missing_ok=True)
                changed.append(relative)
        except Exception:
            for relative in reversed(changed):
                path = root / relative
                if old[relative] is None:
                    path.unlink(missing_ok=True)
                else:
                    rollback = stage / "rollback"
                    rollback.write_bytes(old[relative])
                    os.replace(rollback, path)
            raise
