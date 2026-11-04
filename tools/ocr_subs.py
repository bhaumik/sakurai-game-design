"""Optional OCR of a profile-defined subtitle strip.

Usage: python -I tools/ocr_subs.py VIDEO OUTPUT [--profile PATH] [--rec-model PATH]
No OCR dependencies are imported for --check-cache or module import.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

# Isolated Python (-I) does not place this directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (DEFAULT_PROFILE, PipelineError, REVIEW_STATUS, atomic_bytes, atomic_json,
                             cache_matches, fingerprint, load_profile, ocr_context, sha256_file,
                             validate_ocr)


def probe_size(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(path)], text=True)
    try:
        w, h = map(int, out.strip().splitlines()[0].split(","))
        if min(w, h) < 1:
            raise ValueError("empty dimensions")
        return w, h
    except (ValueError, IndexError) as exc:
        raise PipelineError(f"{path}: invalid FFprobe dimensions") from exc


def decoded_strips(path, cfg):
    """Yield full raw frames and require successful FFmpeg completion.

    Stderr goes to a temporary file to avoid deadlocking the stdout pipe.
    A generator closed early terminates the child, rather than leaking it.
    """
    probe_size(path)
    w, height = cfg["width"], cfg["strip_height"]
    vf = (f"scale={w}:{cfg['height']},crop={w}:{height}:0:{cfg['strip_y0']},"
          f"fps={cfg['sample_fps']},format=gray")
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vf", vf,
             "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=errors)
        count, partial, finished = 0, False, False
        try:
            size = w * height
            while True:
                buf = proc.stdout.read(size)
                if not buf:
                    break
                if len(buf) != size:
                    partial = True
                    break
                yield count / cfg["sample_fps"], buf
                count += 1
            proc.stdout.close()
            returncode = proc.wait()
            finished = True
            errors.seek(0)
            diagnostic = errors.read().decode("utf-8", errors="replace")[-4000:]
            if returncode:
                raise PipelineError(f"{path}: FFmpeg failed ({returncode}): {diagnostic.strip()}")
            if partial or count == 0:
                raise PipelineError(f"{path}: FFmpeg emitted {'an incomplete frame' if partial else 'no frames'}")
        finally:
            if not finished:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                proc.stdout.close()


def strips(path, cfg):
    frames = decoded_strips(path, cfg)
    try:
        for t, buf in frames:
            import numpy as np
            yield t, np.frombuffer(buf, np.uint8).reshape(cfg["strip_height"], cfg["width"])
    finally:
        frames.close()


def segments(path, cfg):
    import numpy as np
    segs, cur = [], None
    frames = strips(path, cfg)
    try:
        for t, gray in frames:
            mask = gray > cfg["text_threshold"]
            if (np.percentile(gray, cfg["bar_dark_percentile"]) >= cfg["bar_dark_threshold"]
                    or int(mask.sum()) < cfg["min_text_pixels"]):
                if cur:
                    segs.append(cur)
                    cur = None
                continue
            if cur is not None:
                union = np.logical_or(mask, cur["mask"]).sum()
                diff = np.logical_xor(mask, cur["mask"]).sum() / max(union, 1)
                if diff < cfg["change_fraction"]:
                    cur["end"] = t
                    cur["frames"].append(gray)
                    continue
                segs.append(cur)
            cur = {"start": t, "end": t, "mask": mask, "frames": [gray]}
    finally:
        frames.close()
    if cur:
        segs.append(cur)
    return segs


def line_crops(gray, cfg):
    import numpy as np
    mask = gray > cfg["text_threshold"]
    rows = mask.sum(axis=1) > 2
    bands, start = [], None
    for y, on in enumerate(list(rows) + [False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start >= 8:
                bands.append((start, y))
            start = None
    crops = []
    for y0, y1 in bands:
        cols = np.where(mask[y0:y1].any(axis=0))[0]
        x0, x1 = max(cols[0] - 12, 0), min(cols[-1] + 12, cfg["width"])
        y0, y1 = max(y0 - 8, 0), min(y1 + 8, cfg["strip_height"])
        crop = 255 - gray[y0:y1, x0:x1]
        crops.append(np.ascontiguousarray(np.stack([crop] * 3, axis=-1)))
    return crops


def verify_loaded_recognition_model(engine, rec_model):
    """Fail closed when an installed RapidOCR release cannot expose the loaded asset.

    Inspect only recognizer descendants, not detection/classification or config declarations.
    An accepted Rec.model_path parameter alone is not proof that it was honored.
    """
    expected_hash = sha256_file(rec_model)
    roots = [getattr(engine, name, None) for name in ("text_rec", "text_recognizer", "recognizer")]
    pending, seen = [(root, 0) for root in roots if root is not None], set()
    while pending:
        node, depth = pending.pop()
        if id(node) in seen or depth > 5:
            continue
        seen.add(id(node))
        if type(node).__module__.startswith("onnxruntime"):
            loaded = getattr(node, "_model_path", None)
            if isinstance(loaded, (str, Path)) and Path(loaded).is_file():
                actual_hash = sha256_file(loaded)
                if actual_hash != expected_hash:
                    raise PipelineError("RapidOCR loaded a different recognition model; no pinned output published")
                return {"status": "observed_loaded_recognition_asset", "sha256": actual_hash,
                        "observed_loaded_path": str(Path(loaded).resolve()),
                        "method": "recognizer ONNX Runtime session _model_path observation"}
        for name in ("session", "infer_session", "ort_session", "engine", "net"):
            child = getattr(node, name, None)
            if child is not None and not isinstance(child, (str, bytes, int, float, bool)):
                pending.append((child, depth + 1))
    raise PipelineError("Cannot verify installed RapidOCR's loaded recognition asset; explicit model provenance unresolved, no output published")


def recognize(video, cfg, rec_model=None):
    # Finish decoding successfully before loading a recognizer or publishing anything.
    sampled = segments(video, cfg)
    from rapidocr import RapidOCR
    engine = RapidOCR(params={"Rec.model_path": str(Path(rec_model).resolve())}) if rec_model else RapidOCR()
    verification = (verify_loaded_recognition_model(engine, rec_model) if rec_model else
                    {"status": "unresolved_default_model", "sha256": None})
    lines = []
    for segment in sampled:
        if len(segment["frames"]) < 2:
            continue
        gray = segment["frames"][len(segment["frames"]) // 2]
        raw_parts = []
        for crop in line_crops(gray, cfg):
            result = engine(crop, use_det=False, use_cls=False, use_rec=True)
            raw_parts.extend(result.txts or [])
        text = " ".join(t.strip() for t in raw_parts if t.strip()).strip()
        if text:
            # Retain individual recognized segments and engine strings, not corrected or merged copies.
            lines.append({"start": round(segment["start"], 2),
                          "end": round(segment["end"] + 1 / cfg["sample_fps"], 2),
                          "text": text, "raw_text_lines": raw_parts})
    return lines, verification


def process(video, output, profile, rec_model=None, check_only=False, force=False):
    context = ocr_context(video, profile, rec_model)
    if check_only:
        return cache_matches(output, context)
    if not force and cache_matches(output, context):
        print(f"{video}: validated cache")
        return True
    lines, verification = recognize(video, profile["ocr"], rec_model)
    if context != ocr_context(video, profile, rec_model):
        raise PipelineError(f"{video}: source/model/runtime changed during OCR; no output published")
    value = {"schema_version": 1, "fingerprint": fingerprint(context), "provenance": context,
             "model_runtime_verification": verification,
             "review_status": REVIEW_STATUS,
             "raw_segment_preservation": "retained_without_editorial_correction",
             "segments": lines, "segments_sha256": fingerprint(lines)}
    validate_ocr(value, output, context)
    output = Path(output)
    serialized = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                             allow_nan=False) + "\n").encode()
    if output.exists() and output.read_bytes() != serialized:
        previous = output.read_bytes()
        archive = output.parent / "raw-revisions" / output.stem / f"{sha256_file(output)}.json"
        if archive.exists() and archive.read_bytes() != previous:
            raise PipelineError(f"{archive}: prior raw OCR archive integrity mismatch")
        atomic_bytes(archive, previous)
    atomic_json(output, value)
    print(f"{video}: {len(lines)} raw OCR segments; not visually verified")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--rec-model", type=Path, help="Explicit local recognition ONNX asset; no model pin is inferred")
    parser.add_argument("--check-cache", action="store_true", help="No OCR; exit 0 only for a validated reusable cache")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        valid = process(args.video, args.output, load_profile(args.profile), args.rec_model,
                        args.check_cache, args.force)
        return 0 if valid else 1
    except (PipelineError, OSError, subprocess.SubprocessError, ImportError) as exc:
        print(f"OCR error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
