# shared/encoding — display encoding (the single source of truth)

`display_encoding.json` is the **one** place vessel-shape and suspicion-color
mappings live. Both lanes read it so backend display hints and frontend rendering
can never drift:

- **Backend** — `backend/app/core/display.py` loads this JSON and fills
  `ScoredVessel.display` (shape, color, color_hex, band). Also served verbatim at
  `GET /encoding`.
- **Frontend** — `frontend/src/types/encoding.ts` imports this JSON directly
  (Vite JSON import) and reproduces the same lookup/interpolation logic, so a
  client can recompute hints itself and get identical results.

## What's in it

| Key | Meaning |
|---|---|
| `ship_type_to_shape` | `ShipType` enum value → deck.gl shape key (triangle, square, diamond, …). |
| `suspicion_color_stops.stops` | Piecewise-linear color ramp `[score, [r,g,b]]`, score 0→1, cool→hot. Consumers interpolate. |
| `suspicion_bands` | Discrete bands (calm / watch / elevated / high / critical) as `[min_inclusive, max_exclusive]`. |
| `sensor_colors` | Recommended-sensor → RGB for the cueing overlay boxes. |

`_comment` keys are documentation only; consumers skip them.

## Changing it

It's a **contract** (like `shared/api_contract.md`): change via PR + a ping.
After editing the JSON, nothing needs regenerating — both consumers read it live —
but bump `version` and sanity-check both sides (`GET /encoding` vs the TS import).
Keep the `ship_type_to_shape` keys in sync with the `ShipType` enum
(`backend/app/models/enums.py` / `frontend/src/types/models.ts`).
