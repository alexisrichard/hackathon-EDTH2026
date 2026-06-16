from __future__ import annotations

import json
import unittest
from pathlib import Path

from scoring.behavioral import behavioral_history
from scoring.ship_trust import score_vessel_risk

CUT_DAY_FILE = (
    Path(__file__).parents[2]
    / "frontend"
    / "public"
    / "data"
    / "ais"
    / "tracks_2024-11-18.json"
)


def _steady_day(day: str, kn: float = 12.0) -> dict:
    """A clean transit: constant speed, constant heading, no gaps."""
    base = 1731888000
    kf = [[base + i * 300, 15.0 + i * 0.02, 55.0, kn, 90] for i in range(12)]
    return {"date": day, "kf": kf, "gaps": []}


def _shady_day(day: str) -> dict:
    """Loitering (slow), erratic (sharp turns), and a long dark gap."""
    base = 1731888000
    courses = [90, 10, 200, 30, 250, 70]  # repeated sharp turns
    kf = [
        [base + i * 300, 19.0, 59.0, 0.5, courses[i % len(courses)]]
        for i in range(12)
    ]
    return {"date": day, "kf": kf, "gaps": [[base, base + 3600]]}  # 1h dark


class BehavioralTests(unittest.TestCase):
    def test_clean_transit_scores_near_zero(self) -> None:
        result = behavioral_history([_steady_day("2024-01-01")], as_of="2024-11-18")
        self.assertTrue(result["available"])
        self.assertLess(result["value"], 0.05)
        self.assertEqual(result["components"]["long_dark_gaps"], 0)

    def test_shady_track_scores_high(self) -> None:
        result = behavioral_history([_shady_day("2024-01-01")], as_of="2024-11-18")
        self.assertGreater(result["value"], 0.6)
        self.assertEqual(result["components"]["long_dark_gaps"], 1)
        self.assertGreater(result["components"]["slow_keyframes"], 0)
        self.assertGreater(result["components"]["sharp_turns"], 0)

    def test_clean_and_shady_are_separable(self) -> None:
        clean = behavioral_history([_steady_day("2024-01-01")], as_of="2024-11-18")
        shady = behavioral_history([_shady_day("2024-01-01")], as_of="2024-11-18")
        self.assertGreater(shady["value"], clean["value"] + 0.5)

    def test_no_history_is_unavailable_not_risky(self) -> None:
        result = behavioral_history([], as_of="2024-11-18")
        self.assertFalse(result["available"])
        self.assertEqual(result["value"], 0.0)
        self.assertIsNone(result["known_through"])

    def test_day_on_or_after_as_of_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "look-ahead"):
            behavioral_history([_steady_day("2024-11-18")], as_of="2024-11-18")
        with self.assertRaisesRegex(ValueError, "look-ahead"):
            behavioral_history([_steady_day("2024-12-01")], as_of="2024-11-18")

    def test_critical_proximity_only_when_predicate_supplied(self) -> None:
        day = _shady_day("2024-01-01")
        without = behavioral_history([day], as_of="2024-11-18")
        self.assertNotIn("critical_proximity", without["components"])

        # Predicate that treats the loiter location (19.0, 59.0) as on-cable.
        on_cable = lambda lon, lat: abs(lon - 19.0) < 0.5 and abs(lat - 59.0) < 0.5
        with_geo = behavioral_history([day], as_of="2024-11-18", near_critical=on_cable)
        self.assertEqual(with_geo["components"]["critical_proximity"], 1.0)
        self.assertGreaterEqual(with_geo["value"], without["value"])

    def test_known_through_feeds_score_vessel_risk(self) -> None:
        """The extractor's output must slot straight into the risk combiner."""
        history = behavioral_history(
            [_shady_day("2024-01-01"), _shady_day("2024-02-01")],
            as_of="2024-11-18",
        )
        scored = score_vessel_risk(
            {
                "vessel_id": "MMSI:1",
                "is_synthetic": True,
                "as_of": "2024-11-18T00:00:00Z",
                "behavioral_history": history,
                "identity_risk": {"available": False},
                "watchlist": [],
            }
        )
        self.assertGreater(scored["risk"], 0.6)

    def test_real_yi_peng_3_cut_day_track_shows_dark_and_loiter(self) -> None:
        """Anchor on real data: the hero's actual 2024-11-18 keyframes must
        exhibit the loiter + dark-gap signature the features detect."""
        if not CUT_DAY_FILE.exists():
            self.skipTest("AIS corpus not present")
        vessels = json.loads(CUT_DAY_FILE.read_text())["vessels"]
        yp = next(v for v in vessels if v["mmsi"] == 414270000)
        # Treat the cut day as a single record dated the day before as_of.
        day = {"date": "2024-11-18", "kf": yp["kf"], "gaps": yp["gaps"]}
        result = behavioral_history([day], as_of="2024-11-19")
        self.assertTrue(result["available"])
        self.assertGreaterEqual(result["components"]["long_dark_gaps"], 1)
        self.assertGreater(result["components"]["slow_keyframes"], 0)


if __name__ == "__main__":
    unittest.main()
