"""Synthetic pipeline fixtures only. Never download, decode a real video, or import OCR libraries."""
import builtins
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import pipeline_common as common
import pipeline_acquire as acquisition
import pipeline_run as runner
import ocr_subs as ocr
import build_transcripts as transcripts


def runtime():
    return {"python": "synthetic", "implementation": "fixture", "platform": "fixture",
            "packages": {name: {"status": "observed", "version": "fixture"}
                         for name in ("rapidocr", "onnxruntime", "numpy")},
            "ffmpeg": {"status": "observed", "output": "fixture ffmpeg"},
            "ffprobe": {"status": "observed", "output": "fixture ffprobe"}}


def envelope(context, lines=None):
    lines = [{"start": 1.0, "end": 2.0, "text": "Synthetic raw typo.",
              "raw_text_lines": [" Synthetic raw typo. "]}] if lines is None else lines
    return {"schema_version": 1, "provenance": context, "fingerprint": common.fingerprint(context),
            "model_runtime_verification": {"status": "observed_loaded_recognition_asset",
                                           "sha256": context["model"]["sha256"]},
            "review_status": common.REVIEW_STATUS,
            "raw_segment_preservation": "retained_without_editorial_correction",
            "segments": lines, "segments_sha256": common.fingerprint(lines)}


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.video = self.directory / "fixture.mp4"
        self.video.write_bytes(b"not a real video")
        self.model = self.directory / "fixture.onnx"
        self.model.write_bytes(b"not a real model")
        self.output = self.directory / "fixture.json"
        self.profile = common.load_profile()
        self.metadata = patch.object(common, "runtime_metadata", side_effect=runtime)
        self.metadata.start()
        self.addCleanup(self.metadata.stop)
        self.context = common.ocr_context(self.video, self.profile, self.model)
        common.atomic_json(self.output, envelope(self.context))

    def test_valid_cache(self):
        self.assertTrue(common.cache_matches(self.output, self.context))

    def test_malformed_cache(self):
        self.output.write_text('{"segments":')
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_non_json_constant_cache(self):
        self.output.write_text('[NaN]')
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_overflow_json_number_cache(self):
        self.output.write_text('{"value": 1e999}')
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_duplicate_json_keys_cache(self):
        self.output.write_text('{"schema_version": 1, "schema_version": 2}')
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_malformed_model_verification_not_reusable(self):
        value = common.read_json(self.output)
        value["model_runtime_verification"] = 12
        common.atomic_json(self.output, value)
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_legacy_list_is_not_cache(self):
        common.atomic_json(self.output, [{"start": 0, "end": 1, "text": "legacy"}])
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_video_hash_changes_invalidate(self):
        self.video.write_bytes(b"different video bytes")
        self.assertFalse(common.cache_matches(self.output, common.ocr_context(self.video, self.profile, self.model)))

    def test_model_hash_changes_invalidate(self):
        self.model.write_bytes(b"different model bytes")
        self.assertFalse(common.cache_matches(self.output, common.ocr_context(self.video, self.profile, self.model)))

    def test_configuration_changes_invalidate(self):
        profile = copy.deepcopy(self.profile)
        profile["ocr"]["sample_fps"] = 2
        self.assertFalse(common.cache_matches(self.output, common.ocr_context(self.video, profile, self.model)))

    def test_tool_version_changes_invalidate(self):
        context = copy.deepcopy(self.context)
        context["runtime"]["ffmpeg"]["output"] = "new version"
        self.assertFalse(common.cache_matches(self.output, context))

    def test_code_changes_invalidate(self):
        context = copy.deepcopy(self.context)
        context["tool_sha256"]["ocr_subs.py"] = "changed"
        self.assertFalse(common.cache_matches(self.output, context))

    def test_segment_tampering_invalidates(self):
        value = common.read_json(self.output)
        value["segments"][0]["text"] = "changed without updating integrity hash"
        common.atomic_json(self.output, value)
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_fingerprint_tampering_invalidates(self):
        value = common.read_json(self.output)
        value["fingerprint"] = "incorrect"
        common.atomic_json(self.output, value)
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_unknown_model_honest_and_not_reusable(self):
        context = common.ocr_context(self.video, self.profile)
        self.assertIsNone(context["model"]["sha256"])
        common.atomic_json(self.output, envelope(context))
        self.assertFalse(common.cache_matches(self.output, context))

    def test_unresolved_dependency_not_reusable(self):
        context = copy.deepcopy(self.context)
        context["runtime"]["packages"]["rapidocr"] = {"status": "not_installed_or_unresolved", "version": None}
        common.atomic_json(self.output, envelope(context))
        self.assertFalse(common.cache_matches(self.output, context))

    def test_missing_source_clear(self):
        self.video.unlink()
        with self.assertRaisesRegex(common.PipelineError, "missing or empty video"):
            common.ocr_context(self.video, self.profile)

    def test_atomic_serialization_failure_keeps_previous(self):
        previous = self.output.read_bytes()
        with self.assertRaises(ValueError):
            common.atomic_json(self.output, {"bad": float("nan")})
        self.assertEqual(previous, self.output.read_bytes())

    def test_atomic_replace_failure_keeps_previous(self):
        previous = self.output.read_bytes()
        with patch.object(common.os, "replace", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                common.atomic_json(self.output, {"new": True})
        self.assertEqual(previous, self.output.read_bytes())
        self.assertFalse(list(self.directory.glob(".fixture.json.*")))

    def test_raw_engine_strings_preserved_and_not_verified(self):
        common.validate_ocr(common.read_json(self.output), self.output)
        value = envelope(self.context)
        with patch.object(ocr, "recognize", return_value=(value["segments"], value["model_runtime_verification"])):
            ocr.process(self.video, self.output, self.profile, self.model, force=True)
        value = common.read_json(self.output)
        self.assertEqual(value["segments"][0]["raw_text_lines"], [" Synthetic raw typo. "])
        self.assertEqual(value["review_status"], common.REVIEW_STATUS)

    def test_model_configuration_alone_not_accepted(self):
        engine = SimpleNamespace(text_rec=SimpleNamespace(config={"model_path": str(self.model)}))
        with self.assertRaisesRegex(common.PipelineError, "Cannot verify"):
            ocr.verify_loaded_recognition_model(engine, self.model)

    def test_changed_ocr_archives_prior_raw_bytes(self):
        previous = self.output.read_bytes()
        previous_hash = common.sha256_file(self.output)
        value = envelope(self.context)
        lines = [{"start": 1, "end": 2, "text": "New raw recognition.", "raw_text_lines": [" New raw recognition. "]}]
        with patch.object(ocr, "recognize", return_value=(lines, value["model_runtime_verification"])):
            ocr.process(self.video, self.output, self.profile, self.model, force=True)
        archive = self.directory / "raw-revisions" / "fixture" / f"{previous_hash}.json"
        self.assertEqual(previous, archive.read_bytes())
        self.assertEqual(common.read_json(self.output)["segments"], lines)

    def test_actual_loaded_model_observed(self):
        session_type = type("SyntheticOrtSession", (), {"__module__": "onnxruntime.synthetic"})
        session = session_type()
        session._model_path = str(self.model)
        engine = SimpleNamespace(text_rec=SimpleNamespace(session=SimpleNamespace(session=session)))
        verification = ocr.verify_loaded_recognition_model(engine, self.model)
        self.assertEqual(verification["sha256"], common.sha256_file(self.model))
        self.assertEqual(verification["status"], "observed_loaded_recognition_asset")

    def test_loaded_model_mismatch_rejected(self):
        different = self.directory / "different.onnx"
        different.write_bytes(b"different model fixture")
        session_type = type("SyntheticOrtSession", (), {"__module__": "onnxruntime.synthetic"})
        session = session_type()
        session._model_path = str(different)
        engine = SimpleNamespace(text_rec=SimpleNamespace(session=session))
        with self.assertRaisesRegex(common.PipelineError, "different recognition model"):
            ocr.verify_loaded_recognition_model(engine, self.model)

    def test_cache_missing_runtime_model_verification_rejected(self):
        value = common.read_json(self.output)
        del value["model_runtime_verification"]
        common.atomic_json(self.output, value)
        self.assertFalse(common.cache_matches(self.output, self.context))

    def test_failed_ffmpeg_no_publication(self):
        previous = self.output.read_bytes()
        proc = unittest.mock.Mock()
        proc.stdout = io.BytesIO(b"1234")
        proc.wait.return_value = 7
        proc.poll.return_value = 7
        cfg = {"width": 2, "height": 2, "strip_height": 2, "strip_y0": 0, "sample_fps": 1}
        with patch.object(ocr, "probe_size", return_value=(2, 2)), patch.object(ocr.subprocess, "Popen", return_value=proc):
            with patch.object(ocr, "recognize", side_effect=lambda *args: list(ocr.decoded_strips("fixture", cfg))):
                with self.assertRaisesRegex(common.PipelineError, "FFmpeg failed \\(7\\)"):
                    ocr.process(self.video, self.output, self.profile, self.model, force=True)
        self.assertEqual(previous, self.output.read_bytes())

    def test_partial_decode_fails(self):
        proc = unittest.mock.Mock()
        proc.stdout = io.BytesIO(b"123")
        proc.wait.return_value = 0
        cfg = {"width": 2, "height": 2, "strip_height": 2, "strip_y0": 0, "sample_fps": 1}
        with patch.object(ocr, "probe_size", return_value=(2, 2)), patch.object(ocr.subprocess, "Popen", return_value=proc):
            with self.assertRaisesRegex(common.PipelineError, "incomplete frame"):
                list(ocr.decoded_strips("fixture", cfg))

    def test_zero_frame_decode_fails(self):
        proc = unittest.mock.Mock()
        proc.stdout = io.BytesIO()
        proc.wait.return_value = 0
        cfg = {"width": 2, "height": 2, "strip_height": 2, "strip_y0": 0, "sample_fps": 1}
        with patch.object(ocr, "probe_size", return_value=(2, 2)), patch.object(ocr.subprocess, "Popen", return_value=proc):
            with self.assertRaisesRegex(common.PipelineError, "no frames"):
                list(ocr.decoded_strips("fixture", cfg))


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "repository"
        self.ocr_dir = self.directory / "ocr"
        self.ocr_dir.mkdir()
        self.listing = self.directory / "videos.tsv"
        self.listing.write_text("new\tNew Title [Design Specifics]\t30\nold\tOld Title [Special]\t20\n")
        for video_id in ("old", "new"):
            common.atomic_json(self.ocr_dir / f"{video_id}.json", [{"start": 1, "end": 2, "text": f"{video_id} synthetic raw content."}])
        self.plan = transcripts.build(self.listing, self.ocr_dir, self.root, initialize=True)

    def index(self):
        with (self.root / "episodes" / "index.csv").open(newline="") as stream:
            return list(csv.DictReader(stream))

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_reordered_listing_preserves_ids_and_paths(self):
        previous = self.index()
        self.listing.write_text("old\tOld Title [Special]\t20\nnew\tNew Title [Design Specifics]\t30\n")
        transcripts.build(self.listing, self.ocr_dir, self.root)
        self.assertEqual(previous, self.index())

    def test_title_edit_does_not_move_existing_raw(self):
        previous = self.index()
        raw_path = self.root / previous[0]["transcript"]
        raw = raw_path.read_bytes()
        self.listing.write_text("new\tNew Title [Design Specifics]\t30\nold\tRenamed Title [Special]\t20\n")
        plan = transcripts.build(self.listing, self.ocr_dir, self.root)
        self.assertEqual(previous[0]["transcript"], self.index()[0]["transcript"])
        self.assertEqual("Renamed Title", self.index()[0]["title"])
        self.assertEqual(raw, raw_path.read_bytes())
        self.assertEqual(plan["documents"][0]["projection_status"], "existing_raw_retained_not_regenerated")
        self.assertFalse(list((self.root / "episodes" / "transcripts").glob("*renamed*")))

    def test_unknown_video_rejected_no_publication(self):
        previous = self.snapshot()
        self.listing.write_text(self.listing.read_text() + "unknown\tUnknown Title\t10\n")
        with self.assertRaisesRegex(common.PipelineError, "unknown=.*unknown"):
            transcripts.build(self.listing, self.ocr_dir, self.root)
        self.assertEqual(previous, self.snapshot())

    def test_removed_video_rejected_no_publication(self):
        self.listing.write_text("old\tOld Title [Special]\t20\n")
        with self.assertRaisesRegex(common.PipelineError, "missing=.*new"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def test_missing_ocr_clear_and_no_publication(self):
        previous = self.snapshot()
        (self.ocr_dir / "new.json").unlink()
        with self.assertRaisesRegex(common.PipelineError, "new.json: missing OCR"):
            transcripts.build(self.listing, self.ocr_dir, self.root)
        self.assertEqual(previous, self.snapshot())

    def test_empty_ocr_requires_review(self):
        common.atomic_json(self.ocr_dir / "new.json", [])
        with self.assertRaisesRegex(common.PipelineError, "empty OCR.*reviewed empty-source"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def test_reviewed_empty_source_is_explicit(self):
        (self.ocr_dir / "new.json").unlink()
        decisions = self.directory / "decisions.json"
        common.atomic_json(decisions, {"schema_version": 1, "decisions": [{"video_id": "new", "status": "reviewed_empty_source",
                                                                         "reviewed_by": "Synthetic reviewer", "reason": "Synthetic test only"}]})
        plan = transcripts.build(self.listing, self.ocr_dir, self.root, decisions_path=decisions, replace_existing=True)
        self.assertEqual(plan["documents"][1]["ocr_source"]["status"], "reviewed_empty_source")
        self.assertIn("explicitly reviewed", (self.root / self.index()[1]["transcript"]).read_text())

    def test_review_decision_does_not_hide_malformed_ocr(self):
        (self.ocr_dir / "new.json").write_text("broken json")
        decisions = self.directory / "decisions.json"
        common.atomic_json(decisions, {"schema_version": 1, "decisions": [{"video_id": "new", "status": "reviewed_empty_source",
                                                                         "reviewed_by": "Synthetic", "reason": "fixture"}]})
        with self.assertRaisesRegex(common.PipelineError, "cannot read valid JSON"):
            transcripts.build(self.listing, self.ocr_dir, self.root, decisions_path=decisions)

    def test_correction_sidecar_not_applied_and_raw_not_overwritten(self):
        corrections = self.root / "knowledge" / "annotations.json"
        common.atomic_json(corrections, {"corrections": [{"proposed_text": "Do not replace raw content"}]})
        previous = self.snapshot()
        plan = transcripts.build(self.listing, self.ocr_dir, self.root)
        self.assertFalse(plan["corrections_applied"])
        for name, content in previous.items():
            if name.endswith(".md") or name == "knowledge/annotations.json":
                self.assertEqual(content, (self.root / name).read_bytes())

    def test_explicit_replacement_archives_previous_raw(self):
        row = self.index()[0]
        target = self.root / row["transcript"]
        original = target.read_bytes()
        original_hash = common.sha256_file(target)
        common.atomic_json(self.ocr_dir / "old.json", [{"start": 1, "end": 2, "text": "Different OCR, not editorial correction."}])
        transcripts.build(self.listing, self.ocr_dir, self.root, replace_existing=True)
        archive = self.root / "episodes" / "transcript-revisions" / "old" / f"{original_hash}.md"
        self.assertEqual(original, archive.read_bytes())
        self.assertIn("Different OCR", target.read_text())

    def test_plan_only_has_no_writes(self):
        previous = self.snapshot()
        plan = transcripts.build(self.listing, self.ocr_dir, self.root, plan_only=True)
        self.assertEqual(previous, self.snapshot())
        self.assertFalse(plan["original_inherited_provenance_reconstructed"])

    def test_fresh_tree_requires_explicit_initialization(self):
        with self.assertRaisesRegex(common.PipelineError, "initialize-index required"):
            transcripts.build(self.listing, self.ocr_dir, self.directory / "empty")

    def test_invalid_segment_rejected(self):
        common.atomic_json(self.ocr_dir / "old.json", [{"start": 4, "end": 1, "text": "Bad"}])
        with self.assertRaisesRegex(common.PipelineError, "reversed"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def test_unknown_ocr_document_rejected(self):
        common.atomic_json(self.ocr_dir / "unindexed.json", [])
        with self.assertRaisesRegex(common.PipelineError, "unknown OCR documents"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def versioned_source(self, name="old", profile=None):
        video = self.directory / f"{name}.mp4"
        video.write_bytes(b"synthetic asset only")
        model = self.directory / "model.onnx"
        model.write_bytes(b"synthetic model only")
        with patch.object(common, "runtime_metadata", side_effect=runtime):
            context = common.ocr_context(video, profile or common.load_profile(), model)
        common.atomic_json(self.ocr_dir / "old.json", envelope(context))

    def test_versioned_source_metadata_accepted(self):
        self.versioned_source()
        plan = transcripts.build(self.listing, self.ocr_dir, self.root, plan_only=True)
        self.assertEqual(plan["documents"][0]["ocr_source"]["status"], "versioned_raw_ocr")

    def test_versioned_source_wrong_video_rejected(self):
        self.versioned_source(name="different")
        with self.assertRaisesRegex(common.PipelineError, "OCR video identity mismatch"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def test_versioned_source_wrong_profile_rejected(self):
        profile = common.load_profile()
        profile["ocr"]["sample_fps"] = 2
        self.versioned_source(profile=profile)
        with self.assertRaisesRegex(common.PipelineError, "OCR source profile mismatch"):
            transcripts.build(self.listing, self.ocr_dir, self.root)

    def test_ordinary_publication_failure_rolls_back(self):
        first, second = self.directory / "first", self.directory / "second"
        first.write_bytes(b"previous")
        real = transcripts.atomic_bytes
        def failing(path, content):
            if path == second:
                raise OSError("fixture publication failure")
            real(path, content)
        with patch.object(transcripts, "atomic_bytes", side_effect=failing):
            with self.assertRaises(OSError):
                transcripts.publish({first: b"changed", second: b"new"})
        self.assertEqual(b"previous", first.read_bytes())
        self.assertFalse(second.exists())


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.profile = common.load_profile()

    def listing(self):
        path = self.work / "videos.tsv"
        path.write_text("fixture\tSynthetic title\t10\n")
        return path

    def test_default_fetch_requires_frozen_listing_no_network(self):
        with patch.object(acquisition.subprocess, "run") as call:
            with self.assertRaisesRegex(common.PipelineError, "frozen listing missing"):
                acquisition.freeze_listing(self.work, self.profile)
            call.assert_not_called()

    def test_frozen_listing_no_refresh_and_hash_preserved(self):
        path = self.listing()
        original = path.read_bytes()
        with patch.object(acquisition.subprocess, "run") as call:
            target, metadata = acquisition.freeze_listing(self.work, self.profile)
            call.assert_not_called()
        self.assertEqual(original, target.read_bytes())
        self.assertEqual(common.sha256_file(path), metadata["sha256"])
        self.assertEqual(original, (self.work / metadata["snapshot"]).read_bytes())
        self.assertFalse(metadata["original_inherited_provenance_reconstructed"])

    def test_failed_refresh_preserves_previous_listing(self):
        path = self.listing()
        previous = path.read_bytes()
        with patch.object(acquisition.subprocess, "run", side_effect=subprocess.CalledProcessError(4, ["fixture"])):
            with self.assertRaises(subprocess.CalledProcessError):
                acquisition.freeze_listing(self.work, self.profile, refresh=True)
        self.assertEqual(previous, path.read_bytes())

    def test_invalid_refresh_preserves_previous_listing(self):
        path = self.listing()
        previous = path.read_bytes()
        with patch.object(acquisition.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=b"malformed")):
            with self.assertRaises(common.PipelineError):
                acquisition.freeze_listing(self.work, self.profile, refresh=True)
        self.assertEqual(previous, path.read_bytes())

    def test_missing_expected_video_starts_no_workers(self):
        self.listing()
        with patch.object(runner, "run_worker") as call:
            with self.assertRaisesRegex(common.PipelineError, "missing or empty expected video"):
                runner.run_all(self.work, sys.executable)
            call.assert_not_called()

    def test_failed_ocr_worker_no_completion_manifest(self):
        self.listing()
        (self.work / "video").mkdir()
        (self.work / "video" / "fixture.mp4").write_bytes(b"synthetic")
        with patch.object(runner, "run_worker", side_effect=subprocess.CalledProcessError(2, ["fixture"])):
            with self.assertRaisesRegex(common.PipelineError, "OCR worker failures"):
                runner.run_all(self.work, sys.executable)
        self.assertFalse((self.work / "ocr-manifest.json").exists())

    def test_failed_acquisition_worker_no_completion_manifest(self):
        self.listing()
        with patch.object(acquisition, "acquire_asset", side_effect=subprocess.CalledProcessError(3, ["fixture"])):
            with self.assertRaisesRegex(common.PipelineError, "acquisition worker failures"):
                acquisition.acquire(self.work, self.profile)
        self.assertFalse((self.work / "acquisition-manifest.json").exists())

    def test_duplicate_listing_rejected(self):
        path = self.listing()
        path.write_text(path.read_text() * 2)
        with self.assertRaisesRegex(common.PipelineError, "duplicate video"):
            common.read_listing(path, self.profile)

    def test_imports_are_lazy(self):
        script = '''import builtins, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'numpy', 'rapidocr', 'onnxruntime'}:
        raise AssertionError('eager OCR dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import ocr_subs, pipeline_common, pipeline_run, pipeline_acquire, build_transcripts
'''
        subprocess.run([sys.executable, "-I", "-c", script, str(TOOLS)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
