# frontend/ — the dashboard (V1 RUNNING)

**Lane:** Frontend & Demo · **Owner:** Alexis

The operator cockpit, V1 live:

```bash
npm install
npm run dev          # → http://localhost:5173
```

**What V1 does** (all in-browser, zero backend/AWS needed):

- **Satellite basemap** — EOX Sentinel-2 Cloudless tiles (real imagery, global, CC-BY),
  CSS-dimmed to the ops aesthetic. Falls back to the void background offline.
- **Geography** — country borders + EEZ + 12 nm territorial seas (Marine Regions), with
  ISO zone codes labelled along the maritime lines.
- **Infrastructure** — per-category toggles grouped by theme, each with a select-all master:
  *Energy* (pipelines · power cables · terminals · platforms · wind), *Telecom* (submarine
  cables), *Transport* (commercial/naval ports · anchorages · chokepoints), *Military*
  (naval bases · restricted/exercise zones, rendered as red dashed areas).
- **Geopoints** — ~840 scored & **clustered** POI sites colored by **v1 strategic score**
  + optional **heatmap**. Lighthouses dropped (nav aids, not targets); ports filtered to
  working harbours; anchorages off by default. Data + scoring weights:
  `scripts/geo/build_web_layers.py` → `public/data/*.json`.
- **Mock AIS fleet** — EAGLE S scripted incident + ~110 synthetic vessels on Baltic +
  North Sea lanes (`src/mock/fleet.ts`), shape=type / color=suspicion per the shared
  encoding. Replay clock: play/pause/speed/scrub; the suspicion arc crosses the
  14:00Z Estlink 2 cut and the SAR cue fires at 13:35Z.
- **UI shell** — topbar (mark = status light), alert feed (click → fly to vessel),
  task-next queue, time scrubber with incident tick, layer toggles, legend.

**Swap mock → live:** `src/mock/fleet.ts` is the stand-in for the typed API client in
`src/api/` (backend `/scores` + `/cues`); both speak the same encoding/types.

**Contract:** [`../shared/api_contract.md`](../shared/api_contract.md). Demo dates/AOIs: [`../shared/scenarios.json`](../shared/scenarios.json).

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
