/**
 * Frontend mirror of the shared display encoding.
 *
 * The single source of truth is `shared/encoding/display_encoding.json`. This
 * module imports that JSON directly (via Vite's JSON import) so the backend
 * (which reads the same file) and the frontend never drift. The helper
 * functions reproduce the backend's `app/core/display.py` logic exactly, so a
 * client can recompute shape/color itself instead of trusting the per-vessel
 * `display` hints the API already provides.
 */

// Vite resolves JSON imports out of the box. The relative path climbs out of
// frontend/src/types/ to the repo-root shared/ directory.
import encoding from "../../../shared/encoding/display_encoding.json";

import type { RGB, SensorType, ShipType, SuspicionBand } from "./models";

export const DISPLAY_ENCODING = encoding;

// The JSON carries `_comment` string keys alongside the data, so cast through
// `unknown` to the data-only shape we actually consume.
const SHIP_SHAPES = encoding.ship_type_to_shape as unknown as Record<string, string>;
const COLOR_STOPS = encoding.suspicion_color_stops.stops as unknown as [number, number[]][];
const BANDS = encoding.suspicion_bands as unknown as Record<string, number[] | string>;
const SENSOR_COLORS = encoding.sensor_colors as unknown as Record<string, number[]>;

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

/** deck.gl shape key for a normalized vessel class. */
export function shapeForShipType(shipType: ShipType): string {
  return SHIP_SHAPES[shipType] ?? SHIP_SHAPES["unknown"] ?? "circle";
}

/** Interpolate the suspicion color ramp at `score` in [0, 1] -> RGB. */
export function colorForSuspicion(score: number): RGB {
  const s = clamp01(score);
  let [prevPos, prevRgb] = COLOR_STOPS[0];
  for (const [pos, rgb] of COLOR_STOPS) {
    if (s <= pos) {
      if (pos === prevPos) {
        return rgb.map((c) => Math.round(c)) as RGB;
      }
      const frac = (s - prevPos) / (pos - prevPos);
      return rgb.map((c, i) => Math.round(prevRgb[i] + frac * (c - prevRgb[i]))) as RGB;
    }
    prevPos = pos;
    prevRgb = rgb;
  }
  const last = COLOR_STOPS[COLOR_STOPS.length - 1][1];
  return last.map((c) => Math.round(c)) as RGB;
}

/** Same as `colorForSuspicion` but as a `#rrggbb` hex string. */
export function colorHexForSuspicion(score: number): string {
  const [r, g, b] = colorForSuspicion(score);
  const h = (n: number) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

/** Bucket a suspicion score into a discrete band. */
export function bandForScore(score: number): SuspicionBand {
  const s = clamp01(score);
  for (const [name, range] of Object.entries(BANDS)) {
    if (name.startsWith("_") || !Array.isArray(range)) continue;
    const [lo, hi] = range as number[];
    if (s >= lo && s < hi) return name as SuspicionBand;
  }
  return "critical";
}

/** RGB color for a recommended sensor (cueing overlay boxes). */
export function colorForSensor(sensor: SensorType): RGB {
  return (SENSOR_COLORS[sensor] ?? [125, 207, 255]) as RGB;
}
