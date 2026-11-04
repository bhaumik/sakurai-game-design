"""Optional network acquisition. Importing this module performs no acquisition."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (DEFAULT_PROFILE, PipelineError, atomic_bytes, atomic_json,
                             load_profile, read_json, read_listing, sha256_file, tool_version)


def freeze_listing(work, profile, listing=None, refresh=False):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    target = work / "videos.tsv"
    if refresh:
        # A failed refresh must not replace the previous frozen listing.
        result = subprocess.run(["yt-dlp", "--flat-playlist", "--print",
                                 "%(id)s\t%(title)s\t%(duration)s", profile["channel_url"]],
                                capture_output=True, check=True)
        with tempfile.TemporaryDirectory(dir=work) as temporary:
            candidate = Path(temporary) / "videos.tsv"
            candidate.write_bytes(result.stdout)
            read_listing(candidate, profile)
            content = candidate.read_bytes()
        origin = "explicit_live_refresh"
    else:
        source = Path(listing) if listing else target
        if not source.is_file():
            raise PipelineError(f"{source}: frozen listing missing; supply --listing or explicitly opt in with --refresh")
        read_listing(source, profile)
        content = source.read_bytes()
        origin = "supplied_frozen_listing_original_acquisition_unknown"
    import hashlib
    digest = hashlib.sha256(content).hexdigest()
    snapshot = work / "listings" / f"{digest}.tsv"
    if snapshot.exists() and snapshot.read_bytes() != content:
        raise PipelineError(f"{snapshot}: frozen snapshot hash collision or corruption")
    atomic_bytes(snapshot, content)
    atomic_bytes(target, content)
    return target, {"sha256": digest, "snapshot": str(snapshot.relative_to(work)),
                    "origin": origin, "original_inherited_provenance_reconstructed": False}


def probe_asset(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
                            capture_output=True, text=True, check=True)
    try:
        width, height = map(int, result.stdout.strip().splitlines()[0].split(","))
        if width < 1 or height < 1:
            raise ValueError("zero dimensions")
    except (IndexError, ValueError) as exc:
        raise PipelineError(f"{path}: no valid video stream") from exc
    return {"width": width, "height": height}


def acquire_asset(work, row, profile, previous=None):
    video_id = row["video_id"]
    asset = work / "video" / f"{video_id}.mp4"
    existed = asset.exists()
    if existed:
        if not asset.stat().st_size:
            raise PipelineError(f"{asset}: empty asset; remove/reacquire after review")
        if previous and previous["sha256"] != sha256_file(asset):
            raise PipelineError(f"{asset}: acquired asset hash changed; review a new source revision in a new work directory")
    else:
        log = work / "logs" / f"download-{video_id}.log"
        with log.open("wb") as stream:
            subprocess.run(["yt-dlp", "--js-runtimes", "node", "--no-playlist", "--abort-on-error",
                            "--write-info-json", "--remux-video", "mp4", "-f", profile["download"]["format"],
                            "-o", str(work / "video" / f"{video_id}.%(ext)s"), "--sleep-requests", "1",
                            f"https://www.youtube.com/watch?v={video_id}"],
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
    if not asset.is_file() or not asset.stat().st_size:
        raise PipelineError(f"{video_id}: worker finished without expected nonempty asset {asset}")
    dimensions = probe_asset(asset)
    info_path = work / "video" / f"{video_id}.info.json"
    selected = None
    if info_path.exists():
        info = read_json(info_path)
        if not isinstance(info, dict) or info.get("id") != video_id:
            raise PipelineError(f"{info_path}: invalid/mismatched download metadata")
        selected = {key: info.get(key) for key in ("format_id", "format", "ext", "vcodec", "width", "height")}
    record = {"video_id": video_id, "path": str(asset.relative_to(work)),
              "size_bytes": asset.stat().st_size, "sha256": sha256_file(asset),
              "dimensions": dimensions, "selected_format": selected,
              "info_json_sha256": sha256_file(info_path) if info_path.exists() else None,
              "provenance_status": "observed_existing_asset_original_acquisition_unknown" if existed else "download_observed_this_run"}
    if previous:
        record["prior_provenance_status"] = previous.get("provenance_status", "unknown")
    return record


def acquire(work, profile, listing=None, refresh=False, jobs=3):
    work = Path(work).resolve()
    frozen, listing_record = freeze_listing(work, profile, listing, refresh)
    rows = read_listing(frozen, profile)
    for directory in ("video", "logs"):
        (work / directory).mkdir(exist_ok=True)
    manifest_path = work / "acquisition-manifest.json"
    previous = {}
    if manifest_path.exists():
        prior = read_json(manifest_path)
        if not isinstance(prior, dict) or prior.get("schema_version") != 1 or not isinstance(prior.get("assets"), list):
            raise PipelineError(f"{manifest_path}: malformed prior acquisition manifest")
        for record in prior["assets"]:
            if (not isinstance(record, dict) or not isinstance(record.get("video_id"), str)
                    or record["video_id"] in previous
                    or not isinstance(record.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])):
                raise PipelineError(f"{manifest_path}: malformed/duplicate prior asset record")
            previous[record["video_id"]] = record
    assets, failures = [], []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        tasks = {pool.submit(acquire_asset, work, row, profile, previous.get(row["video_id"])): row["video_id"] for row in rows}
        for future in as_completed(tasks):
            video_id = tasks[future]
            try:
                assets.append(future.result())
                print(f"{video_id}: validated acquired asset", flush=True)
            except Exception as exc:
                failures.append(f"{video_id}: {exc}")
    if failures:
        raise PipelineError("acquisition worker failures; no completion manifest published:\n" + "\n".join(failures))
    if sha256_file(frozen) != listing_record["sha256"]:
        raise PipelineError("frozen listing changed during acquisition; no completion manifest published")
    if {asset["video_id"] for asset in assets} != {row["video_id"] for row in rows}:
        raise PipelineError("acquisition result coverage does not match the frozen listing")
    for asset in assets:
        if sha256_file(work / asset["path"]) != asset["sha256"]:
            raise PipelineError(f"{asset['path']}: video asset changed before manifest publication")
    tools = {name: tool_version(command) for name, command in
             (("yt-dlp", ["yt-dlp", "--version"]), ("node", ["node", "--version"]),
              ("ffmpeg", ["ffmpeg", "-version"]), ("ffprobe", ["ffprobe", "-version"]))}
    atomic_json(manifest_path, {"schema_version": 1, "status": "all_expected_assets_validated",
                               "listing": listing_record, "profile": profile, "runtime_tools": tools,
                               "pipeline_sha256": sha256_file(__file__),
                               "assets": sorted(assets, key=lambda record: record["video_id"]),
                               "original_inherited_provenance_reconstructed": False})
    return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--listing", type=Path)
    group.add_argument("--refresh", action="store_true", help="Explicitly allow a new live listing request")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        path = acquire(args.work, load_profile(args.profile), args.listing, args.refresh, args.jobs)
        print(f"Complete: {path}")
        return 0
    except (PipelineError, OSError, subprocess.SubprocessError) as exc:
        print(f"Acquisition error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
