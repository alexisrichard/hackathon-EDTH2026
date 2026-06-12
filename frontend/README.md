# frontend/ — the dashboard

**Lane:** Frontend & Demo · **Owner:** _TBD_

The operator cockpit. One screen, three panels (see [`../PLAN.md`](../PLAN.md) §6):

1. **Map** — vessel tracks, cable routes, criticality overlay, alert markers, time-scrub bar.
2. **Alert feed** — top suspicious vessels now, one-click drill-in.
3. **Cueing panel** — "top 5 areas to task next," boxes on the map with reasoning.

**Hero demo:** Eagle S, Christmas Eve 2024 — watch the score climb over Estlink 2, the cueing engine recommend a satellite box, the cable flip red. Scripted, 3 min, with a recorded backup video (no live-data dependency).

**Proposed stack (confirm Friday):** React + MapLibre or deck.gl for the geo-heavy UI, Vite.

```
src/
├── components/   # Map, AlertFeed, CueingPanel, TimeScrubber
└── api/          # typed client → backend
```

**Contract:** code against [`../shared/api_contract.md`](../shared/api_contract.md) with a mock fixture; point at the live backend when it's up. Demo dates/AOIs come from [`../shared/scenarios.json`](../shared/scenarios.json).

**Run:** _TBD_ — likely `npm install && npm run dev`.

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md).
