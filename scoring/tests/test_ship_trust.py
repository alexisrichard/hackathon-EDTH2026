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
        self.assertEqual(result["confidence"], 0.15)  # only "watchlist checked"
        self.assertIn("no prior signal", result["explanation"])

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
