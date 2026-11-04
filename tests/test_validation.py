import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tools.validate import validate
from test_validation_helpers import fixture, edit_json, edit_jsonl, write_json


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = fixture(Path(self.temp.name))

    def assertInvalid(self, fragment):
        report = validate(self.root)
        self.assertFalse(report.ok)
        self.assertIn(fragment, json.dumps(report.as_dict()))

    def test_valid_optional_blanks(self):
        self.assertTrue(validate(self.root).ok)

    def test_missing_dataset(self):
        (self.root / 'work/parts/essence-lenses.jsonl').unlink()
        self.assertInvalid('missing nonempty lenses')

    def test_duplicate_id(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows.append(rows[0].copy()))
        self.assertInvalid('duplicate id')

    def test_missing_required_field(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows[0].pop('why'))
        self.assertInvalid('missing required fields')

    def test_unexpected_field(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows[0].update(source_id='do-not-drop'))
        self.assertInvalid('unexpected fields')

    def test_unknown_domain(self):
        edit_jsonl(self.root / 'work/batches/batch-01.jsonl', lambda rows: rows[0]['principles'][0].update(domain='oops'))
        self.assertInvalid('unknown domain')

    def test_wrong_type(self):
        edit_jsonl(self.root / 'work/batches/batch-01.jsonl', lambda rows: rows[0].update(ep=True))
        self.assertInvalid('expected integer')

    def test_unknown_priority(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows[0].update(priority='URGENT'))
        self.assertInvalid('unknown priority')

    def test_dangling_episode(self):
        edit_jsonl(self.root / 'work/parts/essence-techniques.jsonl', lambda rows: rows[0].update(episodes='999'))
        self.assertInvalid('dangling reference')

    def test_dangling_lens(self):
        edit_jsonl(self.root / 'work/parts/essence-lenses.jsonl', lambda rows: rows[0].update(principles='ESS-99'))
        self.assertInvalid('dangling reference')

    def test_batch_owner(self):
        edit_jsonl(self.root / 'work/batches/batch-01.jsonl', lambda rows: rows[0].update(ep=2))
        self.assertInvalid('outside owning batch')

    def test_malformed_json(self):
        (self.root / 'work/parts/essence-lenses.jsonl').write_text('{broken\n')
        self.assertInvalid('essence-lenses.jsonl:1')

    def test_missing_notes(self):
        (self.root / 'episodes/notes/001-fixture.md').unlink()
        self.assertInvalid('missing file')

    def test_contained_path(self):
        edit_json(self.root / 'knowledge/catalogue.json', lambda x: x['documents'][0].update(notes_path='../outside.md'))
        self.assertInvalid('within repository root')

    def test_symlink_escape(self):
        target = self.root / 'episodes/notes/001-fixture.md'
        target.unlink()
        target.symlink_to('/etc/hosts')
        self.assertInvalid('within repository root')

    def test_missing_sidecar(self):
        (self.root / 'knowledge/claims.json').unlink()
        self.assertInvalid('claims.json')

    def test_source_fk(self):
        edit_json(self.root / 'knowledge/catalogue.json', lambda x: x['documents'][0].update(source_id='absent:source'))
        self.assertInvalid('unknown source_id')

    def test_video_identity(self):
        edit_json(self.root / 'knowledge/catalogue.json', lambda x: x['documents'][0].update(video_id='XXXXXXXXXXX'))
        self.assertInvalid('document_id must equal')

    def test_transcript_hash(self):
        with (self.root / 'episodes/transcripts/001-fixture.md').open('a') as f:
            f.write('changed\n')
        self.assertInvalid('SHA-256 mismatch')

    def test_segment_pointer_hash(self):
        edit_json(self.root / 'knowledge/segments.json', lambda x: x['segments'][0].update(text_sha256='0'*64))
        self.assertInvalid('segment text SHA-256 mismatch')

    def test_dangling_evidence(self):
        edit_json(self.root / 'knowledge/claims.json', lambda x: x['claims'][0]['evidence'][0].update(document_id='book:missing'))
        self.assertInvalid('unknown evidence document_id')

    def test_timestamp_type(self):
        edit_json(self.root / 'knowledge/claims.json', lambda x: x['claims'][0]['evidence'][0]['locator'].update(start_seconds='3'))
        self.assertInvalid('finite number')

    def test_annotation_claim(self):
        edit_json(self.root / 'knowledge/annotations.json', lambda x: x['items']['ESS-01'].update(evidence_claim_ids=['ABSENT']))
        self.assertInvalid('unknown evidence claim')

    def test_pending_source_has_no_documents(self):
        edit_json(self.root / 'knowledge/catalogue.json', lambda x: x['sources'][0].update(status='pending'))
        self.assertInvalid('pending sources must have zero')

    def test_pending_source_without_claims_allowed(self):
        edit_json(self.root / 'knowledge/catalogue.json', lambda x: x['sources'].append({'source_id':'synthetic:pending', 'author':'Synthetic', 'work':'Unavailable fixture', 'kind':'book', 'language':'en', 'status':'pending', 'url':''}))
        self.assertTrue(validate(self.root).ok)

    def test_synthetic_book_page(self):
        def catalogue(x):
            x['sources'].append({'source_id':'fixture:book', 'author':'Synthetic', 'work':'Synthetic book fixture', 'kind':'book', 'language':'en', 'status':'available', 'url':'https://example.invalid'})
            x['documents'].append({'document_id':'book:synthetic-fixture', 'source_id':'fixture:book', 'title':'Synthetic book', 'url':'https://example.invalid', 'language':'en', 'translation_layer':'none', 'review_status':'unreviewed', 'page_count':10})
        edit_json(self.root / 'knowledge/catalogue.json', catalogue)
        edit_json(self.root / 'knowledge/claims.json', lambda x: x['claims'][0].update(evidence=[{'document_id':'book:synthetic-fixture','locator':{'kind':'page','page':3}}]))
        self.assertTrue(validate(self.root).ok)
        edit_json(self.root / 'knowledge/claims.json', lambda x: x['claims'][0]['evidence'][0]['locator'].update(page=0))
        self.assertInvalid('expected integer')

    def test_ocr_suspect_is_warning(self):
        edit_json(self.root / 'knowledge/segments.json', lambda x: x['segments'][0].update(suspect=True))
        report = validate(self.root)
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)

    def test_unexpected_csv_header(self):
        path = self.root / 'skills/sakurai-game-design/data/principles.csv'
        path.write_text(path.read_text().replace('id,area', 'oops,area', 1))
        self.assertInvalid('expected CSV headers')

    def test_stale_exports_do_not_block_input_preflight(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows[0].update(why='New authored reason'))
        self.assertInvalid('projection differs')
        self.assertTrue(validate(self.root, check_outputs=False).ok)

    def test_json_cli_success_and_failure(self):
        script = Path(__file__).resolve().parents[1] / 'tools/validate.py'
        command = [sys.executable, str(script), '--root', str(self.root), '--json']
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        (self.root / 'knowledge/claims.json').unlink()
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(json.loads(result.stdout)['ok'])

    def test_malformed_sidecar_field_types_are_diagnostics(self):
        for name, key in [('catalogue', 'sources'), ('catalogue', 'documents'), ('segments', 'segments'), ('claims', 'claims')]:
            path = self.root / 'knowledge' / (name + '.json')
            original = json.loads(path.read_text())
            for field in original[key][0]:
                for value in [None, [], {}, True, 3]:
                    with self.subTest(sidecar=name, field=field, value=value):
                        modified = copy.deepcopy(original)
                        modified[key][0][field] = value
                        write_json(path, modified)
                        report = validate(self.root)
                        self.assertIsInstance(report.errors, list)
            write_json(path, original)


if __name__ == '__main__':
    unittest.main()
