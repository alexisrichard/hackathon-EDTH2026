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

## Data layer (built — types + client + encoding)

The typed data layer the map renders against is already in place; UI components
are day-of work.

```
src/
├── types/
│   ├── models.ts     # TS mirror of the backend pydantic models (1:1)
│   ├── encoding.ts   # imports shared/encoding/display_encoding.json + shape/color helpers
│   └── index.ts
└── api/
    ├── client.ts     # typed fetch client (CueingApiClient + default `api`)
    ├── example.ts    # non-UI usage example (loadDemoFrame, toMarker)
    └── index.ts
```

Usage:

```ts
import { api } from "./api";
import { colorForSuspicion, shapeForShipType } from "./types/encoding";

const scores = await api.scores({ t: "2024-12-25T13:50:00Z" });   // ScoredVessel[]
const cues   = await api.cues({ t: "2024-12-25T13:50:00Z", top: 5 });
// Each ScoredVessel already carries display.shape / display.color / display.color_hex;
// the helpers recompute the same values client-side from the shared encoding.
```

Point the client at the backend with `VITE_API_BASE_URL` (see `.env.example`;
default `http://localhost:8000`, mock mode). Recommended deps (react, typescript,
vite, deck.gl, maplibre-gl) are listed in `package.json`.

**Run:** `npm install && npm run dev` (after the UI is built). Typecheck the data
layer now with `npm run typecheck`.

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md).
