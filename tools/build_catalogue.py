#!/usr/bin/env python3
"""Snapshot immutable source IDs and retained transcript locators, without rewriting text.

Run once for the inherited corpus, then review updates to the resulting catalog.
Existing episode aliases and source paths are authoritative and never regenerated
from a live listing. Hashes describe retained files, not original videos/OCR assets.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAGRAPH = re.compile(r'^\[(\d+):(\d+)\]\(https?://[^)]+\)\s*(.*)$')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(root):
    target = root / 'knowledge'
    target.mkdir(exist_ok=True)
    old_path = target / 'catalogue.json'
    previous = json.loads(old_path.read_text()) if old_path.exists() else {}
    old = {d['document_id']: d for d in previous.get('documents', [])}
    documents, segments = [], []
    with (root / 'episodes/index.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        doc_id = 'youtube:' + row['video_id']
        text_path = root / row['transcript']
        data = text_path.read_bytes()
        document = {
            'document_id': doc_id, 'source_id': 'sakurai:creating-games',
            'episode': int(row['ep']), 'title': row['title'], 'url': row['url'],
            'video_id': row['video_id'], 'duration_seconds': int(float(row['duration_s'])),
            'notes_path': row['transcript'].replace('/transcripts/', '/notes/'),
            'transcript_path': row['transcript'], 'language': 'en',
            'translation_layer': 'official English on-screen subtitles, captured through third-party OCR',
            'review_status': 'unreviewed_ocr', 'transcript_sha256': sha(data),
            'provenance': 'Inherited retained transcript. Original OCR JSON and video asset hashes were not supplied.'
        }
        if doc_id in old:
            for key in ('episode', 'notes_path', 'transcript_path'):
                if old[doc_id].get(key) != document[key]:
                    raise ValueError(f'{doc_id}: published {key} changed; migrate explicitly')
            if old[doc_id]['transcript_sha256'] != document['transcript_sha256']:
                raise ValueError(f'{doc_id}: retained transcript changed; review source revision before resnapshotting')
        documents.append(document)
        starts, seen = [], set()
        for lineno, line in enumerate(data.decode('utf-8').splitlines(), 1):
            match = PARAGRAPH.match(line)
            if not match:
                continue
            seconds = int(match[1]) * 60 + int(match[2])
            segment_id = f'{doc_id}:t{seconds:06d}'
            if segment_id in seen:
                raise ValueError(f'{doc_id}: duplicate timestamp at line {lineno}')
            seen.add(segment_id)
            starts.append({
                'segment_id': segment_id, 'document_id': doc_id,
                'start_seconds': seconds, 'transcript_path': row['transcript'],
                'line_start': lineno, 'text_sha256': sha(match[3].encode('utf-8')),
                'review_status': 'unreviewed_ocr',
                'suspect': (int(row['ep']), seconds) in {(3, 24), (3, 98), (4, 249), (4, 256), (4, 282), (6, 412), (6, 562)},
            })
        for i, segment in enumerate(starts):
            segment['next_start_seconds'] = starts[i+1]['start_seconds'] if i+1 < len(starts) else document['duration_seconds']
        segments.extend(starts)
    missing = set(old) - {d['document_id'] for d in documents}
    if missing:
        raise ValueError(f'Published documents missing from inherited index: {sorted(missing)}')
    sources = [
        {'source_id': 'sakurai:creating-games', 'author': 'Masahiro Sakurai',
         'work': 'Masahiro Sakurai on Creating Games', 'kind': 'video_series', 'language': 'en',
         'status': 'available', 'url': 'https://www.youtube.com/@sora_sakurai_en/videos',
         'source_family': 'sakurai:creating-games', 'rights': 'Inherited materials, no new license granted.'},
        {'source_id': 'isbister:how-games-move-us', 'author': 'Katherine Isbister',
         'work': 'How Games Move Us: Emotion by Design', 'kind': 'book', 'language': 'en',
         'status': 'pending', 'url': 'https://direct.mit.edu/books/book/3115/How-Games-Move-UsEmotion-by-Design',
         'source_family': 'isbister:how-games-move-us',
         'rights': 'No chapter text or takeaways imported. Requires an accessible copy or supplied excerpts.'}
    ]
    if previous.get('sources'):
        sources = previous['sources']
    payloads = {
        'catalogue.json': {'schema_version': '1.0', 'sources': sources, 'documents': documents},
        'segments.json': {'schema_version': '1.0', 'provenance': 'Pointers into immutable inherited OCR transcripts, not recovered original OCR segments. next_start_seconds is a reading boundary, not an exact subtitle end.', 'segments': segments}
    }
    for name, payload in payloads.items():
        temporary = target / (name + '.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target / name)
    return len(documents), len(segments)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    args = ap.parse_args()
    try:
        docs, segs = build(args.root.resolve())
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        ap.exit(1, f'catalogue error: {exc}\n')
    print(f'{docs} stable documents, {segs} retained-paragraph pointers; source text unchanged')


if __name__ == '__main__':
    main()
