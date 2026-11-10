"""Regenerate all three assignment exports. Run from any working directory."""
from pathlib import Path

from netarchitect.exporter import export_plan
from netarchitect.planner import build_plan
from netarchitect.presets import get_preset


def main():
    root = Path(__file__).resolve().parent
    for name in ("campus", "metro", "global"):
        plan = build_plan(get_preset(name))
        result = export_plan(plan, root/"output"/name, force=True)
        print(f"{name}: {result['config_count']} configs, {result['check_count']} offline checks passed")
    print("Open output/campus/report.html to start. See docs/verification.md for the simulator lab.")


if __name__ == "__main__":
    main()
