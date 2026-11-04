"""Generate the study guide's derived pages and the skill's reference files from the CSV data.

usage: python build_guide.py

Writes:
  study-guide/checklists.md         review questions per area (lenses + principle questions)
  study-guide/glossary.md           Sakurai's terms
  study-guide/episode-index.md      every episode with its one-line lesson
  skills/sakurai-game-design/references/quick-reference.md   every principle, compact
  skills/sakurai-game-design/references/techniques.md        every technique, compact
"""
import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
try:
    from .contracts import ContractError, publish
    from .validate import preflight
except ImportError:
    from contracts import ContractError, publish
    from validate import preflight

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "skills" / "sakurai-game-design" / "data"
GUIDE = ROOT / "study-guide"
REFS = ROOT / "skills" / "sakurai-game-design" / "references"
AREAS = [  # (area, title, chapter file)
    ("essence", "Game essence", "02-game-essence.md"),
    ("balance", "Balance and difficulty", "03-balance-and-difficulty.md"),
    ("planning", "Planning, structure and pacing", "04-planning-and-structure.md"),
    ("feel", "Game feel", "05-game-feel.md"),
    ("animation", "Animation", "06-animation.md"),
    ("visuals", "Visuals, characters and effects", "07-visuals-and-effects.md"),
    ("audio", "Audio", "08-audio.md"),
    ("ui", "UI and clarity", "09-ui-and-clarity.md"),
    ("team", "Directing and teams", "10-directing-and-teams.md"),
    ("craft", "Work ethic and creativity", "11-work-ethic-and-creativity.md"),
    ("marketing", "Marketing and updates", "12-marketing-and-updates.md"),
    ("tech", "Tech and tools", "13-tech-and-tools.md"),
    ("case-study", "Case studies", "14-case-studies.md"),
]
EPS = {}
OUTPUTS = {}


def emit(path, content):
    OUTPUTS[path.relative_to(ROOT)] = content.rstrip("\n") + "\n"


def rows(name):
    path = DATA / f"{name}.csv"
    if not path.is_file():
        raise ContractError(f"{path}: required CSV is missing")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ep_links(field, base):
    out = []
    for e in str(field).replace(",", ";").split(";"):
        e = e.strip().lstrip("ep").strip()
        if not e:
            continue
        if not e.isdigit() or e not in EPS:
            raise ContractError(f"unknown episode reference {e!r}")
        target = ROOT / EPS[e]["transcript"].replace("/transcripts/", "/notes/")
        out.append(f"[{e}]({os.path.relpath(target, base)})")
    return ", ".join(out)


def by_area(items):
    d = defaultdict(list)
    for r in items:
        d[r.get("area", "")].append(r)
    return d


def checklists():
    lenses, principles = by_area(rows("lenses")), by_area(rows("principles"))
    md = ["# Checklists", "",
          "Review questions to ask of your own design or build, drawn from Sakurai's lenses and principles. "
          "Start with the pre-ship list, then use the area lists for the feature you're reviewing.", "",
          "## Pre-ship: the critical questions", "",
          "Every principle marked CRITICAL, phrased as a question. A \"no\" here is a problem players will feel.", ""]
    for area, title, _ in AREAS:
        for p in principles.get(area, []):
            if p["priority"] == "CRITICAL" and p.get("review_question"):
                md.append(f"- [ ] {p['review_question']} *({p['id']}; eps {ep_links(p['episodes'], GUIDE)})*")
    md.append("")
    for area, title, chapter in AREAS:
        if not lenses.get(area) and not principles.get(area):
            continue
        md += [f"## {title}", "", f"Chapter: [{chapter}]({chapter})", ""]
        for l in lenses.get(area, []):
            md.append(f"- [ ] **{l['lens']}** *({l['id']})*")
            if l.get("look_for"):
                md.append(f"  - Good: {l['look_for']}")
            if l.get("red_flags"):
                md.append(f"  - Red flags: {l['red_flags']}")
        extra = [p for p in principles.get(area, []) if p["priority"] in ("HIGH", "MEDIUM") and p.get("review_question")]
        if extra:
            md += ["", "More questions:", ""]
            md += [f"- [ ] {p['review_question']} *({p['id']})*" for p in extra]
        md.append("")
    emit(GUIDE / "checklists.md", "\n".join(md))


def glossary():
    md = ["# Glossary", "", "Sakurai's terms and coinages, as used in the series.", "",
          "| Term | Meaning | Episodes |", "|---|---|---|"]
    for g in rows("glossary"):
        md.append(f"| **{g['term']}** | {g['meaning']} | {ep_links(g['episodes'], GUIDE)} |")
    emit(GUIDE / "glossary.md", "\n".join(md))


def episode_index():
    eps = rows("episodes")
    md = ["# Episode index", "",
          f"All {len(eps)} episodes of *Masahiro Sakurai on Creating Games* in release order, with the one-line lesson of each. "
          "Links go to the study notes; each notes file links on to the full transcript and the video.", ""]
    cats = defaultdict(list)
    for e in eps:
        cats[e["category"]].append(e)
    md += ["## By category", ""]
    for cat in sorted(cats, key=lambda c: -len(cats[c])):
        links = ", ".join(f"[{e['ep']}](../{e['notes']})" for e in cats[cat])
        md.append(f"- **{cat}** ({len(cats[cat])}): {links}")
    md += ["", "## In release order", "", "| # | Episode | Category | Lesson |", "|---|---|---|---|"]
    for e in eps:
        lesson = e["summary"].replace("|", "/")
        md.append(f"| {e['ep']} | [{e['title']}](../{e['notes']}) | {e['category']} | {lesson} |")
    emit(GUIDE / "episode-index.md", "\n".join(md))


def quick_reference():
    principles = by_area(rows("principles"))
    md = ["# Quick reference: every principle", "",
          "Compact list of every principle by area, most important first. "
          "Use `scripts/search.py` to get full rows (why, anti-pattern, example, episodes).", ""]
    for area, title, chapter in AREAS:
        if not principles.get(area):
            continue
        md += [f"## {title} (`--area {area}`)", ""]
        for p in principles[area]:
            md.append(f"- **{p['id']}** [{p['priority']}] {p['principle']}: {p['how_to_apply']} *(eps {p['episodes']})*")
        md.append("")
    emit(REFS / "quick-reference.md", "\n".join(md))

    techniques = by_area(rows("techniques"))
    md = ["# Techniques", "", "Concrete, implementable recipes, with Sakurai's numbers where he gives them.", ""]
    for area, title, _ in AREAS:
        if not techniques.get(area):
            continue
        md += [f"## {title}", ""]
        for t in techniques[area]:
            md.append(f"### {t['id']} · {t['technique']}")
            for k in ("what", "how", "when", "pitfalls"):
                if t.get(k):
                    md.append(f"- **{k}:** {t[k]}")
            md.append(f"- **episodes:** {t['episodes']}")
            md.append("")
    emit(REFS / "techniques.md", "\n".join(md))


def build_guide(root=None):
    global ROOT, DATA, GUIDE, REFS, EPS, OUTPUTS
    ROOT = Path(root or Path(__file__).resolve().parent.parent).resolve()
    DATA = ROOT / "skills/sakurai-game-design/data"
    GUIDE = ROOT / "study-guide"
    REFS = ROOT / "skills/sakurai-game-design/references"
    preflight(ROOT, guide=True)
    with (ROOT / "episodes/index.csv").open(encoding="utf-8", newline="") as handle:
        EPS = {r["ep"]: r for r in csv.DictReader(handle)}
    for _, _, chapter in AREAS:
        if not (GUIDE / chapter).is_file():
            raise ContractError(f"{GUIDE / chapter}: required authored chapter is missing")
    OUTPUTS = {}
    checklists()
    glossary()
    episode_index()
    quick_reference()
    publish(ROOT, OUTPUTS)
    return dict(OUTPUTS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        build_guide(args.root)
    except (ContractError, OSError) as exc:
        parser.exit(1, f"Guide build failed before publication or was rolled back: {exc}\n")
    print("generated checklists, glossary, episode index, quick reference, techniques")


if __name__ == "__main__":
    main()
