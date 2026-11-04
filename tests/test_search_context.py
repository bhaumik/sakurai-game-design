"""Retrieval regressions; read-only corpus tests plus isolated corruption fixtures."""
import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/sakurai-game-design/scripts"
sys.path.insert(0, str(SCRIPTS))
import search
from evidence import DataError, EvidenceStore


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = EvidenceStore(ROOT / "knowledge", ROOT)
        cls.cozy = search.load_context(ROOT / "examples/context-cozy.json")
        cls.sword = search.load_context(ROOT / "examples/context-sword.json")
        cls.novice = search.load_context(ROOT / "examples/context-novice.json")

    def response(self, query, review=False, context=None, domains=None, area=None, n=5, source="sakurai"):
        return search.build_response(query, domains or search.DEFAULT_MIX, n, area, context or {}, source, review, self.store)

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = search.main(args)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def assert_arg_error(self, args):
        code, out, err = self.cli(args)
        self.assertEqual(code, 2, (out, err))
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)

    def test_plural_singular_same_routing_and_ranks(self):
        first = self.response("hits feel weak", n=2)
        second = self.response("hit feel weak", n=2)
        self.assertEqual(first["hinted_areas"], second["hinted_areas"])
        for domain in search.DEFAULT_MIX:
            self.assertEqual([(r["id"], r["score"]) for r in first["results"][domain]], [(r["id"], r["score"]) for r in second["results"][domain]])

    def test_weak_hits_direct_principle_above_boss_strategy(self):
        rows = self.response("hits feel weak")["results"]["principles"]
        self.assertEqual(rows[0]["id"], "FEEL-02")
        self.assertNotIn("ESS-13", [r["id"] for r in rows[:2]])

    def test_hint_is_not_hard_gate(self):
        rows = self.response("hits feel weak")["results"]["principles"]
        self.assertTrue(any(r["area"] != "feel" for r in rows))

    def test_cozy_query_does_not_route_on_negated_combat(self):
        result = self.response("cozy narrative game with dialogue, gardening, no combat and no time pressure", review=True, n=2)
        self.assertNotIn("essence", result["hinted_areas"])
        self.assertEqual(result["inferred_exclusions"], ["combat", "time_pressure"])
        for rows in result["results"].values():
            for row in rows:
                self.assertFalse(row["applicability"]["mandatory_change"])

    def test_cozy_pressure_principles_are_skipped(self):
        result = self.response("stress pressure growth", review=True, context=self.cozy, domains=["principles"], n=30)
        rows = {r["id"]: r for r in result["results"]["principles"]}
        self.assertIn("ESS-04", rows)
        self.assertEqual(rows["ESS-04"]["status"], "not_applicable")
        if "ESS-19" in rows:
            self.assertEqual(rows["ESS-19"]["status"], "not_applicable")

    def test_cozy_action_story_technique_not_required(self):
        result = self.response("story dialogue narrative", review=True, context=self.cozy, domains=["techniques"], n=20)
        row = next(r for r in result["results"]["techniques"] if r["id"] == "PLAN-T22")
        self.assertEqual(row["status"], "not_applicable")
        self.assertFalse(row["applicability"]["mandatory_change"])

    def test_novice_nonfighting_reversal_not_applicable(self):
        result = self.response("shoryuken reversal input", review=True, context=self.novice, domains=["techniques"], n=20)
        row = next(r for r in result["results"]["techniques"] if r["id"] == "ESS-T04")
        self.assertEqual(row["status"], "not_applicable")

    def test_novice_casual_does_not_prioritize_reversal(self):
        rows = self.response("novice casual game", review=True, context=self.novice, n=3)["results"]["techniques"]
        self.assertNotIn("ESS-T04", [r["id"] for r in rows])
        self.assertTrue(any("audience" in r["title"].lower() or "target" in r["title"].lower() for r in rows))

    def test_positive_sword_hitstop(self):
        rows = self.response("hitstop sword", review=True, context=self.sword, n=3)["results"]["techniques"]
        row = next(r for r in rows if r["id"] == "FEEL-T03")
        self.assertEqual(row["status"], "applicable")

    def test_applicable_precedes_priority(self):
        rows = self.response("combat stress story sword", review=True, context=self.cozy, n=50)["results"]["principles"]
        ranks = [search.APPLICABILITY_ORDER[r["status"]] for r in rows]
        self.assertEqual(ranks, sorted(ranks))

    def test_missing_scope_is_question_not_universal_fit(self):
        rows = self.response("skip pause cutscene", domains=["principles"])["results"]["principles"]
        self.assertTrue(rows)
        self.assertTrue(all(r["status"] == "needs_context" for r in rows))
        self.assertTrue(all(r["applicability"]["question"] for r in rows))

    def test_genre_alone_does_not_infer_exclusions(self):
        result = self.response("cozy narrative gardening")
        self.assertEqual(result["inferred_exclusions"], [])

    def test_koster_topic_is_source_mismatch(self):
        result = self.response("Raph Koster fun learning", review=True)
        self.assertEqual(result["status"], "source_mismatch")
        self.assertEqual(result["results"], {})

    def test_unknown_explicit_source(self):
        result = self.response("fun learning", source="raph-koster")
        self.assertEqual(result["status"], "source_mismatch")

    def test_pending_isbister_source(self):
        result = self.response("emotion", source="isbister:how-games-move-us")
        self.assertEqual(result["status"], "source_mismatch")
        self.assertFalse(result["results"])

    def test_pending_isbister_author_name(self):
        self.assertEqual(self.response("Katherine Isbister emotion")["status"], "source_mismatch")

    def test_documented_gaps(self):
        for query in ("input buffering", "coyote time", "input buffering coyote time", "input-buffering"):
            with self.subTest(query=query):
                result = self.response(query)
                self.assertEqual(result["status"], "unsupported_topic")
                self.assertFalse(result["results"])

    def test_negative_controls(self):
        for query in ("qzxvblorp", "postgres database migration"):
            with self.subTest(query=query):
                result = self.response(query, review=True)
                self.assertEqual(result["status"], "no_match")
                self.assertFalse(any(result["results"].values()))

    def test_json_result_contract_and_episode_links(self):
        code, out, err = self.cli(["hitstop sword", "--json", "-n", "2"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(result["filters"]["limit_per_domain"], 2)
        for rows in result["results"].values():
            for row in rows:
                for field in ("id", "score", "rank", "matched_fields", "sources", "status", "applicability"):
                    self.assertIn(field, row)
                self.assertTrue(row["sources"])
                for source in row["sources"]:
                    self.assertTrue(source["url"].startswith("https://"))
                    self.assertTrue((ROOT / source["notes_path"]).is_file())
                    self.assertTrue((ROOT / source["transcript_path"]).is_file())

    def test_episode_47_claim_join_and_segment_provenance(self):
        rows = self.response("hitstop sword", context=self.sword, n=3)["results"]["techniques"]
        row = next(r for r in rows if r["id"] == "FEEL-T03")
        self.assertTrue(any(s["episode"] == 47 for s in row["sources"]))
        self.assertEqual(row["claim_locator_status"], "available")
        self.assertTrue(row["claims"])
        for claim in row["claims"]:
            self.assertEqual(claim["review_status"], "retained_text_checked")
            for evidence in claim["evidence"]:
                self.assertIn("t=", evidence["document"]["time_url"])
                self.assertTrue(evidence["segments"])
                self.assertIn("review_status", evidence["segments"][0])

    def test_uncurated_results_still_join_sources(self):
        rows = self.response("hitstop sword", domains=["lenses"])["results"]["lenses"]
        self.assertTrue(rows)
        self.assertTrue(all(r["sources"] for r in rows))
        self.assertTrue(any(r["claim_locator_status"] == "unavailable" for r in rows))

    def test_quote_exact_dedup_and_themes(self):
        rows = self.response("Players press buttons", domains=["quotes"], n=5)["results"]["quotes"]
        duplicated = [r for r in rows if r["record"]["ep"] == "104" and r["record"]["time"] == "01:35"]
        self.assertEqual(len(duplicated), 1)
        self.assertGreaterEqual(duplicated[0]["record"]["duplicate_count"], 1)
        self.assertTrue(duplicated[0]["record"]["themes"])
        self.assertIn("t=95s", duplicated[0]["sources"][0]["time_url"])

    def test_duplicate_quote_fixture_preserves_themes(self):
        with (ROOT / "skills/sakurai-game-design/data/quotes.csv").open(newline="") as f:
            original = next(r for r in csv.DictReader(f) if r["ep"] == "104" and r["time"] == "01:35")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with (directory / "quotes.csv").open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["quote", *search.DOMAINS["quotes"][2]])
                writer.writeheader()
                writer.writerow({**original, "theme": "first annotation"})
                writer.writerow({**original, "theme": "second annotation"})
            with patch.object(search, "DATA_DIR", directory):
                rows = search.load("quotes")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["duplicate_count"], 2)
            self.assertEqual(rows[0]["themes"], ["first annotation", "second annotation"])

    def test_episode_47_quote_preserves_time_url(self):
        rows = self.response("hit stop", domains=["quotes"], n=40)["results"]["quotes"]
        rows = [r for r in rows if r["record"]["ep"] == "47"]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["record"]["time"], row["sources"][0]["timestamp"])
            self.assertIn("t=", row["sources"][0]["time_url"])

    def test_skip_pause_group_preserves_exceptions(self):
        result = self.response("skip pause cutscene", review=True, domains=["principles"])
        group = next(g for g in result["concern_groups"] if {"UI-01", "PLAN-21"} <= {m["id"] for m in g["members"]})
        members = {m["id"]: m for m in group["members"]}
        self.assertIn("online", members["UI-01"]["how_to_apply"])
        self.assertIn("line", members["PLAN-21"]["how_to_apply"])
        self.assertFalse(group["count_as_independent_confirmations"])

    def test_audience_risk_group(self):
        result = self.response("novice casual audience", review=True, domains=["principles"])
        self.assertTrue(any({"BAL-01", "CASE-01"} <= {m["id"] for m in g["members"]} for g in result["concern_groups"]))

    def test_metadata_not_searchable_design_evidence(self):
        self.assertEqual(self.response("T03", domains=["techniques"])["status"], "no_match")
        for domain in search.DOMAINS:
            self.assertFalse(set(search.weighted_fields(domain)) & {"id", "ep", "episodes", "url", "notes", "area", "priority", "principles"})

    def test_review_honors_area(self):
        result = self.response("cozy narrative dialogue no combat no time pressure", review=True, area="ui", n=2)
        self.assertTrue(result["results"]["principles"])
        self.assertTrue(all(r["area"] == "ui" for rows in result["results"].values() for r in rows))
        self.assertTrue(all(m["area"] == "ui" for group in result["concern_groups"] for m in group["members"]))

    def test_review_honors_domain_and_limit(self):
        result = self.response("skip pause cutscene", review=True, domains=["quotes"], n=2)
        self.assertEqual(set(result["results"]), {"quotes"})
        self.assertLessEqual(len(result["results"]["quotes"]), 2)

    def test_review_limit_per_domain(self):
        result = self.response("hitstop sword", review=True, n=2)
        self.assertTrue(all(len(rows) <= 2 for rows in result["results"].values()))

    def test_invalid_limits(self):
        for limit in ("0", "-1"):
            with self.subTest(limit=limit):
                self.assert_arg_error(["hitstop", "-n", limit])
                self.assert_arg_error(["--review", "hitstop", "-n", limit])

    def test_invalid_area(self):
        self.assert_arg_error(["difficulty", "--area", "balnce"])

    def test_unsupported_area_combinations(self):
        for domain in ("quotes", "glossary", "episodes"):
            with self.subTest(domain=domain):
                self.assert_arg_error(["difficulty", "--domain", domain, "--area", "balance"])
                self.assert_arg_error(["--review", "difficulty", "--domain", domain, "--area", "balance"])

    def test_conflicting_modes(self):
        for args in (["--episode", "3", "--transcript", "47"], ["hitstop", "--review", "sword"], ["--areas", "--review", "hitstop"]):
            with self.subTest(args=args):
                self.assert_arg_error(args)

    def test_zero_episode_and_empty_text(self):
        for args in (["--episode", "0"], ["--transcript", "0"], ["--review", ""], [""], ["--review", "   "]):
            with self.subTest(args=args):
                self.assert_arg_error(args)

    def test_missing_episode_clean_failure(self):
        code, out, err = self.cli(["--episode", "999"])
        self.assertEqual(code, 1)
        self.assertIn("episode 999 not found", err)
        self.assertNotIn("Traceback", err)

    def test_source_selector_document_and_area_modes(self):
        for args in (["--episode", "47"], ["--transcript", "47"], ["--areas"]):
            with self.subTest(args=args):
                code, out, err = self.cli([*args, "--source", "isbister:how-games-move-us", "--json"])
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(out)["status"], "source_mismatch")

    def test_source_selector_review_quotes_glossary(self):
        for args in (["--review", "fun"], ["fun", "--domain", "quotes"], ["fun", "--domain", "glossary"]):
            with self.subTest(args=args):
                code, out, err = self.cli([*args, "--source", "Koster", "--json"])
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(out)["status"], "source_mismatch")

    def test_malformed_context_and_invalid_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            for content in ("{broken", "[]", '{"unknown": "x"}', '{"mechanics": 3}', '{"audience": null}', '{"genre": ""}', '{"input": [true]}'):
                with self.subTest(content=content):
                    path.write_text(content)
                    self.assert_arg_error(["hitstop", "--context", str(path)])
            self.assert_arg_error(["hitstop", "--context", str(path.parent / "missing.json")])

    def test_missing_csv_is_data_error_not_no_match(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(search, "DATA_DIR", Path(directory)):
            code, out, err = self.cli(["hitstop", "--json"])
            self.assertEqual(code, 1, err)
            self.assertEqual(json.loads(out)["status"], "data_error")

    def test_malformed_csv_is_data_error(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(search, "DATA_DIR", Path(directory)):
            (Path(directory) / "principles.csv").write_text("id,principle\nX,bad\n")
            with self.assertRaises(DataError):
                search.load("principles")

    def test_missing_each_required_sidecar_is_data_error(self):
        for name in ("catalogue.json", "claims.json", "annotations.json", "segments.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                for source in (ROOT / "knowledge").glob("*.json"):
                    if source.name != name:
                        shutil.copyfile(source, target / source.name)
                with patch.object(search, "KNOWLEDGE_DIR", target):
                    code, out, err = self.cli(["hitstop", "--json"])
                    self.assertEqual(code, 1, err)
                    self.assertEqual(json.loads(out)["status"], "data_error")

    def test_corrupt_sidecar_and_broken_claim_join(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for source in (ROOT / "knowledge").glob("*.json"):
                shutil.copyfile(source, target / source.name)
            claims = json.loads((target / "claims.json").read_text())
            claims["claims"][0]["evidence"][0]["document_id"] = "youtube:not-real"
            (target / "claims.json").write_text(json.dumps(claims))
            with self.assertRaises(DataError):
                EvidenceStore(target, ROOT)
            (target / "claims.json").write_text("{broken")
            with self.assertRaises(DataError):
                EvidenceStore(target, ROOT)

    def test_markdown_has_scores_fields_links_and_qualifiers(self):
        code, out, err = self.cli(["hitstop sword", "-n", "2"])
        self.assertEqual(code, 0, err)
        for expected in ("**Score:**", "**Matched fields:**", "youtube:", "Notes:", "transcript:", "retained_text_checked", "Limitations:"):
            self.assertIn(expected, out)


if __name__ == "__main__":
    unittest.main()
