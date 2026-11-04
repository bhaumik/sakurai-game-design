# Repository guidance for agents

Use this repository as attributed evidence, not a universal game-design rulebook. Read `README.md`, `ROADMAP.md`, and `CONTRIBUTING.md` before changes. Ask for or preserve the game's audience, core appeal, active mechanics, exclusions, intended tension, platform/input constraints, and development stage.

## Evidence discipline

Keep source statements, source examples, author synthesis, and application hypotheses separate. `retained_text_checked` does not mean audiovisually verified. Raw OCR defects are unresolved until source review establishes a correction. Do not invent quotes, hitstop durations, shake amplitudes, book takeaways, or test results. Conditions and tension relations are curator interpretations unless explicitly source-grounded.

Open the cited source before attributing an implementation detail. Respect unavailable-source and unsupported-topic responses. A lexical hit or a high priority does not establish applicability. Skip irrelevant advice with a reason instead of manufacturing a change to the game's premise.

## Work boundaries

Assign disjoint file ownership before parallel work. Follow the authored/generated boundaries in `CONTRIBUTING.md`. One integration owner publishes shared outputs. Do not edit only a generated CSV, renumber identities, or overwrite raw source text. Do not install the agent skill into a user's account unless requested.

## Validation and publishing

Run `python3 tools/validate.py` and `python3 -m unittest discover -s tests -v`. Run affected CLI examples and negative controls. Check source/evidence quality separately from structural validation. Update the roadmap and docs when behavior changes.

Target `bhaumik/sakurai-game-design` explicitly for GitHub operations and push only to the fork's origin. Do not publish to flossbud's upstream or change repository visibility/licenses without authorization. Preserve the upstream creator's attribution.
