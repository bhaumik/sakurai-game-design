"""Offline, validated generation of compatible CSV views and area candidates.

python3 tools/build_data.py areas|data [--root PATH]
Knowledge sidecars remain authored additive inputs and are never rewritten here.
"""
import argparse
import json
from pathlib import Path

try:
    from .contracts import (AREA_PREFIX, KINDS, PRIORITY, DATA_PATH, EPISODE_FIELDS,
                            Report, csv_text, flat, projected_areas, projected_data,
                            publish, read_jsonl, validate_legacy, ContractError)
    from .validate import preflight
except ImportError:
    from contracts import (AREA_PREFIX, KINDS, PRIORITY, DATA_PATH, EPISODE_FIELDS,
                           Report, csv_text, flat, projected_areas, projected_data,
                           publish, read_jsonl, validate_legacy, ContractError)
    from validate import preflight

ROOT = Path(__file__).resolve().parent.parent


def inputs(root):
    preflight(root)
    report = Report()
    data = validate_legacy(root, report, check_outputs=False, compare_outputs=False)
    report.require()
    return data


def build_areas(root=None):
    root = Path(root or ROOT).resolve()
    data = inputs(root)
    episodes, areas = projected_areas(data["index"], data["batches"])
    outputs = {DATA_PATH / "episodes.csv": csv_text(EPISODE_FIELDS, episodes)}
    for area, rows in sorted(areas.items()):
        outputs[Path("work/areas") / f"{area}.jsonl"] = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    # Only known generator-owned area names can be retired. Unknown authored files survive.
    stale = [Path("work/areas") / f"{area}.jsonl" for area in AREA_PREFIX if area not in areas]
    publish(root, outputs, stale)
    return outputs


def build_data(root=None):
    root = Path(root or ROOT).resolve()
    rows_by_kind = projected_data(inputs(root)["parts"])
    outputs = {DATA_PATH / f"{kind}.csv": csv_text(fields, rows_by_kind[kind]) for kind, fields in KINDS.items()}
    publish(root, outputs)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("areas", "data"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        outputs = {"areas": build_areas, "data": build_data}[args.stage](args.root)
    except (ContractError, OSError) as exc:
        parser.exit(1, f"Build failed before publication or was rolled back: {exc}\n")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
