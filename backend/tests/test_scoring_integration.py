from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
for path in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.data import mock_scenario as ms
from app.data.mock import MockDataSource


class ScoringIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MockDataSource()

    def test_scores_use_five_factor_engine(self) -> None:
        scores = self.source.scores_at(ms.DEMO_INSTANT)

        self.assertEqual(scores[0].vessel.mmsi, ms.SUSPECT_MMSI)
        breakdown = scores[0].breakdown
        self.assertGreater(breakdown.score, 0.7)
        self.assertEqual(breakdown.score, breakdown.suspicion)
        self.assertEqual(len(breakdown.contributions), 5)
        self.assertIn("does not assess hostile intent", breakdown.disclaimer)

    def test_cues_are_ranked_by_scoring_engine(self) -> None:
        cues = self.source.cues_at(ms.DEMO_INSTANT, top=5)

        self.assertGreaterEqual(len(cues), 1)
        self.assertLessEqual(len(cues), 5)
        self.assertEqual([cue.rank for cue in cues], list(range(1, len(cues) + 1)))
        self.assertIn(ms.SUSPECT_MMSI, cues[0].driver_mmsis)
        self.assertEqual(cues[0].sensor.value, "SAR")
        self.assertGreaterEqual(cues[0].score, cues[-1].score)
        self.assertIn("not for targeting", cues[0].why)

    def test_bbox_filters_before_ranking(self) -> None:
        bbox = (24.6, 59.6, 25.1, 60.0)
        cues = self.source.cues_at(ms.DEMO_INSTANT, top=1, bbox=bbox)

        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].driver_mmsis, [230123000])


if __name__ == "__main__":
    unittest.main()
