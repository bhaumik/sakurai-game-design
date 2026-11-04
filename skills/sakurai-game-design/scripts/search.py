#!/usr/bin/env python3
"""Dependency-free, attributed retrieval of local game-design evidence.

  search.py "hits feel weak" --context examples/context-sword.json --json
  search.py --review "dialogue pacing" --area ui --context examples/context-cozy.json
  search.py "hitstop" --domain quotes --source sakurai
  search.py --episode 47 --source sakurai

BM25 scores are meaningful within a dataset, not calibrated across datasets.
Applicability is a conservative scope check, not a claim of universal design fit.
See docs/search-contract.md for the JSON contract and failure semantics.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from evidence import DataError, EvidenceStore, episode_numbers

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_DIR / "data"
REPO_ROOT = SKILL_DIR.parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DOMAINS = {
    "principles": ("principles.csv", "principle", ["id", "area", "priority", "why", "how_to_apply", "anti_pattern", "example", "review_question", "episodes", "keywords"]),
    "techniques": ("techniques.csv", "technique", ["id", "area", "what", "how", "when", "pitfalls", "episodes", "keywords"]),
    "lenses": ("lenses.csv", "lens", ["id", "area", "look_for", "red_flags", "principles", "episodes", "keywords"]),
    "episodes": ("episodes.csv", "title", ["ep", "category", "summary", "takeaways", "games", "tags", "notes", "url"]),
    "quotes": ("quotes.csv", "quote", ["ep", "title", "time", "theme"]),
    "glossary": ("glossary.csv", "term", ["meaning", "episodes"]),
}
DEFAULT_MIX = ["principles", "techniques", "lenses"]
AREAS = ("essence", "balance", "planning", "feel", "animation", "visuals", "audio", "ui", "team", "craft", "marketing", "tech", "case-study")
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
APPLICABILITY_ORDER = {"applicable": 0, "needs_context": 1, "not_applicable": 2}
MIN_RELATIVE = 0.25
AREA_BOOST = 1.4
AREA_HINTS = {
    "essence": "risk reward fun core loop enemy boss strategy combat shooter puzzle competitive",
    "balance": "difficulty difficult hard easy beginner novice casual audience expert balance stuck fair handicap boss",
    "planning": "concept pacing tutorial onboarding cutscene story narrative dialogue structure level reward scope prototype jam proposal cozy",
    "feel": "feel weak hitstop hit stop shake impact jump responsive lag input camera controls dash cancel knockback weight floaty aerial air sword",
    "animation": "animation pose windup lead follow-through attack swing frames",
    "visuals": "effect particles explosion flash color readability readable silhouette art character lighting fireball projectile",
    "audio": "sound music audio sfx mix voice reverb",
    "ui": "menu hud ui text font icon button remap skip pause loading dialogue",
    "team": "team director feedback review meeting playtest decision",
    "craft": "motivation idea career habit health",
    "marketing": "trailer marketing reveal demo update patch",
    "tech": "debug parameter tuning frame rate fps build bug hardware optimization",
}
STOP = set("a an and are as at be but by for from has have how i if in into is it its of on or so that the their them then there these this to was what when where which who will with you your game games no not without".split())
SYNONYMS = {"novice": "beginner", "newcomer": "beginner", "hitstop": "hitstop"}
CONTEXT_FIELDS = {"audience", "genre", "mechanics", "excluded_mechanics", "desired_tension", "core_appeal", "platform", "input", "stage"}
KNOWN_AUTHORS = {
    "raph koster": "Raph Koster", "koster": "Raph Koster", "katherine isbister": "Katherine Isbister", "isbister": "Katherine Isbister",
    "jesse schell": "Jesse Schell", "schell": "Jesse Schell", "chris crawford": "Chris Crawford", "crawford": "Chris Crawford",
    "masahiro sakurai": "Masahiro Sakurai", "sakurai": "Masahiro Sakurai",
}
GAPS = {"input buffering": "The indexed Sakurai material does not document input buffering.", "coyote time": "The indexed Sakurai material does not document coyote time."}
DEFAULT_GROUPS = {"UI-01": "player-controlled-noninteractive-time", "PLAN-21": "player-controlled-noninteractive-time", "BAL-01": "audience-relative-risk", "CASE-01": "audience-relative-risk"}


def stem(token):
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[:-len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def tokenize(text):
    text = re.sub(r"\bhit[ -]+stop\b", "hitstop", str(text).lower())
    return [SYNONYMS.get(stem(t), stem(t)) for t in re.findall(r"[a-z0-9]+", text.replace("-", " ")) if t not in STOP]


def design_tokens(text):
    text = re.sub(r"\b[A-Z]{2,8}-(?:T|L)?\d{2,3}\b", " ", str(text), flags=re.I)
    text = re.sub(r"https?://\S+|\bepisodes/(?:notes|transcripts)/\S+|\bep(?:isode)?\s+\d+\b", " ", text, flags=re.I)
    return tokenize(text)


def explicit_exclusions(text):
    """Only explicit negation, never 'cozy' alone, establishes exclusions."""
    patterns = {
        "combat": r"\b(?:no|without|non)[ -]+combat\b|\bnon[ -]?fighting\b|\bno fighting\b",
        "time_pressure": r"\b(?:no|without)[ -]+(?:time[ -]+pressure|timer(?:s)?|time[ -]+limit(?:s)?)\b",
    }
    excluded = set()
    positive = text
    for tag, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            excluded.add(tag)
            positive = re.sub(pattern, " ", positive, flags=re.I)
    return positive, excluded


def hinted_areas(query):
    positive, _ = explicit_exclusions(query)
    tokens = set(tokenize(positive))
    return {area for area, words in AREA_HINTS.items() if tokens & set(tokenize(words))}


def load(domain):
    path = DATA_DIR / DOMAINS[domain][0]
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, strict=True)
            required = {DOMAINS[domain][1], *DOMAINS[domain][2]}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise DataError(f"{path}: missing required CSV columns")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DataError(f"cannot read {path}: {exc}") from exc
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise DataError(f"{path}: empty or malformed CSV")
    if domain == "quotes":
        dedup = {}
        for row in rows:
            key = (" ".join(row["quote"].casefold().split()), row["ep"], row["time"])
            if key not in dedup:
                dedup[key] = {**row, "themes": [row["theme"]], "duplicate_count": 1}
            else:
                merged = dedup[key]
                merged["duplicate_count"] += 1
                if row["theme"] not in merged["themes"]:
                    merged["themes"].append(row["theme"])
                    merged["theme"] += "; " + row["theme"]
        rows = list(dedup.values())
    return rows


class BM25:
    def __init__(self, docs, k1=1.4, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.avg = sum(map(len, docs)) / max(len(docs), 1) or 1
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(d) for d in docs]

    def score(self, query):
        tokens = set(tokenize(query))
        return [sum(self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * len(self.docs[i]) / self.avg)) for t in tokens if t in tf) for i, tf in enumerate(self.tf)]


def weighted_fields(domain):
    title = DOMAINS[domain][1]
    roles = {title: 5.0}
    if domain in DEFAULT_MIX:
        roles["keywords"] = 3.0
    for field in {"why", "how_to_apply", "review_question", "what", "how", "look_for", "summary", "takeaways", "meaning"} & set(DOMAINS[domain][2]):
        roles[field] = 1.0
    for field in {"when", "games", "tags", "theme"} & set(DOMAINS[domain][2]):
        roles[field] = 1.5
    for field in {"anti_pattern", "pitfalls", "red_flags"} & set(DOMAINS[domain][2]):
        roles[field] = 0.25
    if "example" in DOMAINS[domain][2]:
        roles["example"] = 0.35
    return roles


def context_values(context, field):
    value = context.get(field, [])
    return value if isinstance(value, list) else [value]


def scope_tags(text):
    """Recognize narrow scope vocabulary, not semantic universal suitability."""
    tags = set()
    if re.search(r"\b(combat|fight(?:ing)?|sword|attack|hitstop|hits?|impact)\b", text, re.I):
        tags.add("combat")
    if re.search(r"\b(fighting|reversal|shoryuken|anti.air)\b", text, re.I):
        tags.add("fighting")
    for tag, pattern in {"impact": r"\b(hitstop|hit.stop|hits?|impact|sword)\b", "reversal": r"\breversal\b", "anti_air": r"\banti.air\b", "knockback": r"\bknockback|launching\b", "challenge": r"\bchallenge|difficult|difficulty\b", "risk_reward": r"\brisk|reward\b", "competitive": r"\bcompetitive\b", "novice": r"\bnovice\b", "casual": r"\bcasual\b"}.items():
        if re.search(pattern, text, re.I):
            tags.add(tag)
    if re.search(r"\b(action|combat|sword|shooter)\b", text, re.I):
        tags.add("action")
    if re.search(r"\b(time.pressure|timer|timed|countdown)\b", text, re.I):
        tags.add("time_pressure")
    if re.search(r"\b(hitstop|hit.stop)\b", text, re.I):
        tags.add("hitstop")
    if re.search(r"\b(beginner|novice|newcomer|casual)\b", text, re.I):
        tags.add("beginner")
    if re.search(r"\b(story|narrative|dialogue|cutscene)\b", text, re.I):
        tags.add("narrative")
    return tags


def evaluate_scope(row, annotation, query, context):
    positive_query, excluded = explicit_exclusions(query)
    positive_context = []
    for field in CONTEXT_FIELDS - {"excluded_mechanics"}:
        for value in context_values(context, field):
            cleaned, inferred = explicit_exclusions(value)
            positive_context.append(cleaned)
            excluded |= inferred
    for value in context_values(context, "excluded_mechanics"):
        excluded.add(value.lower().replace(" ", "_"))
        excluded |= scope_tags(value)
    positive = " ".join([positive_query, *positive_context])
    tags = scope_tags(positive)
    if "combat" in excluded:
        excluded |= {"fighting", "hitstop"}
        tags.add("no_combat")
    if "time_pressure" in excluded or "no_pressure" in excluded:
        tags.add("no_pressure")
    if "challenge" in excluded or "no_challenge" in excluded:
        tags.add("no_challenge")
    if "no_combat" in excluded:
        tags.add("no_combat")
        excluded |= {"combat", "fighting", "hitstop"}
    tags -= excluded - {"no_combat", "no_pressure", "no_challenge"}
    conditions = annotation.get("conditions", {})
    requires = list(conditions.get("requires_any", []))
    excludes = list(conditions.get("excludes_any", []))
    basis = annotation.get("applicability_basis", "Uncurated scope check; not verified as source-grounded.")
    # Existing technique conditions are preserved and conservatively recognized.
    when = row.get("when", "")
    fallback = None
    if not requires and re.search(r"fighting games|reversal|anti-air", when, re.I):
        fallback = "fighting"
    elif not requires and re.search(r"action games", when, re.I):
        fallback = "action"
    elif not requires and re.search(r"sword|strong hits|hit stop|hitstop", when, re.I):
        fallback = "combat"
    if fallback:
        requires = [fallback]
        basis = "Conservative interpretation of the retained technique 'when' field."

    def matches(condition):
        raw = condition.lower().strip()
        field, separator, value = raw.partition(":")
        if not separator:
            field, separator, value = raw.partition("=")
        if separator and field in CONTEXT_FIELDS:
            tokens = set(tokenize(" ".join(context_values(context, field))))
            wanted = set(tokenize(value))
            return bool(wanted) and wanted <= tokens
        tag = raw.replace(" ", "_")
        if tag.startswith("no_"):
            return tag in tags
        return tag in tags or (bool(tokenize(raw)) and set(tokenize(raw)) <= set(tokenize(positive)))

    blocked = [condition for condition in requires if condition.lower().replace(" ", "_") in excluded]
    triggered = [condition for condition in excludes if matches(condition)]
    satisfied = [condition for condition in requires if matches(condition)]
    info = {"conditions": {"requires_any": requires, "excludes_any": excludes}, "basis": basis, "excluded_tags": sorted(excluded), "matched_conditions": satisfied}
    if triggered or (requires and len(blocked) == len(requires)):
        return {**info, "status": "not_applicable", "reason": "Explicit context conflicts with scope: " + ", ".join(triggered or blocked), "question": None, "mandatory_change": False}
    if requires and satisfied:
        return {**info, "status": "applicable", "reason": "Stated scope is present: " + ", ".join(satisfied) + ". This does not prove effectiveness for the project.", "question": None, "mandatory_change": False}
    missing = ", ".join(requires) if requires else (when or "the target player, active mechanic and intended experience")
    return {**info, "status": "needs_context", "reason": "Lexical relevance alone does not establish applicability.", "question": "Does the project satisfy " + missing + "?", "mandatory_change": False}


def item_id(domain, row):
    if row.get("id"):
        return row["id"]
    if domain == "episodes":
        return "episode:" + row["ep"]
    if domain == "quotes":
        normalized = " ".join(row["quote"].casefold().split()) + "|" + row["ep"] + "|" + row["time"]
        return "quote:" + hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return "glossary:" + re.sub(r"[^a-z0-9]+", "-", row["term"].lower()).strip("-")


def search(domain, query, n, area=None, context=None, store=None, source_id="sakurai:creating-games", review=False):
    store = store or EvidenceStore(KNOWLEDGE_DIR, REPO_ROOT)
    context = context or {}
    rows = load(domain)
    if area:
        if domain not in DEFAULT_MIX:
            raise ValueError(f"--area is not supported for {domain}; search an area-bearing dataset instead")
        rows = [r for r in rows if r["area"] == area]
    # Legacy CSV records belong to Sakurai; adding a catalogue source does not
    # manufacture another author's authored item records.
    rows = [r for r in rows if r.get("source_id", "sakurai:creating-games") == source_id]
    positive, _ = explicit_exclusions(query)
    query_tokens = set(tokenize(positive))
    totals = [0.0] * len(rows)
    field_matches = [{} for _ in rows]
    for field, weight in weighted_fields(domain).items():
        docs = [design_tokens(row.get(field, "")) for row in rows]
        scores = BM25(docs).score(positive)
        for index, score in enumerate(scores):
            totals[index] += score * weight
            matched = query_tokens & set(docs[index])
            if matched:
                field_matches[index][field] = {"tokens": sorted(matched), "weight": weight, "score": round(score * weight, 6)}
    hints = hinted_areas(positive)
    results = []
    for row, score, fields in zip(rows, totals, field_matches):
        if score <= 0:
            continue
        boost = AREA_BOOST if row.get("area") in hints else 1.0
        score *= boost
        identifier = item_id(domain, row)
        annotation = store.annotations.get(identifier, {})
        applicability = evaluate_scope(row, annotation, query, context)
        sources, claims = store.joins(row, identifier, source_id)
        if domain == "episodes" and sources:
            identifier = sources[0]["document_id"]
        result = {
            "id": identifier, "title": row[DOMAINS[domain][1]], "domain": domain,
            "score": round(score, 6), "area": row.get("area"), "priority": row.get("priority"),
            "source_id": source_id, "author": store.sources[source_id]["author"],
            "matched_fields": fields, "matched_tokens": sorted({t for match in fields.values() for t in match["tokens"]}),
            "area_boost": boost, "applicability": applicability, "status": applicability["status"],
            "evidence_type": "retained_quote_unverified" if domain == "quotes" else "indexed_synthesis",
            "sources": sources, "claims": claims,
            "claim_locator_status": "available" if claims else "unavailable",
            "qualifiers": annotation.get("related", []), "concept_group": annotation.get("concept_group", DEFAULT_GROUPS.get(identifier)),
            "record": row,
        }
        results.append(result)
    top = max((r["score"] for r in results), default=0)
    results = [r for r in results if r["score"] >= top * MIN_RELATIVE]
    if review:
        results.sort(key=lambda r: (APPLICABILITY_ORDER[r["status"]], PRIORITY_ORDER.get(r["priority"], 9) if r["status"] == "applicable" else 9, -r["score"]))
    else:
        results.sort(key=lambda r: (-r["score"], PRIORITY_ORDER.get(r["priority"], 9)))
    for rank, result in enumerate(results[:n], 1):
        result["rank"] = rank
    return results[:n]


def groups_for(results, store, source_id, area=None):
    groups = {}
    all_principles = {row["id"]: row for row in load("principles")}
    for result in results.get("principles", []):
        group = result.get("concept_group")
        if not group:
            continue
        members = [key for key, value in DEFAULT_GROUPS.items() if value == group]
        members += [key for key, annotation in store.annotations.items() if annotation.get("concept_group") == group]
        records = []
        for identifier in dict.fromkeys(members + [result["id"]]):
            row = all_principles.get(identifier)
            if row and (not area or row["area"] == area):
                sources, claims = store.joins(row, identifier, source_id)
                records.append({"id": identifier, "title": row["principle"], "area": row["area"], "how_to_apply": row["how_to_apply"], "conditions": store.annotations.get(identifier, {}).get("conditions", {}), "sources": sources, "claims": claims})
        groups[group] = {"concept_group": group, "count_as_independent_confirmations": False, "members": records}
    return list(groups.values())


def source_issue(query, selector, store):
    source_id = store.source_for_query(selector)
    if not source_id or store.sources[source_id]["status"] != "available" or not any(d["source_id"] == source_id for d in store.documents.values()):
        return None, "source_mismatch", f"No imported material is available for source {selector!r}."
    requested = {name for alias, name in KNOWN_AUTHORS.items() if re.search(r"\b" + re.escape(alias) + r"\b", query, re.I)}
    available_author = store.sources[source_id]["author"]
    if requested and requested != {available_author}:
        return source_id, "source_mismatch", "Requested author(s) " + ", ".join(sorted(requested)) + f" are not covered by the selected {available_author} corpus."
    return source_id, None, None


def build_response(query, domains, n, area, context, selector, review, store):
    source_id, issue, message = source_issue(query, selector, store)
    positive, inferred = explicit_exclusions(query)
    response = {
        "schema_version": "1.0", "mode": "review" if review else "search", "query": query,
        "filters": {"domains": domains, "area": area, "source": selector, "source_id": source_id, "limit_per_domain": n},
        "context": context, "inferred_exclusions": sorted(inferred), "hinted_areas": sorted(hinted_areas(positive)),
        "status": issue or "no_match", "messages": [message] if message else [], "results": {},
        "unsupported_terms": [], "concern_groups": [],
    }
    if issue:
        return response
    gaps = [message for topic, message in GAPS.items() if topic in query.lower().replace("-", " ")]
    if gaps:
        response["status"] = "unsupported_topic"
        response["messages"] = gaps + ["Do not substitute generic lag or control advice for this technical specification."]
        return response
    response["results"] = {domain: search(domain, query, n, area, context, store, source_id, review) for domain in domains}
    rows = [row for matches in response["results"].values() for row in matches]
    matched = {token for row in rows for token in row["matched_tokens"]}
    response["unsupported_terms"] = sorted(set(tokenize(positive)) - matched)
    if rows:
        response["status"] = "partial_match" if response["unsupported_terms"] else "ok"
        response["messages"].append("Lexical retrieval is not proof of source accuracy or project fit. Scores are comparable only within a domain.")
    else:
        response["messages"].append("No lexical matches. Retry once within the original intent; no universal fallback is supplied.")
    if review:
        response["concern_groups"] = groups_for(response["results"], store, source_id, area)
        response["messages"].append("Evaluate applicable findings first. Conditional and skipped findings carry no required change; static priority cannot override scope.")
    return response


def render(response):
    print(f"# Attributed game-design {response['mode']}: {response.get('query', '')}\n")
    print(f"**Status:** {response['status']}")
    for message in response.get("messages", []):
        print(f"\n{message}")
    if response.get("unsupported_terms"):
        print("\n**Unmatched normalized query terms:** " + ", ".join(response["unsupported_terms"]))
    emitted_groups = set()
    for domain, results in response.get("results", {}).items():
        print(f"\n## {domain} ({len(results)} matches)")
        for result in results:
            group = result.get("concept_group")
            first_in_group = group not in emitted_groups
            if response["mode"] == "review" and group in emitted_groups:
                print(f"\n- {result['id']} belongs to the concern **{group}** above; not independent confirmation.")
            if group:
                emitted_groups.add(group)
            print(f"\n### {result['id']}: {result['title']}")
            print(f"\n**Score:** {result['score']:.3f} | **Applicability:** {result['status']} | **Source:** {result['author']} ({result['source_id']})")
            print("\n" + result["applicability"]["reason"])
            if result["applicability"]["question"]:
                print("\n**Context question:** " + result["applicability"]["question"])
            print("\n**Matched fields:** " + "; ".join(f"{field} [{', '.join(value['tokens'])}] (weight {value['weight']})" for field, value in result["matched_fields"].items()))
            for field in DOMAINS[domain][2]:
                if field in {"id", "episodes", "keywords", "notes", "url"} or not result["record"].get(field):
                    continue
                print(f"- **{field}:** {result['record'][field]}")
            print(f"- **Claim-level locators:** {result['claim_locator_status']}")
            for source in result["sources"]:
                print(f"- **Document:** [{source['title']}]({source.get('time_url', source['url'])}) ({source['document_id']}; {source['review_status']})")
                if source.get("notes_path"):
                    print(f"  - Notes: {source['notes_path']}; transcript: {source.get('transcript_path')}")
            for claim in result["claims"]:
                print(f"- **Claim {claim['claim_id']} ({claim['claim_type']}, {claim['review_status']}):** {claim['text']}")
                if claim.get("limitations"):
                    print("  - Limitations: " + str(claim["limitations"]))
                if claim.get("context"):
                    print("  - Context: " + json.dumps(claim["context"], ensure_ascii=False))
                for evidence in claim["evidence"]:
                    print("  - Evidence: " + evidence["document_id"] + " " + json.dumps(evidence["locator"], ensure_ascii=False))
                    print("  - Source: " + evidence["document"].get("time_url", evidence["document"]["url"]))
            for qualifier in result["qualifiers"]:
                print(f"- **Qualifier link:** {qualifier['relation']} -> {qualifier['item_id']}")
            if group and first_in_group and response["mode"] == "review":
                for concern in response["concern_groups"]:
                    if concern["concept_group"] == group:
                        print(f"\n**Grouped concern:** {group}; count once, preserve conditions.")
                        for member in concern["members"]:
                            print(f"- **{member['id']}:** {member['how_to_apply']}")
    if response.get("content") is not None:
        print("\n" + response["content"])
    if response.get("areas"):
        for area, count in response["areas"].items():
            print(f"- {area}: {count} principles")


def load_context(path):
    if not path:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read --context {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) - CONTEXT_FIELDS:
        raise ValueError("--context must be an object using only " + ", ".join(sorted(CONTEXT_FIELDS)))
    for field, content in value.items():
        if not isinstance(content, (str, list)) or isinstance(content, list) and any(not isinstance(x, str) or not x.strip() for x in content):
            raise ValueError(f"--context {field} must be a string or array of nonempty strings")
        if isinstance(content, str) and not content.strip():
            raise ValueError(f"--context {field} must not be empty")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--domain", choices=list(DOMAINS), help="search exactly one dataset, also honored by review")
    parser.add_argument("--area", choices=AREAS, help="filter principles, techniques and lenses only")
    parser.add_argument("-n", type=int, default=5, help="positive displayed limit per dataset, including review")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--review", metavar="DESIGN")
    modes.add_argument("--episode", type=int)
    modes.add_argument("--transcript", type=int)
    modes.add_argument("--areas", action="store_true")
    parser.add_argument("--context", metavar="JSON_FILE", help="project brief using the documented context keys")
    parser.add_argument("--source", default="sakurai:creating-games", help="source ID or known catalogue author alias")
    parser.add_argument("--json", action="store_true", help="emit JSON contract version 1.0")
    args = parser.parse_args(argv)
    if args.n <= 0:
        parser.error("-n must be a positive integer")
    special = args.review is not None or args.episode is not None or args.transcript is not None or args.areas
    if args.query is not None and special:
        parser.error("positional query cannot be combined with a mode option")
    if args.review is not None and not args.review.strip() or args.query is not None and not args.query.strip():
        parser.error("query/review text must not be empty")
    if args.episode is not None and args.episode <= 0 or args.transcript is not None and args.transcript <= 0:
        parser.error("episode/transcript number must be positive")
    if (args.episode is not None or args.transcript is not None or args.areas) and (args.domain or args.area or args.context or args.n != 5):
        parser.error("document/areas modes do not accept domain, area, context or a custom limit")
    if args.area and args.domain and args.domain not in DEFAULT_MIX:
        parser.error(f"--area is not supported with --domain {args.domain}")
    if not special and args.query is None:
        parser.error("provide a query or one mode option")
    try:
        context = load_context(args.context)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        store = EvidenceStore(KNOWLEDGE_DIR, REPO_ROOT)
        if args.episode is not None or args.transcript is not None:
            number = args.episode if args.episode is not None else args.transcript
            kind = "notes" if args.episode is not None else "transcript"
            source_id, issue, message = source_issue("", args.source, store)
            response = {"schema_version": "1.0", "mode": kind, "query": "", "status": issue or "ok", "filters": {"source": args.source, "source_id": source_id}, "messages": [message] if message else [], "results": {}}
            if not issue:
                documents = [d for d in store.by_episode.get(number, []) if d["source_id"] == source_id]
                if not documents:
                    raise ValueError(f"episode {number} not found")
                document = documents[0]
                relative = document.get("notes_path" if kind == "notes" else "transcript_path")
                if not relative or not (REPO_ROOT / relative).is_file():
                    raise DataError(f"episode {number}: required {kind} file missing")
                response["content"] = (REPO_ROOT / relative).read_text(encoding="utf-8")
                response["sources"] = [store.resolve_document(document)]
        elif args.areas:
            source_id, issue, message = source_issue("", args.source, store)
            response = {"schema_version": "1.0", "mode": "areas", "query": "", "status": issue or "ok", "filters": {"source": args.source, "source_id": source_id}, "messages": [message] if message else [], "results": {}}
            if not issue:
                response["areas"] = dict(Counter(r["area"] for r in load("principles") if r.get("source_id", "sakurai:creating-games") == source_id))
        else:
            query = args.review if args.review is not None else args.query
            domains = [args.domain] if args.domain else DEFAULT_MIX
            response = build_response(query, domains, args.n, args.area, context, args.source, args.review is not None, store)
    except DataError as exc:
        if args.json:
            print(json.dumps({"schema_version": "1.0", "status": "data_error", "error": str(exc)}))
        else:
            print(f"data error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        parser.exit(1, f"error: {exc}\n")
    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        render(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
