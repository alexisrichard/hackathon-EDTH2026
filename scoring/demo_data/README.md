# Synthetic scoring scenario

`synthetic_scenario.json` is the small, offline-safe fixture for the first
hackathon demo. Everything in it is fictional:

- seven vessels and their AIS-like tracks;
- seven protected or contextual infrastructure features;
- six satellite collection windows;
- factor values prepared for the scoring contract.

The scenario deliberately includes different situations:

- `DEMO-001` has strong proximity and movement factors;
- `DEMO-003` has stale AIS, represented by a low `ais_recency` value;
- `DEMO-004` follows a routine-looking track near a port;
- `DEMO-007` has no satellite window and must not become an immediate tasking
  recommendation.

The future scoring module should receive the value of the top-level
`observations` array:

```python
scenario = json.load(open("scoring/demo_data/synthetic_scenario.json"))
recommendations = rank_tasking(scenario["observations"], top_n=5)
```

The `infrastructure` and `vessel_tracks` sections exist so the backend and
dashboard can render the same fictional scenario without relying on network
access or real-time operational data.

Do not present these values as real vessel activity or real satellite
availability.
