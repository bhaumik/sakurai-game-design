# Contributing to the contextual library

Start with the README, roadmap, and `docs/implementation-plan.md`. Keep inherited source statements, synthesis interpretations, and project hypotheses distinct. No change should make a rule sound more universal than its evidence supports.

## File ownership and rebuild inputs

`episodes/index.csv` is the inherited channel identity register. Published episode numbers are aliases, not identities to regenerate from current upload order. `episodes/transcripts/` contains retained raw OCR text. Do not silently clean it or replace it with guessed wording. Store corrections and source revisions explicitly in `knowledge/`.

`episodes/notes/` and `work/batches/batch-*.jsonl` are paired authored representations from the original extraction. Notes edits do not automatically update batches. A semantic correction must update or qualify both representations deliberately. The batch-range assignments in `work/batches/ranges.json` are the ownership boundary.

`work/parts/*-principles.jsonl`, techniques, lenses, quotes, and glossary are authored synthesis inputs. The skill's CSVs are generated from these inputs, so edits made only to a CSV will be lost. The area-stage JSONL files are generated batch projections, not the canonical synthesis result.

`study-guide/01` through `14-*.md` are authored narrative chapters. `tools/build_guide.py` generates checklists, glossary, episode index, and skill reference pages, not those chapters or episode notes. Review semantic chapter/data consistency during an edit rather than assuming a build does it.

`knowledge/catalogue.json`, `claims.json`, and `annotations.json` become reviewed source/provenance inputs after bootstrap. `segments.json` points into immutable retained files. Context exclusions and qualifier links are curated annotations with explicit basis. Update schema and consumers together if adding a field. Do not resnapshot source hashes simply to make validation pass after accidental text changes.

The search utility and existing skill belong to the retrieval worker. Contracts, validators, offline builders, and CI belong to the data worker. Acquisition tools and profiles belong to the optional-pipeline worker. One integration owner reviews shared exports, docs, and commits. Never let parallel agents publish the same aggregate file independently.

## Select the appropriate change path

For a synthesis-input edit, validate first, run `python3 tools/build_data.py data`, then `python3 tools/build_guide.py`. For a batch edit, run `python3 tools/build_data.py areas`; affected area synthesis and authored notes/chapters need explicit review before the data/guide stages. The areas stage does not perform new synthesis by itself.

For a prose-only change, cite the relevant source and record whether it alters meaning. If so, inspect the paired structured input and downstream narrative. For a provenance correction, preserve raw text, provide the independently verified replacement and locator, record review status, and update dependent claims without erasing history.

For a new source, add immutable author/work/document records and typed locators, then independently attributed claims and relationships. Existing item IDs must remain stable. A pending source has no findings until accessible material is read. Use the future-source fixtures to test schema support without pretending their synthetic text is a real book excerpt.

## Required gates

Run `python3 tools/validate.py` and `python3 -m unittest discover -s tests -v`. Check JSON and Markdown search for the affected use case. Test invalid inputs and the negative control, not only the happy path. If a builder changes, exercise it in a temporary copy and compare generated output before publishing.

Passing validation establishes structural integrity, not source accuracy or player benefit. Context rules are heuristic and deliberately conservative. New applicability judgments need a stated basis and source checks. Experiment records require actual observations before being marked complete.

## GitHub and rights boundaries

Push to this fork's `origin`, not `upstream`. Name `bhaumik/sakurai-game-design` explicitly in GitHub issue and pull-request commands: a clone can retain upstream as the GitHub CLI default. Preserve upstream attribution. Do not grant a permissive license over inherited code, analysis, or transcript text without authority. Do not add inaccessible book passages or redistribute participant data.
