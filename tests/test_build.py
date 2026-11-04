import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import build_data, build_guide
from tools.contracts import ContractError, DATA_PATH, projected_data, publish, read_jsonl
from tools.validate import validate
from test_validation_helpers import fixture, edit_jsonl


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = fixture(Path(self.temp.name))

    def snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_invalid_input_preserves_outputs(self):
        path = self.root / 'work/parts/essence-principles.jsonl'
        edit_jsonl(path, lambda rows: rows[0].update(unknown='do not drop'))
        before = self.snapshot()
        with self.assertRaises(ContractError):
            build_data.build_data(self.root)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_id_preserves_outputs(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows.append(rows[0].copy()))
        before = self.snapshot()
        with self.assertRaises(ContractError):
            build_data.build_data(self.root)
        self.assertEqual(before, self.snapshot())

    def test_areas_invalid_domain_preserves_outputs(self):
        edit_jsonl(self.root / 'work/batches/batch-01.jsonl', lambda rows: rows[0]['principles'][0].update(domain='absent'))
        before = self.snapshot()
        with self.assertRaises(ContractError):
            build_data.build_areas(self.root)
        self.assertEqual(before, self.snapshot())

    def test_missing_csv_guide_fails_without_changes(self):
        (self.root / DATA_PATH / 'lenses.csv').unlink()
        before = self.snapshot()
        with self.assertRaises(ContractError) as error:
            build_guide.build_guide(self.root)
        self.assertIn('lenses.csv', str(error.exception))
        self.assertEqual(before, self.snapshot())

    def test_missing_ref_guide_fails_without_changes(self):
        path = self.root / DATA_PATH / 'lenses.csv'
        path.write_text(path.read_text().replace('ESS-01', 'ESS-99'))
        before = self.snapshot()
        with self.assertRaises(ContractError):
            build_guide.build_guide(self.root)
        self.assertEqual(before, self.snapshot())

    def test_missing_chapter_guide_fails_without_changes(self):
        (self.root / 'study-guide/02-game-essence.md').unlink()
        before = self.snapshot()
        with self.assertRaises(ContractError):
            build_guide.build_guide(self.root)
        self.assertEqual(before, self.snapshot())

    def test_guide_render_error_preserves_outputs(self):
        before = self.snapshot()
        with patch.object(build_guide, 'glossary', side_effect=RuntimeError('synthetic render failure')):
            with self.assertRaises(RuntimeError):
                build_guide.build_guide(self.root)
        self.assertEqual(before, self.snapshot())

    def test_rebuild_stale_exports_allowed(self):
        edit_jsonl(self.root / 'work/parts/essence-principles.jsonl', lambda rows: rows[0].update(why='Changed authored reason'))
        build_data.build_data(self.root)
        self.assertTrue(validate(self.root).ok)

    def test_quote_dedup_merges_themes_preserves_locator(self):
        path = self.root / 'work/parts/essence-quotes.jsonl'
        def mutate(rows):
            rows.append({**rows[0], 'theme':'second theme'})
            rows.append({**rows[0], 'time':'00:04', 'theme':'another location'})
        edit_jsonl(path, mutate)
        build_data.build_data(self.root)
        with (self.root / DATA_PATH / 'quotes.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['theme'], 'synthetic; second theme')
        self.assertEqual([r['time'] for r in rows], ['00:03','00:04'])
        self.assertTrue(validate(self.root).ok)

    def test_glossary_merge_retained(self):
        path = self.root / 'work/parts/essence-glossary.jsonl'
        edit_jsonl(path, lambda rows: rows.append({**rows[0], 'term':'term'}))
        build_data.build_data(self.root)
        with (self.root / DATA_PATH / 'glossary.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['episodes'],'1')
        self.assertEqual(rows[0]['meaning'],'Meaning')

    def test_stale_generated_area_reconciled_authored_survives(self):
        stale = self.root / 'work/areas/audio.jsonl'
        stale.write_text('old output\n')
        authored = self.root / 'work/areas/reviewer-notes.md'
        authored.write_text('Authored notes\n')
        edit_jsonl(self.root / 'work/batches/batch-01.jsonl', lambda rows: rows[0].update(principles=[]))
        build_data.build_areas(self.root)
        self.assertFalse(stale.exists())
        self.assertFalse((self.root / 'work/areas/essence.jsonl').exists())
        self.assertEqual(authored.read_text(), 'Authored notes\n')

    def test_publication_replace_exception_rolls_back(self):
        a, b = self.root / 'a.txt', self.root / 'b.txt'
        a.write_text('old a')
        b.write_text('old b')
        original = os.replace
        count = 0
        def fail_second(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('synthetic publication failure')
            return original(source, destination)
        with patch('tools.contracts.os.replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                publish(self.root, {'a.txt':'new a','b.txt':'new b'})
        self.assertEqual(a.read_text(),'old a')
        self.assertEqual(b.read_text(),'old b')
        self.assertFalse(list(self.root.glob('.build-stage-*')))

    def test_build_is_repeatable_and_sidecars_unchanged(self):
        before = {p.name:p.read_bytes() for p in (self.root/'knowledge').glob('*.json')}
        build_guide.build_guide(self.root)
        snapshot = self.snapshot()
        build_data.build_areas(self.root)
        build_data.build_data(self.root)
        build_guide.build_guide(self.root)
        self.assertEqual(snapshot, self.snapshot())
        self.assertEqual(before, {p.name:p.read_bytes() for p in (self.root/'knowledge').glob('*.json')})


if __name__ == '__main__':
    unittest.main()
