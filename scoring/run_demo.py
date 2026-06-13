"""Run the transparent scorer against the bundled synthetic scenario."""

from __future__ import annotations

import json
from pathlib import Path

from scoring.score import rank_tasking


def main() -> None:
    scenario_path = Path(__file__).parent / "demo_data" / "synthetic_scenario.json"
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    recommendations = rank_tasking(scenario["observations"], top_n=5)

    print("Synthetic defensive collection-priority demo")
    print("No real vessel activity or satellite availability is represented.\n")
    for item in recommendations:
        window = item["recommended_window"]
        print(
            f"{item['rank']}. {item['grid_id']} | "
            f"{item['score'] * 100:.1f}/100 | {window['sensor']} | "
            f"{window['start']} to {window['end']}"
        )
        print(f"   {item['explanation']}")


if __name__ == "__main__":
    main()
