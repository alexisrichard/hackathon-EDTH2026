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

/** Per-vessel point-in-time risk, as carried by a continuous-engine snapshot. */
export interface RiskEntry {
  name: string | null;
  type: string;
  risk: number;
  sar: number;
  live: number;
  confidence: number;
  prior_days: number;
  contributions: Record<string, number>;
  explanation: string;
}

/** One re-tasking instant: the top-N cells to point satellites at, plus the
 *  point-in-time risk of every scored vessel. */
export interface Snapshot {
  at: string;
  at_ts: number;
  dark_contacts: number;
  taskings: ZoneCue[];
  risk: Record<string, RiskEntry>;
}

/** The continuous engine for a scenario: N satellites re-tasked every cadence_h
 *  hours across a lead-up window. Replaces the single magic cue. */
export interface Timeseries {
  id: string;
  label: string;
  sensor: string;
  bbox: [number, number, number, number];
  hero_mmsi: number | null;
  cadence_h: number;
  n_sat: number;
  window: [string, string];
  hero_caught_at: string | null;
  snapshots: Snapshot[];
}

/** What the app renders at the current clock instant — abstracts over a
 *  continuous time-series (C-Lion1) and a single-snapshot scenario (Nord Stream). */
export interface Frame {
  scenarioId: string;
  label: string;
  heroMmsi: number | null;
  at: string;
  riskMap: Map<number, RiskEntry>;
  taskings: ZoneCue[];
  darkContacts: DarkContact[];
  isTimeseries: boolean;
  cadenceH: number | null;
  nSat: number | null;
  nextRetaskTs: number | null;
  caughtAt: string | null;
}

interface ScenarioIndex {
  scenarios: { id: string; has_timeseries?: boolean }[];
}

export interface CueData {
  scenarios: ScenarioPayload[];
  timeseries: Timeseries[];
}

const BASE = "/data/cues";

/** Load the index, every single-snapshot payload, and every continuous
 *  time-series (a couple of MB total, once). */
export async function loadCues(): Promise<CueData> {
  const idxRes = await fetch(`${BASE}/index.json`, { cache: "no-store" });
  if (!idxRes.ok) throw new Error(`cues index: HTTP ${idxRes.status}`);
  const idx = (await idxRes.json()) as ScenarioIndex;
  const scenarios = await Promise.all(
    idx.scenarios.map(async (s) => (await (await fetch(`${BASE}/${s.id}.json`, { cache: "no-store" })).json()) as ScenarioPayload),
  );
  const timeseries = await Promise.all(
    idx.scenarios
      .filter((s) => s.has_timeseries)
      .map(async (s) => (await (await fetch(`${BASE}/${s.id}-timeseries.json`, { cache: "no-store" })).json()) as Timeseries),
  );
  return { scenarios, timeseries };
}

// ---- live backend (continuous scoring outside the precomputed windows) --------

const BACKEND = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8077";
const LIVE_CADENCE_MS = 3 * 3600 * 1000; // snap to the engine's 3h cadence → cacheable
const liveCache = new Map<number, Frame | null>();
const livePending = new Map<number, Promise<Frame | null>>();

function snapshotToFrame(snap: any): Frame {
  const riskMap = new Map<number, RiskEntry>();
  for (const k in snap.risk) riskMap.set(Number(k), snap.risk[k]);
  return {
    scenarioId: "live", label: "Live · Baltic theatre", heroMmsi: null, at: snap.at,
    riskMap, taskings: snap.taskings ?? [], darkContacts: snap.dark_contacts ?? [],
    isTimeseries: true, cadenceH: snap.cadence_h ?? 3, nSat: snap.n_sat ?? 3,
    nextRetaskTs: snap.next_retask_ts ? snap.next_retask_ts * 1000 : null, caughtAt: null,
  };
}

/** Fetch the engine's frame at `clockT` from the live backend, snapped to the
 *  re-tasking cadence and cached per snapped instant (so playback within a window
 *  and re-visits are free). Returns null if the backend is unreachable. */
export function fetchLiveFrame(clockT: number): Promise<Frame | null> {
  const snapped = Math.floor(clockT / LIVE_CADENCE_MS) * LIVE_CADENCE_MS;
  if (liveCache.has(snapped)) return Promise.resolve(liveCache.get(snapped)!);
  const inflight = livePending.get(snapped);
  if (inflight) return inflight;
  const p = fetch(`${BACKEND}/frame?at=${new Date(snapped).toISOString()}`, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => (j ? snapshotToFrame(j) : null))
    .then((f) => { liveCache.set(snapped, f); livePending.delete(snapped); return f; })
    .catch(() => { livePending.delete(snapped); return null; });
  livePending.set(snapped, p);
  return p;
}

/** Has the frame for `clockT`'s 3h window already been fetched? (So the caller can
 *  skip the "scoring…" spinner for an instant, cached swap.) */
export function isLiveCached(clockT: number): boolean {
  const snapped = Math.floor(clockT / LIVE_CADENCE_MS) * LIVE_CADENCE_MS;
  return liveCache.has(snapped);
}

/** Is `clockT` covered by a precomputed time-series window? (If so, no backend.) */
export function inPrecomputedWindow(clockT: number, data: CueData): boolean {
  return data.timeseries.some((ts) => {
    const start = Date.parse(ts.window[0]);
    const end = Date.parse(ts.window[1]) + ts.cadence_h * 3600 * 1000;
    return clockT >= start && clockT <= end;
  });
}

function riskEntryFromVessel(v: TheatreVessel): RiskEntry {
  return {
    name: v.name, type: v.type, risk: v.vessel_risk, sar: v.sar, live: v.live_anomaly,
    confidence: v.breakdown.confidence, prior_days: v.breakdown.prior_days,
    contributions: v.breakdown.contributions, explanation: v.breakdown.explanation,
  };
}

/** The frame to render at `clockT`: a continuous snapshot if a time-series window
 *  covers the clock (latest re-tasking ≤ clock — no look-ahead), else a
 *  single-snapshot scenario on its day, else null (outside any scored window). */
export function frameAt(clockT: number, data: CueData): Frame | null {
  for (const ts of data.timeseries) {
    const start = Date.parse(ts.window[0]);
    const end = Date.parse(ts.window[1]) + ts.cadence_h * 3600 * 1000;
    if (clockT < start || clockT > end) continue;
    let snap: Snapshot | null = null;
    let idx = -1;
    for (let i = 0; i < ts.snapshots.length; i++) {
      if (ts.snapshots[i].at_ts * 1000 <= clockT) {
        snap = ts.snapshots[i];
        idx = i;
      } else break;
    }
    if (!snap) continue;
    const riskMap = new Map<number, RiskEntry>();
    for (const k in snap.risk) riskMap.set(Number(k), snap.risk[k]);
    const next = ts.snapshots[idx + 1];
    return {
      scenarioId: ts.id, label: ts.label, heroMmsi: ts.hero_mmsi, at: snap.at,
      riskMap, taskings: snap.taskings, darkContacts: [], isTimeseries: true,
      cadenceH: ts.cadence_h, nSat: ts.n_sat,
      nextRetaskTs: next ? next.at_ts * 1000 : null, caughtAt: ts.hero_caught_at,
    };
  }
  const tsIds = new Set(data.timeseries.map((t) => t.id));
  const day = dayKey(clockT);
  const scn = data.scenarios.find(
    (s) => !tsIds.has(s.id) && dayKey(Date.parse(s.at)) === day && clockT >= s.at_ts * 1000,
  );
  if (scn) {
    const riskMap = new Map<number, RiskEntry>();
    for (const v of scn.theatre) riskMap.set(v.mmsi, riskEntryFromVessel(v));
    return {
      scenarioId: scn.id, label: scn.label, heroMmsi: scn.hero_mmsi, at: scn.at,
      riskMap, taskings: scn.cues, darkContacts: scn.dark_contacts, isTimeseries: false,
      cadenceH: null, nSat: null, nextRetaskTs: null, caughtAt: null,
    };
  }
  return null;
}
