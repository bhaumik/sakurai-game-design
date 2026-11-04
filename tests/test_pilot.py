import csv
import hashlib
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


class EvidencePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = read_json('knowledge/catalogue.json')
        cls.claims = read_json('knowledge/claims.json')['claims']
        cls.annotations = read_json('knowledge/annotations.json')
        cls.segments = {s['segment_id']:s for s in read_json('knowledge/segments.json')['segments']}
        cls.documents = {d['document_id']:d for d in cls.catalogue['documents']}

    def test_pilot_checks_are_not_video_verification(self):
        self.assertEqual(len(self.claims), 24)
        for claim in self.claims:
            self.assertEqual(claim['review_status'], 'retained_text_checked')
            self.assertIn('Not checked against original video', claim['limitations'])
        for document in self.documents.values():
            self.assertEqual(document['review_status'], 'unreviewed_ocr')

    def test_book_remains_pending_without_fabricated_material(self):
        book_id = 'isbister:how-games-move-us'
        book = next(s for s in self.catalogue['sources'] if s['source_id'] == book_id)
        self.assertEqual(book['status'], 'pending')
        self.assertFalse([d for d in self.documents.values() if d['source_id'] == book_id])

    def test_original_transcript_hashes_still_match(self):
        for doc in self.documents.values():
            data = (ROOT / doc['transcript_path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), doc['transcript_sha256'])

    def test_exact_claim_spans_resolve_retained_paragraphs(self):
        for claim in self.claims:
            for evidence in claim['evidence']:
                locator = evidence['locator']
                self.assertLess(locator['start_seconds'], locator['end_seconds'])
                self.assertTrue(locator['segment_ids'])
                for sid in locator['segment_ids']:
                    seg = self.segments[sid]
                    self.assertEqual(seg['document_id'], evidence['document_id'])
                    self.assertGreaterEqual(seg['start_seconds'], locator['start_seconds'])
                    self.assertLess(seg['start_seconds'], locator['end_seconds'])

    def test_numeric_blend_detail_not_universal_stop_duration(self):
        blend = next(c for c in self.claims if c['claim_id'] == 'SK-047-BLEND')
        self.assertIn('not a general hitstop duration', blend['text'])
        self.assertEqual(blend['context']['numeric_scope'], 'damage-pose blend only')

    def test_risk_reward_boundary_is_linked_both_ways(self):
        items = self.annotations['items']
        self.assertIn({'item_id':'ESS-17','relation':'qualified_by'},items['ESS-01']['related'])
        self.assertIn({'item_id':'ESS-01','relation':'qualifies'},items['ESS-17']['related'])

    def test_unresolved_ocr_is_not_guessed(self):
        self.assertEqual(len(self.annotations['corrections']), 7)
        for correction in self.annotations['corrections']:
            self.assertEqual(correction['status'], 'unresolved')
            self.assertIsNone(correction['proposed_text'])
            self.assertTrue(self.segments[correction['segment_id']]['suspect'])

    def test_experiment_templates_contain_no_results(self):
        claim_ids = {c['claim_id'] for c in self.claims}
        for path in (ROOT / 'experiments/templates').glob('*.json'):
            template = json.loads(path.read_text())
            self.assertEqual(template['claim_type'], 'application_hypothesis')
            self.assertEqual(template['status'], 'not_run')
            self.assertEqual(template['observations'], [])
            self.assertIsNone(template['decision'])
            self.assertTrue(set(template['source_claim_ids']) <= claim_ids)
            self.assertTrue(all(v is None for v in template['parameters'].values()))


if __name__ == '__main__':
    unittest.main()
