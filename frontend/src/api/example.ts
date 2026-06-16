/**
 * Example usage of the data layer (NOT a UI component).
 *
 * Shows the frontend lane how to drive the map from the typed client + encoding:
 * fetch scored vessels at the demo instant, derive deck.gl shape + RGB color from
 * each vessel's suspicion, and pull the top cue box. Delete or adapt when wiring
 * the real components.
 */

import { api } from "./client";
import { colorForSuspicion, shapeForShipType } from "../types/encoding";
import type { CueRecommendation, ScoredVessel } from "../types/models";

/** A flat, render-ready vessel marker for a deck.gl IconLayer / ScatterplotLayer. */
export interface VesselMarker {
  mmsi: number;
  name: string | null;
  position: [number, number]; // [lon, lat]
  heading: number;
  shape: string; // deck.gl icon key
  color: [number, number, number]; // RGB
  suspicion: number;
  why: string;
}

/** Map a ScoredVessel to a render-ready marker. */
export function toMarker(s: ScoredVessel): VesselMarker {
  return {
    mmsi: s.vessel.mmsi,
    name: s.vessel.name,
    position: [s.position.lon, s.position.lat],
    heading: s.position.heading ?? s.position.cog ?? 0,
    // The backend already provides display.shape / display.color; here we show
    // recomputing client-side from the shared encoding — they agree by construction.
    shape: shapeForShipType(s.vessel.ship_type),
    color: colorForSuspicion(s.breakdown.suspicion),
    suspicion: s.breakdown.suspicion,
    why: s.breakdown.why,
  };
}

/** Fetch the demo frame: vessel markers + the #1 cue box, for a given instant. */
export async function loadDemoFrame(
  t?: Date | string,
): Promise<{ markers: VesselMarker[]; topCue: CueRecommendation | undefined }> {
  const [scores, cues] = await Promise.all([api.scores({ t }), api.cues({ t, top: 5 })]);
  return { markers: scores.map(toMarker), topCue: cues[0] };
}
