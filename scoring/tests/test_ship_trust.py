from __future__ import annotations

import copy
import unittest

from scoring.ship_trust import RISK_DISCLAIMER, score_vessel_risk


AS_OF = "2024-11-18T00:00:00Z"


def _hero_profile() -> dict:
    """Yi Peng 3 on the C-Lion1 cut day: anomalous behaviour, some identity
    risk, and — truthfully — no sanction in force on that date."""
    return {
        "vessel_id": "MMSI:412549000",
        "vessel_name": "Yi Peng 3",
        "is_synthetic": False,
        "as_of": AS_OF,
        "behavioral_history": {
            "available": True,
            "known_through": "2024-11-17T23:59:59Z",
            "value": 0.82,
            "components": {"loiter_over_cable_events": 1, "dark_gaps": 2},
        },
        "identity_risk": {
            "available": True,
            "known_through": "2024-10-01T00:00:00Z",
            "value": 0.40,
        },
        "watchlist": [],
    }


class ShipTrustTests(unittest.TestCase):
    def test_behaviour_alone_flags_the_hero_without_a_watchlist_hit(self) -> None:
        result = score_vessel_risk(_hero_profile())

        # base = (0.70*0.82 + 0.30*0.40) / 1.0 = 0.694
        self.assertAlmostEqual(result["risk"], 0.694, places=3)
        self.assertFalse(result["watchlist_floor_applied"])
        self.assertEqual(result["applied_watchlist_hits"], [])
        self.assertAlmostEqual(result["trust"], 1.0 - result["risk"], places=4)
        self.assertIn("prior AIS behaviour is anomalous", result["explanation"])
        self.assertEqual(result["disclaimer"], RISK_DISCLAIMER)

    def test_contributions_sum_to_base_when_no_floor(self) -> None:
        result = score_vessel_risk(_hero_profile())
        self.assertAlmostEqual(
            round(sum(result["contributions"].values()), 4), result["risk"], places=4
        )

    def test_a_point_in_time_listing_floors_the_risk_high(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = 0.10  # benign behaviour
        profile["identity_risk"]["value"] = 0.10
        profile["watchlist"] = [
            {
                "source": "OFAC_SDN",
                "listed_date": "2024-06-01",
                "severity": 0.9,
                "match": "imo:9999999",
            }
        ]
        result = score_vessel_risk(profile)

        self.assertEqual(result["risk"], 0.9)  # floor wins over benign 0.10 base
        self.assertTrue(result["watchlist_floor_applied"])
        self.assertEqual(len(result["applied_watchlist_hits"]), 1)
        self.assertIn("OFAC_SDN", result["explanation"])

    def test_listing_dated_after_t_is_excluded_no_look_ahead(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = 0.10
        profile["identity_risk"]["value"] = 0.10
        # Sanctioned in 2025 — AFTER the 2024-11-18 evaluation date.
        profile["watchlist"] = [
            {"source": "OFAC_SDN", "listed_date": "2025-01-10", "severity": 0.9}
        ]
        result = score_vessel_risk(profile)

        self.assertFalse(result["watchlist_floor_applied"])
        self.assertEqual(result["applied_watchlist_hits"], [])
        self.assertEqual(len(result["excluded_future_hits"]), 1)
        self.assertLess(result["risk"], 0.5)
        self.assertIn("no look-ahead", result["explanation"])

    def test_a_listing_on_the_exact_day_applies(self) -> None:
        profile = _hero_profile()
        profile["watchlist"] = [
            {"source": "UK_OFSI", "listed_date": "2024-11-18", "severity": 0.8}
        ]
        result = score_vessel_risk(profile)
        self.assertEqual(len(result["applied_watchlist_hits"]), 1)

    def test_behavioral_known_through_after_as_of_is_rejected(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["known_through"] = "2024-11-19T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "look-ahead"):
            score_vessel_risk(profile)

    def test_missing_identity_lowers_confidence_without_raising_risk(self) -> None:
        full = score_vessel_risk(_hero_profile())

        no_identity = _hero_profile()
        no_identity["identity_risk"] = {"available": False}
        partial = score_vessel_risk(no_identity)

        self.assertLess(partial["confidence"], full["confidence"])
        # Behavioural-only risk renormalizes to the behavioural value itself
        # (0.82) — higher than the blended 0.694, but absence never *invented*
        # risk: it is exactly the one signal we have.
        self.assertAlmostEqual(partial["risk"], 0.82, places=3)
        self.assertFalse(partial["signals_available"]["identity_risk"])

    def test_no_signals_at_all_is_low_risk_low_confidence(self) -> None:
        result = score_vessel_risk(
            {
                "vessel_id": "MMSI:000000000",
                "is_synthetic": True,
                "as_of": AS_OF,
                "behavioral_history": {"available": False},
                "identity_risk": {"available": False},
                "watchlist": [],
            }
        )
        self.assertEqual(result["risk"], 0.0)
        self.assertEqual(result["confidence"], 0.30)  # watchlist + SAR always checked
        self.assertIn("no prior signal", result["explanation"])

    def test_sar_dark_approach_adds_on_top_and_explains(self) -> None:
        profile = _hero_profile()
        profile["sar_signals"] = [
            {"signal_type": "ais_dark_approach", "signal_date": "2024-11-17", "gap_hours": None}
        ]
        result = score_vessel_risk(profile)
        # base (~0.69 from behavioral 0.82 + identity 0.40) + 0.5 SAR, clamped to 1.
        self.assertGreater(result["risk"], 0.9)
        self.assertEqual(result["sar_mismatch"], 1.0)
        self.assertEqual(result["contributions"]["sar_mismatch"], 0.5)
        self.assertIn("dark approach", result["explanation"])

    def test_sar_signal_dated_after_t_is_excluded(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = 0.0
        profile["identity_risk"]["value"] = 0.0
        profile["sar_signals"] = [
            {"signal_type": "ais_dark_approach", "signal_date": "2025-01-10", "gap_hours": None}
        ]
        result = score_vessel_risk(profile)
        self.assertEqual(result["sar_mismatch"], 0.0)
        self.assertEqual(len(result["excluded_future_sar"]), 1)

    def test_sar_signal_same_day_but_after_t_is_excluded(self) -> None:
        # as_of is 2024-11-18T00:00:00Z; a signal 6 h later the SAME day is still
        # future → must be excluded (instant-granularity no-look-ahead).
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = 0.0
        profile["identity_risk"]["value"] = 0.0
        profile["sar_signals"] = [
            {"signal_type": "ais_dark_approach", "signal_date": "2024-11-18T06:00:00Z", "gap_hours": None}
        ]
        result = score_vessel_risk(profile)
        self.assertEqual(result["sar_mismatch"], 0.0)
        self.assertEqual(len(result["excluded_future_sar"]), 1)

    def test_sar_blackout_weighted_by_gap_duration(self) -> None:
        def risk_for(gap):
            p = _hero_profile()
            p["behavioral_history"]["value"] = 0.0
            p["identity_risk"]["value"] = 0.0
            p["sar_signals"] = [
                {"signal_type": "ais_blackout", "signal_date": "2024-11-18", "gap_hours": gap}
            ]
            return score_vessel_risk(p)["sar_mismatch"]

        # 0.7 weight × min(1, gap/24): 24h → 0.7, 12h → 0.35, 2h → ~0.058
        self.assertAlmostEqual(risk_for(24), 0.7, places=2)
        self.assertAlmostEqual(risk_for(12), 0.35, places=2)
        self.assertGreater(risk_for(24), risk_for(2))

    def test_invalid_sar_type_is_rejected(self) -> None:
        profile = _hero_profile()
        profile["sar_signals"] = [{"signal_type": "made_up", "signal_date": "2024-11-17"}]
        with self.assertRaisesRegex(ValueError, "signal_type"):
            score_vessel_risk(profile)

    def test_full_signals_give_full_confidence(self) -> None:
        result = score_vessel_risk(_hero_profile())
        self.assertEqual(result["confidence"], 1.0)

    def test_invalid_value_is_rejected(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = 1.5
        with self.assertRaisesRegex(ValueError, "0.0 to 1.0"):
            score_vessel_risk(profile)

    def test_non_finite_value_is_rejected(self) -> None:
        profile = _hero_profile()
        profile["behavioral_history"]["value"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            score_vessel_risk(profile)

    def test_as_of_must_be_utc(self) -> None:
        profile = _hero_profile()
        profile["as_of"] = "2024-11-18T00:00:00"  # no Z
        with self.assertRaisesRegex(ValueError, "UTC"):
            score_vessel_risk(profile)

    def test_known_through_required_when_signal_present(self) -> None:
        profile = _hero_profile()
        del profile["behavioral_history"]["known_through"]
        with self.assertRaisesRegex(ValueError, "known_through is required"):
            score_vessel_risk(profile)

    def test_maxed_component_under_moderate_composite_is_named(self) -> None:
        """A moderate composite with one maxed component (the real Yi Peng 3
        case: dark_events=1.0 but blended value only 0.30) must explain itself
        by that component, not fall back to 'the known signals are limited'."""
        result = score_vessel_risk(
            {
                "vessel_id": "MMSI:414270000",
                "vessel_name": "Yi Peng 3",
                "is_synthetic": False,
                "as_of": AS_OF,
                "behavioral_history": {
                    "available": True,
                    "known_through": "2024-11-08T23:59:59Z",
                    "value": 0.30,
                    "components": {"dark_events": 1.0, "loiter": 0.0, "kinematics": 0.0},
                },
                "identity_risk": {
                    "available": True,
                    "known_through": "2024-10-01T00:00:00Z",
                    "value": 0.35,
                },
                "watchlist": [],
            }
        )
        self.assertIn("ran dark", result["explanation"])
        self.assertNotIn("limited", result["explanation"])

    def test_output_is_deterministic(self) -> None:
        profile = _hero_profile()
        self.assertEqual(
            score_vessel_risk(copy.deepcopy(profile)),
            score_vessel_risk(copy.deepcopy(profile)),
        )


if __name__ == "__main__":
    unittest.main()
