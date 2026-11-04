import csv
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('catalogue_builder', ROOT / 'tools/build_catalogue.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class CatalogueIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'episodes').mkdir()
        with (ROOT / 'episodes/index.csv').open(newline='') as f:
            reader = csv.DictReader(f)
            self.fields = reader.fieldnames
            self.rows = list(reader)[:4]
        for row in self.rows:
            for rel in [row['transcript'], row['transcript'].replace('/transcripts/', '/notes/')]:
                out = self.root / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, out)
        self.write_index(self.rows[:3])
        BUILDER.build(self.root)
        self.original = self.catalogue()

    def tearDown(self):
        self.temp.cleanup()

    def write_index(self, rows):
        with (self.root / 'episodes/index.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(rows)

    def catalogue(self):
        data = json.loads((self.root / 'knowledge/catalogue.json').read_text())
        return {d['document_id']:d for d in data['documents']}

    def test_reordering_preserves_id_alias_and_paths(self):
        self.write_index(list(reversed(self.rows[:3])))
        BUILDER.build(self.root)
        self.assertEqual(self.original, self.catalogue())

    def test_title_change_preserves_published_paths(self):
        self.rows[0]['title'] = 'Updated display title'
        self.write_index(self.rows[:3])
        BUILDER.build(self.root)
        doc_id = 'youtube:' + self.rows[0]['video_id']
        old, new = self.original[doc_id], self.catalogue()[doc_id]
        self.assertEqual(new['title'], 'Updated display title')
        for key in ['episode', 'notes_path', 'transcript_path']:
            self.assertEqual(old[key], new[key])

    def test_addition_does_not_renumber_existing_documents(self):
        self.write_index([self.rows[3], *self.rows[:3]])
        BUILDER.build(self.root)
        current = self.catalogue()
        self.assertEqual(len(current), 4)
        for doc_id, doc in self.original.items():
            self.assertEqual(current[doc_id], doc)

    def test_changed_alias_rejected_before_publication(self):
        self.rows[0]['ep'] = '999'
        self.write_index(self.rows[:3])
        with self.assertRaisesRegex(ValueError, 'published episode changed'):
            BUILDER.build(self.root)
        self.assertEqual(self.original, self.catalogue())

    def test_retained_text_revision_requires_explicit_review(self):
        path = self.root / self.rows[0]['transcript']
        path.write_text(path.read_text() + '\nChanged evidence.\n')
        with self.assertRaisesRegex(ValueError, 'retained transcript changed'):
            BUILDER.build(self.root)
        self.assertEqual(self.original, self.catalogue())

    def test_snapshot_does_not_modify_raw_transcripts(self):
        before = {r['transcript']:(self.root / r['transcript']).read_bytes() for r in self.rows[:3]}
        BUILDER.build(self.root)
        self.assertEqual(before, {p:(self.root / p).read_bytes() for p in before})


if __name__ == '__main__':
    unittest.main()
