/**
 * Real scoring/cueing payloads — the output of `scoring/zone_score.py --emit`.
 *
 * These replace the interim `scenario.ts` heuristic. Each scenario is a
 * point-in-time computation (no look-ahead past its `at` instant): a ranked
 * task-next queue of cells, the SAR dark-vessel detections, and the in-theatre
 * per-vessel risk breakdowns. Static JSON, computed at build time — the app just
 * renders it (same "compute once, stream to the app" model as the stitched tiles).
 */
import { dayKey } from "./clock";

export interface RiskBreakdown {
  risk: number;
  trust: number;
  confidence: number;
  /** weighted contributions to the base risk, e.g. behavioral_history / identity_risk / sar_mismatch */
  contributions: Record<string, number>;
  sar_mismatch: number;
  prior_days: number;
  explanation: string;
}

export interface TheatreVessel {
  mmsi: number;
  name: string | null;
  type: string;
  lon: number;
  lat: number;
  sog: number;
  dark: boolean;
  vessel_risk: number;
  sar: number;
  live_anomaly: number;
  breakdown: RiskBreakdown;
}

export interface CueDriver {
  name: string | null;
  mmsi: number;
  type: string;
  infra_proximity: number;
  vessel_risk: number;
  live_anomaly: number;
  sar: number;
  vessel_score: number;
}

export interface CueTerms {
  infra: number;
  vessel_risk: number;
  live_anomaly: number;
  sar: number;
  dark_density: number;
}

export interface ZoneCue {
  rank: number;
  bbox: [number, number, number, number];
  score: number;
  sensor: string;
  terms: CueTerms;
  drivers: CueDriver[];
  dark_contacts: number;
  why: string;
  disclaimer: string;
}

export interface DarkContact {
  lon: number;
  lat: number;
  confidence: number | null;
}

export interface ScenarioPayload {
  id: string;
  label: string;
  blurb: string;
  as_of: string;
  at: string;
  at_ts: number;
  bbox: [number, number, number, number];
  sensor: string;
  hero_mmsi: number | null;
  cues: ZoneCue[];
  dark_contacts: DarkContact[];
  dark_contacts_excluded_future: number;
  theatre: TheatreVessel[];
  disclaimer: string;
}

interface ScenarioIndex {
  scenarios: { id: string }[];
}

const BASE = "/data/cues";

/** Load the index + every scenario payload (a few hundred KB total, once). */
export async function loadScenarios(): Promise<ScenarioPayload[]> {
  const idxRes = await fetch(`${BASE}/index.json`, { cache: "no-store" });
  if (!idxRes.ok) throw new Error(`cues index: HTTP ${idxRes.status}`);
  const idx = (await idxRes.json()) as ScenarioIndex;
  const payloads = await Promise.all(
    idx.scenarios.map(async (s) => {
      const r = await fetch(`${BASE}/${s.id}.json`, { cache: "no-store" });
      if (!r.ok) throw new Error(`cues ${s.id}: HTTP ${r.status}`);
      return (await r.json()) as ScenarioPayload;
    }),
  );
  return payloads;
}

/** The scenario whose evaluation instant falls on the same UTC day as the clock
 *  (so scrubbing onto an incident day lights up its real cues + scores). */
export function activeScenario(clockT: number, scenarios: ScenarioPayload[]): ScenarioPayload | null {
  const day = dayKey(clockT);
  return scenarios.find((s) => dayKey(Date.parse(s.at)) === day) ?? null;
}

/** mmsi -> point-in-time risk, for the active scenario's theatre. */
export function riskByMmsi(scn: ScenarioPayload | null): Map<number, TheatreVessel> {
  const m = new Map<number, TheatreVessel>();
  if (scn) for (const v of scn.theatre) m.set(v.mmsi, v);
  return m;
}
