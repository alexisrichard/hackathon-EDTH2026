/**
 * In-browser mock AIS fleet, conforming to the shared contract types.
 *
 * - EAGLE S: scripted recreation of the 2024-12-25 Estlink 2 incident — the
 *   same arc the backend MockDataSource serves (slows over the cable,
 *   suspicion climbs to critical BEFORE the 14:00Z cut).
 * - Background fleet: ~110 synthetic vessels on plausible Baltic + North Sea
 *   lanes, deterministic (seeded PRNG) so every reload replays identically.
 *
 * Everything is a pure function of sim time `t`, so scrubbing re-ranks the
 * world instantly. Swap with the typed API client (src/api) when live.
 */
import type { ShipType } from "../types/models";
import { BREACH_T } from "../lib/clock";

export interface MockVesselState {
  mmsi: number;
  name: string;
  shipType: ShipType;
  lon: number;
  lat: number;
  cog: number; // deg, clockwise from north
  sog: number; // knots
  suspicion: number; // 0-1
  why: string;
}

// ---------- deterministic PRNG ----------
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- geometry helpers ----------
const KM_PER_DEG_LAT = 111.32;
const kmPerDegLon = (lat: number) => KM_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);

function segKm(a: [number, number], b: [number, number]): number {
  const midLat = (a[1] + b[1]) / 2;
  const dx = (b[0] - a[0]) * kmPerDegLon(midLat);
  const dy = (b[1] - a[1]) * KM_PER_DEG_LAT;
  return Math.hypot(dx, dy);
}

function bearing(a: [number, number], b: [number, number]): number {
  const midLat = (a[1] + b[1]) / 2;
  const dx = (b[0] - a[0]) * kmPerDegLon(midLat);
  const dy = (b[1] - a[1]) * KM_PER_DEG_LAT;
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}

interface Polyline {
  pts: [number, number][];
  cum: number[]; // cumulative km
  total: number;
}

function polyline(pts: [number, number][]): Polyline {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + segKm(pts[i - 1], pts[i]));
  return { pts, cum, total: cum[cum.length - 1] };
}

/** Position + course at distance `d` km along the line (ping-pong on overflow). */
function along(line: Polyline, d: number): { lon: number; lat: number; cog: number } {
  const L = line.total;
  let x = d % (2 * L);
  if (x < 0) x += 2 * L;
  const fwd = x <= L;
  if (!fwd) x = 2 * L - x;
  let i = 1;
  while (i < line.cum.length - 1 && line.cum[i] < x) i++;
  const a = line.pts[i - 1];
  const b = line.pts[i];
  const span = line.cum[i] - line.cum[i - 1] || 1e-6;
  const f = (x - line.cum[i - 1]) / span;
  const lon = a[0] + (b[0] - a[0]) * f;
  const lat = a[1] + (b[1] - a[1]) * f;
  const brg = bearing(a, b);
  return { lon, lat, cog: ((fwd ? brg : brg + 180) + 360) % 360 };
}

// ---------- shipping lanes (Baltic + North Sea) ----------
interface Lane {
  name: string;
  pts: [number, number][];
  n: number; // vessels on this lane
  types: ShipType[];
}

const LANES: Lane[] = [
  { name: "Gulf of Finland E-W", n: 16, types: ["tanker", "cargo", "tanker", "cargo", "other"],
    pts: [[24.0, 59.45], [25.5, 59.75], [26.5, 60.0], [27.8, 60.25], [28.6, 60.4]] },
  { name: "Helsinki-Tallinn", n: 6, types: ["ropax", "passenger", "high_speed"],
    pts: [[24.95, 60.13], [24.83, 59.62]] },
  { name: "Baltic proper N-S", n: 18, types: ["cargo", "tanker", "cargo", "fishing"],
    pts: [[19.2, 59.2], [19.6, 57.9], [19.0, 56.5], [18.6, 55.5], [16.2, 55.0], [14.4, 54.8]] },
  { name: "Bornholm gate", n: 12, types: ["tanker", "cargo", "tanker"],
    pts: [[12.6, 54.7], [14.2, 54.9], [15.7, 55.2], [17.5, 55.5], [19.5, 55.9]] },
  { name: "Oresund", n: 8, types: ["cargo", "ropax", "tanker", "pleasure"],
    pts: [[12.65, 55.55], [12.75, 55.85], [12.6, 56.1], [12.3, 56.4]] },
  { name: "Kattegat-Skagerrak", n: 12, types: ["tanker", "cargo", "fishing"],
    pts: [[11.9, 56.3], [11.5, 57.0], [10.8, 57.7], [9.5, 58.0], [7.8, 57.9]] },
  { name: "Gulf of Riga", n: 6, types: ["cargo", "fishing", "other"],
    pts: [[23.6, 57.3], [23.0, 57.8], [22.3, 58.2]] },
  { name: "Gulf of Bothnia", n: 7, types: ["cargo", "tanker", "other"],
    pts: [[19.5, 60.5], [19.9, 61.8], [20.7, 63.0], [21.5, 64.2]] },
  { name: "German Bight", n: 12, types: ["cargo", "tanker", "cargo", "dredger"],
    pts: [[3.5, 51.9], [4.8, 52.6], [6.2, 53.6], [7.8, 54.0], [7.9, 53.6]] },
  { name: "North Sea S-N", n: 12, types: ["tanker", "cargo", "fishing", "other"],
    pts: [[2.2, 51.5], [2.8, 53.0], [3.8, 54.8], [4.8, 56.5], [5.8, 58.2], [7.0, 57.95]] },
];

const SHIP_NAMES = [
  "BALTIC ROSE", "NORDLAND", "CELESTINE", "VEGA STAR", "MERIDIAN", "OSTSEE QUEEN",
  "KOTKA TRADER", "AMBER WAVE", "POLARIS", "SILVER GULL", "HANKO EXPRESS", "TRITON",
  "KALEVALA", "WESTWIND", "GOTLAND CARRIER", "AALAND", "BORE SONG", "NEPTUNUS",
  "LAGUNA BELLE", "STORM PETREL", "RIGEL", "ESBJERG STAR", "FRISIAN PRIDE", "SKAGEN",
];

interface BgVessel {
  mmsi: number;
  name: string;
  shipType: ShipType;
  line: Polyline;
  phase: number;
  kn: number;
  dir: 1 | -1;
  base: number; // baseline suspicion
}

function buildFleet(): BgVessel[] {
  const rand = mulberry32(20261225);
  const fleet: BgVessel[] = [];
  let mmsi = 230000001;
  let nameIdx = 0;
  for (const lane of LANES) {
    const line = polyline(lane.pts);
    for (let i = 0; i < lane.n; i++) {
      const shipType = lane.types[Math.floor(rand() * lane.types.length)];
      const named = rand() < 0.35;
      fleet.push({
        mmsi: mmsi++,
        name: named ? SHIP_NAMES[nameIdx++ % SHIP_NAMES.length] : `MMSI ${mmsi}`,
        shipType,
        line,
        phase: rand() * line.total * 2,
        kn: 7 + rand() * 12,
        dir: rand() < 0.5 ? 1 : -1,
        base: rand() < 0.06 ? 0.28 + rand() * 0.17 : 0.01 + rand() * 0.16,
      });
    }
  }
  return fleet;
}

const FLEET = buildFleet();

// ---------- EAGLE S — the scripted incident ----------
export const EAGLE_S_MMSI = 372985000;

/** Estlink 2 crossing point the mock slows over (matches backend scenario). */
export const ESTLINK_CROSS: [number, number] = [26.36, 59.93];

/** Cue box around the crossing — the SAR tasking recommendation. */
export const CUE_BBOX: [number, number, number, number] = [26.2, 59.84, 26.52, 60.02];
export const CUE_FIRES_T = Date.UTC(2024, 11, 25, 13, 35, 0);

const EAGLE_WAYPOINTS: [number, number, number, number][] = [
  // [t, lon, lat, sog]
  [Date.UTC(2024, 11, 25, 10, 0, 0), 28.35, 60.3, 10.5],
  [Date.UTC(2024, 11, 25, 11, 30, 0), 27.4, 60.12, 10.0],
  [Date.UTC(2024, 11, 25, 12, 45, 0), 26.75, 60.0, 7.0],
  [Date.UTC(2024, 11, 25, 13, 20, 0), 26.5, 59.96, 3.0],
  [Date.UTC(2024, 11, 25, 14, 5, 0), 26.3, 59.92, 1.8],
  [Date.UTC(2024, 11, 25, 16, 0, 0), 25.3, 59.75, 9.0],
];

function eagleAt(t: number): MockVesselState {
  const wp = EAGLE_WAYPOINTS;
  let i = 1;
  while (i < wp.length - 1 && wp[i][0] < t) i++;
  const [t0, lon0, lat0, s0] = wp[i - 1];
  const [t1, lon1, lat1, s1] = wp[i];
  const f = Math.max(0, Math.min(1, (t - t0) / (t1 - t0)));
  const lon = lon0 + (lon1 - lon0) * f;
  const lat = lat0 + (lat1 - lat0) * f;
  const sog = s0 + (s1 - s0) * f;
  const cog = bearing([lon0, lat0], [lon1, lat1]);

  // suspicion arc: calm -> watch (cue fires 13:35) -> critical before 14:00 cut
  const ramp = (a: number, b: number, va: number, vb: number) =>
    va + (vb - va) * Math.max(0, Math.min(1, (t - a) / (b - a)));
  let suspicion: number;
  if (t < Date.UTC(2024, 11, 25, 12, 30, 0)) suspicion = 0.02;
  else if (t < CUE_FIRES_T) suspicion = ramp(Date.UTC(2024, 11, 25, 12, 30, 0), CUE_FIRES_T, 0.02, 0.5);
  else if (t < BREACH_T) suspicion = ramp(CUE_FIRES_T, BREACH_T, 0.5, 0.91);
  else suspicion = Math.min(0.93, ramp(BREACH_T, BREACH_T + 30 * 60e3, 0.91, 0.93));

  const why =
    suspicion < 0.25
      ? "Tanker transiting Gulf of Finland, westbound"
      : suspicion < 0.5
        ? `Decelerating on approach to Estlink 2 corridor (${sog.toFixed(1)} kn)`
        : `Declared tanker behaving like a loiterer: ${sog.toFixed(1)} kn directly over Estlink 2 (criticality 0.95), AIS gap 13 min`;

  return { mmsi: EAGLE_S_MMSI, name: "EAGLE S", shipType: "tanker", lon, lat, cog: (cog + 360) % 360, sog, suspicion, why };
}

// ---------- public API ----------
export function fleetAt(t: number): MockVesselState[] {
  const out: MockVesselState[] = [eagleAt(t)];
  const hours = (t - Date.UTC(2024, 11, 25, 0, 0, 0)) / 3600e3;
  for (const v of FLEET) {
    const d = v.phase + v.dir * v.kn * 1.852 * hours;
    const p = along(v.line, d);
    // gentle per-vessel wiggle so the rail isn't static
    const wiggle = 0.04 * Math.sin(t / 9e5 + v.mmsi % 7);
    const suspicion = Math.max(0.005, Math.min(0.49, v.base + wiggle));
    out.push({
      mmsi: v.mmsi,
      name: v.name,
      shipType: v.shipType,
      lon: p.lon,
      lat: p.lat,
      cog: p.cog,
      sog: v.kn,
      suspicion,
      why:
        suspicion >= 0.25
          ? "Course deviation from declared route; intermittent AIS"
          : "Nominal — consistent with declared class and lane",
    });
  }
  return out;
}
