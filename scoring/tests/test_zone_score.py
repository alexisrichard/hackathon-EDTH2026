"""Unit tests for the zone (cueing) engine — the headline product of Part 3.

These exercise the pure ranking/geometry/no-look-ahead logic directly (no tiles,
no geojson, no network), so they are a fast regression guard on the engine that
`validate_fleet`/`zone_score --emit` run end-to-end.
"""
from __future__ import annotations

import unittest

from scoring.zone_score import (
    DARK_FULL,
    VESSEL_W,
    _cell,
    _epoch,
    _vessel_score,
    _why,
    filter_dark_no_lookahead,
    rank_cues,
)


def _flat_cable(_lon, _lat):
    """Stub cable-distance: everything 6 km away → infra_proximity 0.5."""
    return 6.0


def _vessel(mmsi, lon, lat, *, risk=0.0, sar=0.0, live=0.0, name=None, typ="cargo"):
    return {"mmsi": mmsi, "name": name or f"V{mmsi}", "type": typ,
            "lon": lon, "lat": lat, "vessel_risk": risk, "sar": sar,
            "live_anomaly": live}


class CellGeometryTests(unittest.TestCase):
    def test_cell_bbox_is_deterministic_regardless_of_member_order(self) -> None:
        # Two points at DIFFERENT latitudes within the same row+column must return
        # the SAME key AND the SAME bbox. Under the old per-point lon_step they
        # shared a key but produced subtly different bboxes; the lat-band fix
        # (lon_step from the row centre) makes the bbox structurally deterministic.
        k1, b1 = _cell(15.10, 55.30)
        k2, b2 = _cell(15.30, 55.50)
        self.assertEqual(k1, k2)
        self.assertEqual(b1, b2)

    def test_cell_size_is_about_50km(self) -> None:
        _key, bbox = _cell(15.0, 55.0)
        lon0, lat0, lon1, lat1 = bbox
        # ~0.45 deg lat ≈ 50 km; lon span widened by 1/cos(lat)
        self.assertAlmostEqual(lat1 - lat0, 50.0 / 111.32, places=3)
        self.assertGreater(lon1 - lon0, lat1 - lat0)  # lon cells are wider in deg

    def test_neighbouring_points_fall_in_distinct_cells(self) -> None:
        self.assertNotEqual(_cell(15.0, 55.0)[0], _cell(15.0, 56.0)[0])


class VesselScoreTests(unittest.TestCase):
    def test_weights_sum_to_one(self) -> None:
        self.assertAlmostEqual(sum(VESSEL_W.values()), 1.0, places=6)

    def test_a_maxed_vessel_reaches_one(self) -> None:
        rec = {"infra_proximity": 1.0, "vessel_risk": 1.0,
               "live_anomaly": 1.0, "sar": 1.0}
        self.assertAlmostEqual(_vessel_score(rec), 1.0, places=6)

    def test_each_term_contributes_its_weight(self) -> None:
        rec = {"infra_proximity": 0.0, "vessel_risk": 0.0,
               "live_anomaly": 0.0, "sar": 1.0}
        self.assertAlmostEqual(_vessel_score(rec), VESSEL_W["sar"], places=6)


class RankCuesTests(unittest.TestCase):
    def test_empty_theatre_no_dark_is_empty_queue(self) -> None:
        self.assertEqual(rank_cues([], [], _flat_cable), [])

    def test_terms_belong_to_a_single_vessel_no_frankenstein(self) -> None:
        # Two vessels in ONE cell: A is risky but not dark; B has the SAR signal
        # but low risk. The cell's displayed terms must equal ONE vessel's terms,
        # never max(risk_A, sar_B) stitched across both.
        a = _vessel(1, 15.00, 55.30, risk=0.9, sar=0.0, live=1.0, name="Risky")
        b = _vessel(2, 15.05, 55.30, risk=0.1, sar=1.0, live=0.0, name="Dark")
        [cue] = rank_cues([a, b], [], _flat_cable)
        t = cue["terms"]
        # Whichever vessel won, its (risk, sar) pair must be internally consistent
        # with exactly one input vessel — not (0.9 risk AND 1.0 sar).
        self.assertIn((t["vessel_risk"], t["sar"]), {(0.9, 0.0), (0.1, 1.0)})

    def test_vessel_with_all_signals_beats_partial_vessels(self) -> None:
        hero = _vessel(414270000, 16.0, 55.0, risk=0.8, sar=1.0, live=1.0, name="Hero")
        loiterer = _vessel(2, 18.0, 57.0, risk=0.99, sar=0.0, live=1.0, name="Loiter")
        cues = rank_cues([hero, loiterer], [], _flat_cable)
        self.assertEqual(cues[0]["drivers"][0]["name"], "Hero")
        self.assertEqual(cues[0]["rank"], 1)

    def test_noisy_or_combines_vessel_and_dark(self) -> None:
        # A cell with a moderate vessel AND a dark cluster must score strictly
        # higher than either signal alone (noisy-OR), and never exceed 1.0.
        v = _vessel(1, 15.0, 55.0, risk=0.4, live=0.0, sar=0.0)
        dark = [{"incident_id": "X", "lon": 15.0, "lat": 55.0} for _ in range(int(DARK_FULL))]
        [cue] = rank_cues([v], dark, _flat_cable)
        vessel_only = _vessel_score({"infra_proximity": 0.5, "vessel_risk": 0.4,
                                     "live_anomaly": 0.0, "sar": 0.0})
        self.assertGreater(cue["score"], vessel_only)
        self.assertLessEqual(cue["score"], 1.0)

    def test_dark_only_cell_names_no_ais_and_zeroes_vessel_terms(self) -> None:
        dark = [{"incident_id": "X", "lon": 15.4, "lat": 55.5} for _ in range(12)]
        [cue] = rank_cues([], dark, _flat_cable)
        self.assertIn("no AIS", cue["why"])
        self.assertEqual(cue["drivers"], [])
        self.assertEqual(cue["terms"]["vessel_risk"], 0.0)
        self.assertEqual(cue["terms"]["dark_density"], 1.0)
        self.assertEqual(cue["dark_contacts"], 12)

    def test_dark_dominated_cell_does_not_credit_a_present_ais_ship(self) -> None:
        # An AIS rescue boat shares the blast cell, but dark density dominates:
        # its terms/drivers must be suppressed so "no AIS suspect" isn't a lie.
        boat = _vessel(9, 15.4, 55.5, risk=0.6, live=1.0, sar=0.0, name="Rescue")
        dark = [{"incident_id": "X", "lon": 15.4, "lat": 55.5} for _ in range(20)]
        [cue] = rank_cues([boat], dark, _flat_cable)
        self.assertIn("no AIS", cue["why"])
        self.assertEqual(cue["drivers"], [])
        self.assertEqual(cue["terms"]["vessel_risk"], 0.0)

    def test_why_names_the_driver_and_its_reasons(self) -> None:
        hero = _vessel(1, 16.0, 55.0, risk=0.8, sar=1.0, live=1.0, name="Yi Peng 3")
        [cue] = rank_cues([hero], [], _flat_cable)
        self.assertIn("Yi Peng 3", cue["why"])
        self.assertIn("SAR", cue["why"])


class WhyTests(unittest.TestCase):
    def test_dark_narrates_when_it_dominates(self) -> None:
        self.assertIn("no AIS", _why(None, 30, dark_score=1.0, vessel_best=0.0))

    def test_vessel_narrates_when_it_dominates(self) -> None:
        best = {"name": "Foo", "mmsi": 1, "sar": 1.0, "live_anomaly": 1.0,
                "vessel_risk": 0.8, "infra_proximity": 0.9}
        self.assertIn("Foo", _why(best, 0, dark_score=0.0, vessel_best=0.9))


class NoLookAheadDarkTests(unittest.TestCase):
    AT = _epoch("2022-09-26T06:00:00Z")

    def _rows(self):
        return [
            {"incident_id": "NS", "signal_date": "2022-09-26T05:00:00Z", "lon": 1, "lat": 1},  # past → keep
            {"incident_id": "NS", "signal_date": "2022-09-26T07:00:00Z", "lon": 1, "lat": 1},  # future → drop
            {"incident_id": "NS", "signal_date": "", "lon": 1, "lat": 1},                       # blank → drop
            {"incident_id": "NS", "signal_date": "not-a-date", "lon": 1, "lat": 1},             # junk → drop
            {"incident_id": "OTHER", "signal_date": "2022-09-26T05:00:00Z", "lon": 1, "lat": 1},  # wrong incident
        ]

    def test_only_past_dated_matching_incident_is_kept(self) -> None:
        kept, dropped = filter_dark_no_lookahead(self._rows(), "NS", self.AT)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["signal_date"], "2022-09-26T05:00:00Z")
        self.assertEqual(dropped, 3)  # future + blank + junk (wrong incident not counted)

    def test_blank_date_is_failed_closed_not_admitted(self) -> None:
        # The exact hole the reviewer found: a blank date must NOT leak in.
        rows = [{"incident_id": "NS", "signal_date": "", "lon": 1, "lat": 1}]
        kept, dropped = filter_dark_no_lookahead(rows, "NS", self.AT)
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_date_only_contact_is_midnight_utc(self) -> None:
        rows = [{"incident_id": "NS", "signal_date": "2022-09-26", "lon": 1, "lat": 1}]
        kept, _ = filter_dark_no_lookahead(rows, "NS", self.AT)  # midnight < 06:00 → keep
        self.assertEqual(len(kept), 1)
        kept2, _ = filter_dark_no_lookahead(rows, "NS", _epoch("2022-09-25T23:00:00Z"))
        self.assertEqual(kept2, [])  # midnight 09-26 is future vs 09-25 23:00 → drop


if __name__ == "__main__":
    unittest.main()
