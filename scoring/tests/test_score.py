from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from scoring.score import TASKING_DISCLAIMER, rank_tasking, score_observation


SCENARIO_PATH = (
    Path(__file__).parents[1] / "demo_data" / "synthetic_scenario.json"
)


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        cls.observations = cls.scenario["observations"]

    def test_score_is_weighted_and_explained(self) -> None:
        result = score_observation(self.observations[0])

        self.assertEqual(result["vessel_id"], "DEMO-001")
        self.assertAlmostEqual(result["score"], 0.8125)
        self.assertEqual(
            round(sum(result["contributions"].values()), 4), result["score"]
        )
        self.assertIn("does not assess hostile intent", result["disclaimer"])
        self.assertIn("High observation priority", result["explanation"])

    def test_stale_ais_increases_priority_not_recent_ais(self) -> None:
        recent = score_observation(self.observations[0])
        stale_observation = copy.deepcopy(self.observations[0])
        stale_observation["factors"]["ais_recency"] = 0.0
        stale = score_observation(stale_observation)

        self.assertGreater(stale["score"], recent["score"])
        self.assertEqual(stale["contributions"]["ais_staleness"], 0.15)

    def test_no_window_has_zero_availability(self) -> None:
        result = score_observation(self.observations[-1])

        self.assertEqual(result["factors"]["satellite_availability"], 0.0)
        self.assertEqual(result["contributions"]["satellite_availability"], 0.0)

    def test_expired_window_is_not_available_or_ranked(self) -> None:
        expired = copy.deepcopy(self.observations[0])
        expired["satellite_windows"][0]["start"] = "2026-06-12T13:00:00Z"
        expired["satellite_windows"][0]["end"] = "2026-06-12T13:10:00Z"

        scored = score_observation(expired)

        self.assertEqual(scored["factors"]["satellite_availability"], 0.0)
        self.assertEqual(rank_tasking([expired]), [])

    def test_zero_availability_window_is_not_ranked(self) -> None:
        unavailable = copy.deepcopy(self.observations[0])
        unavailable["satellite_windows"][0]["availability"] = 0.0

        scored = score_observation(unavailable)

        self.assertEqual(scored["factors"]["satellite_availability"], 0.0)
        self.assertEqual(rank_tasking([unavailable]), [])

    def test_rank_returns_five_stable_synthetic_cues(self) -> None:
        first = rank_tasking(self.observations, top_n=5)
        second = rank_tasking(self.observations, top_n=5)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)
        self.assertEqual([item["rank"] for item in first], [1, 2, 3, 4, 5])
        self.assertEqual(first[0]["drivers"], ["DEMO-001"])
        self.assertNotIn(
            "DEMO-007", {driver for item in first for driver in item["drivers"]}
        )
        self.assertTrue(all(item["is_synthetic"] for item in first))
        self.assertTrue(
            all(item["disclaimer"] == TASKING_DISCLAIMER for item in first)
        )

    def test_box_is_approximately_fifty_kilometres(self) -> None:
        item = rank_tasking([self.observations[0]], top_n=1)[0]
        min_lon, min_lat, max_lon, max_lat = item["bbox"]
        center_lat = (min_lat + max_lat) / 2
        height_km = (max_lat - min_lat) * 111.32
        width_km = (
            (max_lon - min_lon)
            * 111.32
            * math.cos(math.radians(center_lat))
        )

        self.assertAlmostEqual(height_km, 50.0, delta=0.1)
        self.assertAlmostEqual(width_km, 50.0, delta=0.1)

    def test_same_box_aggregates_drivers_without_simple_sum(self) -> None:
        second = copy.deepcopy(self.observations[0])
        second["vessel_id"] = "DEMO-001-B"
        second["position"] = [24.76, 59.56]
        ranked = rank_tasking([self.observations[0], second], top_n=5)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["drivers"], ["DEMO-001", "DEMO-001-B"])
        self.assertLessEqual(ranked[0]["score"], 1.0)

    def test_empty_input_and_zero_top_n_return_empty(self) -> None:
        self.assertEqual(rank_tasking([]), [])
        self.assertEqual(rank_tasking(self.observations, top_n=0), [])

    def test_invalid_factor_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.observations[0])
        invalid["factors"]["unusual_movement"] = 1.1

        with self.assertRaisesRegex(ValueError, "0.0 to 1.0"):
            score_observation(invalid)

    def test_non_finite_factor_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.observations[0])
        invalid["factors"]["unusual_movement"] = float("nan")

        with self.assertRaisesRegex(ValueError, "finite"):
            score_observation(invalid)

    def test_invalid_position_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.observations[0])
        invalid["position"] = [2.35, 48.86]

        with self.assertRaisesRegex(ValueError, "Baltic"):
            score_observation(invalid)

    def test_invalid_window_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.observations[0])
        invalid["satellite_windows"][0]["end"] = invalid["satellite_windows"][0][
            "start"
        ]

        with self.assertRaisesRegex(ValueError, "after its start"):
            score_observation(invalid)

    def test_window_must_declare_synthetic_status(self) -> None:
        invalid = copy.deepcopy(self.observations[0])
        del invalid["satellite_windows"][0]["is_synthetic"]

        with self.assertRaisesRegex(ValueError, "is_synthetic"):
            score_observation(invalid)


if __name__ == "__main__":
    unittest.main()
