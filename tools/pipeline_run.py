"""Checked orchestration of optional OCR workers; no dependency installation."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (DEFAULT_PROFILE, PipelineError, atomic_json, load_profile,
                             ocr_context, read_json, read_listing, sha256_file, validate_ocr)


def run_worker(work, row, python, profile_path, profile, rec_model, force=False):
    video_id = row["video_id"]
    video, output = work / "video" / f"{video_id}.mp4", work / "ocr" / f"{video_id}.json"
    command = [python, "-I", str(Path(__file__).with_name("ocr_subs.py")), str(video), str(output),
               "--profile", str(profile_path)]
    if rec_model:
        command += ["--rec-model", str(rec_model)]
    if force:
        command.append("--force")
    with (work / "logs" / f"ocr-{video_id}.log").open("wb") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    value = validate_ocr(read_json(output), output, ocr_context(video, profile, rec_model))
    return {"video_id": video_id, "path": str(output.relative_to(work)), "sha256": sha256_file(output),
            "fingerprint": value["fingerprint"], "review_status": value["review_status"],
            "segment_count": len(value["segments"])}


def run_all(work, python, profile_path=DEFAULT_PROFILE, listing=None, rec_model=None, jobs=3, force=False):
    work = Path(work).resolve()
    profile_path = Path(profile_path).resolve()
    profile = load_profile(profile_path)
    listing = Path(listing).resolve() if listing else work / "videos.tsv"
    if not listing.is_file():
        raise PipelineError(f"{listing}: frozen listing required to validate expected OCR results")
    listing_hash = sha256_file(listing)
    rows = read_listing(listing, profile)
    for row in rows:
        video = work / "video" / f"{row['video_id']}.mp4"
        if not video.is_file() or not video.stat().st_size:
            raise PipelineError(f"{video}: missing or empty expected video; no OCR workers started")
    for directory in ("ocr", "logs"):
        (work / directory).mkdir(exist_ok=True)
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        tasks = {pool.submit(run_worker, work, row, python, profile_path, profile, rec_model, force): row["video_id"] for row in rows}
        for future in as_completed(tasks):
            video_id = tasks[future]
            try:
                results.append(future.result())
                print(f"{video_id}: validated OCR output", flush=True)
            except Exception as exc:
                failures.append(f"{video_id}: {exc}")
    if failures:
        raise PipelineError("OCR worker failures; no completion manifest published:\n" + "\n".join(failures))
    if sha256_file(listing) != listing_hash or load_profile(profile_path) != profile:
        raise PipelineError("listing/profile changed during OCR; no completion manifest published")
    if {result["video_id"] for result in results} != {row["video_id"] for row in rows}:
        raise PipelineError("worker result coverage does not match the frozen listing")
    for result in results:
        output = work / result["path"]
        if sha256_file(output) != result["sha256"]:
            raise PipelineError(f"{output}: OCR result changed before manifest publication")
        video = work / "video" / f"{result['video_id']}.mp4"
        validate_ocr(read_json(output), output, ocr_context(video, profile, rec_model))
    atomic_json(work / "ocr-manifest.json", {"schema_version": 1, "status": "all_expected_results_validated",
                                            "listing_sha256": listing_hash, "profile": profile,
                                            "results": sorted(results, key=lambda record: record["video_id"]),
                                            "review_status": "unreviewed_ocr_not_visually_verified"})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--listing", type=Path)
    parser.add_argument("--rec-model", type=Path)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        run_all(args.work, args.python, args.profile, args.listing, args.rec_model, args.jobs, args.force)
        return 0
    except (PipelineError, OSError, subprocess.SubprocessError) as exc:
        print(f"OCR pipeline error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
