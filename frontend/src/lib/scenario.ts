/**
 * Interim scoring + cue, until Côme's scoring engine lands.
 *
 * Real tracks now come from the AIS archive (trackStore). For the demo we
 * surface the known C-Lion1 / BCS-East-West suspect — the bulk carrier
 * YI PENG 3 (MMSI 414270000), which dragged anchor ~100 nm near Bornholm on
 * 2024-11-18 — by amplifying its *real* anomalies (low speed + AIS blackouts).
 * Everyone else gets a low kinematic baseline. This is a placeholder: the real
 * per-vessel suspicion will come from the scoring tier over the keyframes.
 */
import type { VesselFix } from "./trackStore";

export const SUSPECT_MMSI = 414270000; // YI PENG 3

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

export interface Scored {
  suspicion: number;
  why: string;
}

export function scoreFix(v: VesselFix): Scored {
  if (v.mmsi === SUSPECT_MMSI) {
    let s = 0.4;
    if (v.sog < 5) s += 0.25; // dragging / loitering
    if (v.dark) s += 0.25; // AIS blackout
    s = clamp01(s + 0.05);
    const why = v.dark
      ? "Suspect bulk carrier — AIS blackout near the C-Lion1 corridor"
      : `Bulk carrier at ${v.sog.toFixed(1)} kn over the C-Lion1 / BCS cable corridor`;
    return { suspicion: s, why };
  }
  // crude kinematic baseline for the fleet (placeholder for the scoring tier)
  let s = 0.03 + (v.mmsi % 13) / 130; // 0.03–0.13 jitter
  if (v.dark) s += 0.22;
  if (v.sog >= 0.2 && v.sog < 2) s += 0.1; // low-speed loiter (not fully stopped)
  s = clamp01(s);
  const why = v.dark
    ? "AIS dropout — position dead-reckoned"
    : s > 0.2
      ? `Low-speed loiter (${v.sog.toFixed(1)} kn)`
      : "Nominal — consistent with declared class and lane";
  return { suspicion: s, why };
}

/** Cue box around a hot vessel (the tasking recommendation), or null. */
export function cueFor(lon: number, lat: number): [number, number, number, number] {
  const dx = 0.22 / Math.cos((lat * Math.PI) / 180);
  return [lon - dx, lat - 0.15, lon + dx, lat + 0.15];
}
