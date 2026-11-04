"""Read-only dependency-free structural validation of the complete repository."""
import argparse
import json
import sys
from pathlib import Path

try:
    from .contracts import Report, validate_legacy
    from .knowledge_validation import validate_knowledge
except ImportError:
    from contracts import Report, validate_legacy
    from knowledge_validation import validate_knowledge


def validate(root, *, check_outputs=True, compare_outputs=True, require_knowledge=True):
    root = Path(root).resolve()
    report = Report()
    legacy = validate_legacy(root, report, check_outputs, compare_outputs)
    validate_knowledge(root, legacy, report, require_knowledge)
    return report


def preflight(root, *, guide=False):
    report = validate(root, check_outputs=guide, compare_outputs=False)
    report.require()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--json", action="store_true", help="emit machine-readable diagnostics")
    args = parser.parse_args(argv)
    report = validate(args.root)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        for level, messages in (("ERROR", report.errors), ("WARNING", report.warnings)):
            for message in messages:
                print(f"{level} {message['location']}: {message['message']}")
        print("Validation passed" if report.ok else f"Validation failed: {len(report.errors)} error(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
