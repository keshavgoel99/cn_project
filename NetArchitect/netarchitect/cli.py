import argparse
import json
import sys
from pathlib import Path

from .errors import PlanningError
from .exporter import export_plan
from .planner import build_plan
from .presets import PRESETS, get_preset


def main(argv=None):
    parser = argparse.ArgumentParser(prog="netarchitect", description="CIC-307 rule-based network planner. Python 3.9+, no runtime dependencies.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("presets", help="List the three assignment scenarios.")
    preset = commands.add_parser("preset", help="Print editable preset input JSON.")
    preset.add_argument("name", choices=sorted(PRESETS))
    plan = commands.add_parser("plan", help="Validate inputs, explain choices and export IOS configs.")
    source = plan.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", choices=sorted(PRESETS))
    source.add_argument("--input", type=Path, help="Custom input JSON, based on a preset.")
    plan.add_argument("--out", type=Path, required=True, help="Output directory (must be empty).")
    plan.add_argument("--force", action="store_true", help="Replace files from a previous NetArchitect export.")
    args = parser.parse_args(argv)
    try:
        if args.command == "presets":
            for name, data in PRESETS.items():
                print(f"{name:8} {data['name']}")
            return 0
        if args.command == "preset":
            print(json.dumps(get_preset(args.name), indent=2))
            return 0
        if args.preset:
            data = get_preset(args.preset)
        else:
            if args.input.stat().st_size > 1_000_000:
                raise PlanningError("Input JSON must be under 1 MB.")
            data = json.loads(args.input.read_text(encoding="utf-8"))
        result = build_plan(data)
        exported = export_plan(result, args.out, force=args.force)
        print(f"{result['name']}: {result['endpoint_count']} endpoints, {len(result['sites'])} sites")
        print("Routing: "+result["routing"]["protocol"])
        print(f"Exported {exported['config_count']} IOS configs; {exported['check_count']} offline checks passed.")
        print("Files: "+exported["directory"])
        print("Open report.html for decisions; use cabling.csv and host_examples.csv to build the lab.")
        print("Simulator verification still required; see docs/verification.md.")
        return 0
    except (PlanningError, OSError, ValueError) as exc:
        print(f"error [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
