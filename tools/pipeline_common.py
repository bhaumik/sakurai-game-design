"""Dependency-free safety and provenance helpers for optional acquisition only."""
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "sakurai-english.json"
REVIEW_STATUS = "unreviewed_ocr_not_visually_verified"


class PipelineError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def read_json(path):
    def finite_number(text):
        number = float(text)
        if not math.isfinite(number):
            raise ValueError("non-finite JSON number")
        return number

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"),
                          parse_float=finite_number, object_pairs_hook=unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, ValueError) as exc:
        raise PipelineError(f"{path}: cannot read valid JSON: {exc}") from exc


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value):
    # Serialize completely before touching any target; never emit NaN or truncated JSON.
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2,
                                  sort_keys=True, allow_nan=False) + "\n").encode())


def tool_version(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
        return {"status": "observed", "command": command,
                "output": (result.stdout or result.stderr).strip()}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "unresolved", "command": command, "reason": str(exc)}


def runtime_metadata():
    packages = {}
    for name in ("rapidocr", "onnxruntime", "numpy"):
        try:
            packages[name] = {"status": "observed", "version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"status": "not_installed_or_unresolved", "version": None}
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(), "packages": packages,
            "ffmpeg": tool_version(["ffmpeg", "-version"]),
            "ffprobe": tool_version(["ffprobe", "-version"])}


def load_profile(path=DEFAULT_PROFILE):
    profile = read_json(path)
    try:
        cfg = profile["ocr"]
        if (type(profile["schema_version"]) is not int or profile["schema_version"] != 1
                or not all(isinstance(profile[key], str) and profile[key].strip()
                           for key in ("profile_id", "source_id", "language"))):
            raise ValueError("unsupported profile")
        if profile["listing"]["order"] not in ("newest_first", "oldest_first"):
            raise ValueError("unsupported listing order")
        for name in ("width", "height", "strip_y0", "strip_height", "text_threshold", "min_text_pixels"):
            if type(cfg[name]) is not int:
                raise ValueError(f"{name} must be an integer")
        if not (cfg["width"] > 0 and cfg["height"] > 0 and cfg["strip_y0"] >= 0
                and cfg["strip_height"] > 0
                and cfg["strip_y0"] + cfg["strip_height"] <= cfg["height"]):
            raise ValueError("invalid crop bounds")
        if not 0 <= cfg["text_threshold"] <= 255 or cfg["min_text_pixels"] < 1:
            raise ValueError("invalid text threshold")
        for name in ("sample_fps", "change_fraction", "bar_dark_percentile", "bar_dark_threshold"):
            if type(cfg[name]) not in (int, float) or not math.isfinite(cfg[name]):
                raise ValueError(f"invalid {name}")
        if cfg["sample_fps"] <= 0 or not 0 < cfg["change_fraction"] <= 1:
            raise ValueError("invalid sample rate or change fraction")
        if not 0 <= cfg["bar_dark_percentile"] <= 100 or not 0 <= cfg["bar_dark_threshold"] <= 255:
            raise ValueError("invalid subtitle-bar thresholds")
        if not isinstance(profile["listing"]["exclude_title_contains"], list):
            raise ValueError("invalid listing exclusions")
        if not all(isinstance(s, str) for s in profile["listing"]["exclude_title_contains"]):
            raise ValueError("invalid listing exclusions")
        if not isinstance(profile["download"]["format"], str) or not profile["channel_url"].startswith("https://"):
            raise ValueError("invalid source configuration")
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"{path}: invalid source profile: {exc}") from exc
    return profile


def read_listing(path, profile):
    rows, seen = [], set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise PipelineError(f"{path}:{number}: expected video ID, title, duration TSV columns")
        vid, title, duration = parts
        if not re.fullmatch(r"[A-Za-z0-9_-]+", vid) or not title.strip() or vid in seen:
            raise PipelineError(f"{path}:{number}: invalid or duplicate video ID/title")
        seen.add(vid)
        try:
            seconds = float(duration or 0)
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError("not finite/nonnegative")
        except ValueError as exc:
            raise PipelineError(f"{path}:{number}: invalid duration {duration!r}") from exc
        if any(word in title for word in profile["listing"]["exclude_title_contains"]):
            continue
        rows.append({"video_id": vid, "title": title, "duration_s": seconds})
    if not rows:
        raise PipelineError(f"{path}: no eligible videos")
    return rows


def validate_segments(lines, location="OCR"):
    if not isinstance(lines, list):
        raise PipelineError(f"{location}: segments must be a list")
    previous = -1
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            raise PipelineError(f"{location}: segment {index} must be an object")
        for key in ("start", "end"):
            value = line.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise PipelineError(f"{location}: segment {index}: invalid {key}")
        if line["end"] < line["start"] or line["start"] < previous:
            raise PipelineError(f"{location}: segment {index}: reversed or unsorted times")
        if not isinstance(line.get("text"), str) or not line["text"].strip():
            raise PipelineError(f"{location}: segment {index}: missing text")
        if "raw_text_lines" in line and (not isinstance(line["raw_text_lines"], list)
                                         or not all(isinstance(t, str) for t in line["raw_text_lines"])):
            raise PipelineError(f"{location}: segment {index}: invalid raw text lines")
        previous = line["start"]
    return lines


def validate_ocr(value, location="OCR", expected=None):
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value.get("schema_version") != 1):
        raise PipelineError(f"{location}: expected versioned OCR envelope, not legacy or truncated cache")
    context = value.get("provenance")
    if not isinstance(context, dict) or value.get("fingerprint") != fingerprint(context):
        raise PipelineError(f"{location}: invalid provenance fingerprint")
    if expected is not None and context != expected:
        raise PipelineError(f"{location}: stale video/model/configuration/runtime fingerprint")
    if value.get("review_status") != REVIEW_STATUS or value.get("raw_segment_preservation") != "retained_without_editorial_correction":
        raise PipelineError(f"{location}: raw preservation/review status missing or misleading")
    try:
        if context["schema_version"] != 1 or not re.fullmatch(r"[0-9a-f]{64}", context["video"]["sha256"]):
            raise ValueError("invalid source hash")
        if not isinstance(context["profile"], dict) or not isinstance(context["runtime"], dict):
            raise ValueError("invalid profile/runtime")
        model = context["model"]
        if model["status"] == "explicit_local_recognition_asset":
            if not re.fullmatch(r"[0-9a-f]{64}", model["sha256"]):
                raise ValueError("invalid model hash")
            verification = value["model_runtime_verification"]
            if (not isinstance(verification, dict)
                    or verification.get("status") != "observed_loaded_recognition_asset"
                    or verification.get("sha256") != model["sha256"]):
                raise ValueError("explicit model load has not been verified")
        elif model["status"] != "unresolved_default_model":
            raise ValueError("unknown model status")
        elif model.get("sha256") is not None:
            raise ValueError("unresolved default model must not claim an asset hash")
        if not isinstance(context["tool_sha256"], dict) or not context["tool_sha256"]:
            raise ValueError("missing tool hashes")
        if not all(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                   for digest in context["tool_sha256"].values()):
            raise ValueError("invalid tool hashes")
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"{location}: incomplete provenance: {exc}") from exc
    validate_segments(value.get("segments"), location)
    if value.get("segments_sha256") != fingerprint(value["segments"]):
        raise PipelineError(f"{location}: raw segment hash mismatch")
    return value


def cache_matches(path, context):
    try:
        value = validate_ocr(read_json(path), path, context)
        # Defaults can resolve to changing remote model assets. Do not pretend they are pinned.
        return (context["model"]["status"] == "explicit_local_recognition_asset"
                and all(context["runtime"][tool]["status"] == "observed" for tool in ("ffmpeg", "ffprobe"))
                and all(p["status"] == "observed" for p in context["runtime"]["packages"].values())
                and bool(value))
    except (PipelineError, KeyError, OSError):
        return False


def ocr_context(video, profile, rec_model=None):
    video = Path(video)
    if not video.is_file() or not video.stat().st_size:
        raise PipelineError(f"{video}: missing or empty video asset")
    model = {"status": "unresolved_default_model", "identity": "RapidOCR default recognition selection",
             "sha256": None, "reason": "No verified local recognition asset supplied; cache reuse disabled"}
    if rec_model:
        path = Path(rec_model).resolve()
        if not path.is_file() or not path.stat().st_size:
            raise PipelineError(f"{path}: missing or empty recognition model")
        model = {"status": "explicit_local_recognition_asset", "identity": path.name,
                 "path": str(path), "sha256": sha256_file(path),
                 "selection": "RapidOCR params Rec.model_path; detection and classification disabled"}
    tools = Path(__file__).resolve().parent
    return {"schema_version": 1, "video": {"name": video.name, "size_bytes": video.stat().st_size,
                                           "sha256": sha256_file(video)},
            "profile": profile, "model": model, "runtime": runtime_metadata(),
            "tool_sha256": {name: sha256_file(tools / name) for name in ("ocr_subs.py", "pipeline_common.py")}}
