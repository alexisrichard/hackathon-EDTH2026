/**
 * Track store — replays real AIS by interpolating between downsampled keyframes.
 *
 * Tiles come from scripts/ingest/build_ais_tracks.py (adaptive Douglas-Peucker
 * keyframes). The browser holds a window of tiles and reconstructs each vessel's
 * position at any instant `t` by binary-search + linear interpolation between
 * its keyframes — so a few thousand keyframes replay a full day, and the same
 * machinery scales to a 6-year archive streamed window-by-window.
 *
 * V1 loads a single day tile; the API is shaped for multi-tile windowing.
 */
import type { ShipType } from "../types/models";

// keyframe: [t_epoch_s, lon, lat, sog, cog]
type KF = [number, number, number, number, number];

interface RawVessel {
  mmsi: number;
  name: string;
  type: string;
  kf: KF[];
  gaps: [number, number][];
}

interface TrackTile {
  meta: { date: string; start: number; end: number; bbox: number[]; vessels: number; keyframes: number };
  vessels: RawVessel[];
}

export interface VesselFix {
  mmsi: number;
  name: string;
  shipType: ShipType;
  lon: number;
  lat: number;
  cog: number; // deg, from segment bearing
  sog: number; // knots
  dark: boolean; // dead-reckoned: inside an AIS gap / frozen at last known fix
  darkness: number; // 0 = live, →1 = deep into the gap (drives fade-out)
}

/** A fix plus interim suspicion — what the map + alert feed render. */
export interface ScoredVessel extends VesselFix {
  suspicion: number;
  why: string;
}

const SHIP_TYPES = new Set<ShipType>([
  "cargo", "tanker", "fishing", "passenger", "ropax", "high_speed", "military",
  "law_enforcement", "search_and_rescue", "tug", "pilot", "port_tender",
  "anti_pollution", "pleasure", "research", "wing_in_ground", "dredger", "other", "unknown",
]);

function bearing(lon0: number, lat0: number, lon1: number, lat1: number): number {
  const coslat = Math.cos((((lat0 + lat1) / 2) * Math.PI) / 180);
  const dx = (lon1 - lon0) * coslat;
  const dy = lat1 - lat0;
  if (dx === 0 && dy === 0) return NaN;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

// Above this implied speed, a segment isn't real travel — it's a bad AIS fix or
// two vessels sharing an MMSI. (Even fast ferries top out ~40 kn.)
const MAX_KNOTS = 60;
const KM_PER_NM = 1.852;

function haversineKm(lon0: number, lat0: number, lon1: number, lat1: number): number {
  const R = 6371,
    rad = Math.PI / 180;
  const dLat = (lat1 - lat0) * rad,
    dLon = (lon1 - lon0) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat0 * rad) * Math.cos(lat1 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function impliedKnots(a: KF, b: KF): number {
  const dtH = (b[0] - a[0]) / 3600;
  if (dtH <= 0) return Infinity;
  return haversineKm(a[1], a[2], b[1], b[2]) / dtH / KM_PER_NM;
}

/**
 * Drop isolated position spikes: a keyframe whose *both* neighbouring segments
 * imply impossible speed is a bad fix (or an MMSI collision) — the vessel was
 * never there. Done once at load so `positionsAt` stays a hot, simple lerp.
 */
function despike(kf: KF[]): KF[] {
  if (kf.length < 3) return kf;
  const out: KF[] = [kf[0]];
  for (let i = 1; i < kf.length - 1; i++) {
    const a = out[out.length - 1],
      b = kf[i],
      c = kf[i + 1];
    if (impliedKnots(a, b) > MAX_KNOTS && impliedKnots(b, c) > MAX_KNOTS) continue;
    out.push(b);
  }
  out.push(kf[kf.length - 1]);
  return out;
}

/**
 * Interpolate every vessel's fix at instant `t` (epoch seconds). Shared by the
 * single-day store and the cross-tile boundary merge so both interpolate, gap-
 * freeze, and fade identically.
 */
function positionsFrom(vessels: RawVessel[], t: number): VesselFix[] {
  const out: VesselFix[] = [];
  for (const v of vessels) {
    const kf = v.kf;
    const n = kf.length;
    if (n === 0 || t < kf[0][0] || t > kf[n - 1][0]) continue;

    // binary search for segment [lo, hi] with kf[lo].t <= t <= kf[hi].t
    let lo = 0,
      hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (kf[mid][0] <= t) lo = mid;
      else hi = mid;
    }
    const a = kf[lo];
    const b = kf[hi];

    // Don't draw a confident straight line we can't justify. Across an AIS gap
    // or a segment implying impossible speed, hold at the last fix and fade out.
    const segGap = v.gaps.some(([g0, g1]) => a[0] < g1 && b[0] > g0);
    const untrusted = segGap || impliedKnots(a, b) > MAX_KNOTS;

    let lon: number, lat: number, sog: number, cog: number, dark: boolean, darkness: number;
    if (untrusted) {
      lon = a[1];
      lat = a[2];
      sog = a[3];
      cog = a[4];
      dark = true;
      darkness = Math.max(0, Math.min(1, (t - a[0]) / (b[0] - a[0] || 1)));
    } else {
      const span = b[0] - a[0] || 1;
      const f = Math.max(0, Math.min(1, (t - a[0]) / span));
      lon = a[1] + (b[1] - a[1]) * f;
      lat = a[2] + (b[2] - a[2]) * f;
      sog = a[3] + (b[3] - a[3]) * f;
      const brg = bearing(a[1], a[2], b[1], b[2]);
      cog = Number.isNaN(brg) ? a[4] : brg;
      dark = false;
      darkness = 0;
    }

    const shipType = (SHIP_TYPES.has(v.type as ShipType) ? v.type : "unknown") as ShipType;
    out.push({ mmsi: v.mmsi, name: v.name, shipType, lon, lat, cog, sog, dark, darkness });
  }
  return out;
}

/**
 * Union vessels by MMSI across chronologically-ordered tiles, concatenating
 * keyframes + gaps so a vessel's track is continuous across a day boundary.
 * `ordered` is earliest-tile-first; within a tile kf is sorted and tiles don't
 * overlap in time, so the merged kf is sorted without an explicit sort.
 */
function mergeVessels(ordered: RawVessel[][]): RawVessel[] {
  const merged = new Map<number, RawVessel>();
  for (const vessels of ordered) {
    for (const v of vessels) {
      const e = merged.get(v.mmsi);
      if (e) {
        e.kf = e.kf.concat(v.kf);
        e.gaps = e.gaps.concat(v.gaps);
      } else {
        merged.set(v.mmsi, {
          mmsi: v.mmsi,
          name: v.name,
          type: v.type,
          kf: v.kf.slice(),
          gaps: v.gaps.slice(),
        });
      }
    }
  }
  return [...merged.values()];
}

export class TrackStore {
  private vessels: RawVessel[] = [];
  meta: TrackTile["meta"] | null = null;

  async load(url: string): Promise<void> {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    const tile = (await res.json()) as TrackTile;
    for (const v of tile.vessels) v.kf = despike(v.kf);
    this.vessels = tile.vessels;
    this.meta = tile.meta;
  }

  get window(): [number, number] | null {
    return this.meta ? [this.meta.start, this.meta.end] : null;
  }

  /** Read-only access to the (despiked) vessels — for cross-tile stitching. */
  get rawVessels(): RawVessel[] {
    return this.vessels;
  }

  /** All vessels present at instant `t` (epoch seconds), interpolated. */
  positionsAt(t: number): VesselFix[] {
    return positionsFrom(this.vessels, t);
  }

  vesselCount(): number {
    return this.vessels.length;
  }
}

/** UTC day key "YYYY-MM-DD" for epoch-ms t. */
function dayKey(tMs: number): string {
  return new Date(tMs).toISOString().slice(0, 10);
}

/**
 * Windowed tile streaming — loads one day-tile per UTC day on demand, caches a
 * few (LRU), prefetches the next day, and routes positionsAt() to the right
 * day's store. This is what lets the clock roam the whole 6-year archive while
 * only ~a day of keyframes is ever resident.
 */
export class TileManager {
  private tiles = new Map<string, TrackStore>();
  private loading = new Set<string>();
  private missing = new Set<string>();
  private maxResident = 8;
  private lastFleet: VesselFix[] = [];
  // Cached cross-tile merge for the current day-boundary pair (rebuilt only when
  // the pair changes, i.e. once per boundary crossing — not per frame).
  private mergedVessels: RawVessel[] | null = null;
  private mergedKey = "";

  constructor(
    private baseUrl: string,
    private onChange: () => void,
  ) {}

  private async fetchDay(key: string): Promise<void> {
    if (this.tiles.has(key) || this.loading.has(key) || this.missing.has(key)) return;
    this.loading.add(key);
    const store = new TrackStore();
    try {
      await store.load(`${this.baseUrl}/tracks_${key}.json`);
      this.tiles.set(key, store);
      // LRU evict
      while (this.tiles.size > this.maxResident) {
        const oldest = this.tiles.keys().next().value as string;
        this.tiles.delete(oldest);
      }
      this.onChange();
    } catch {
      this.missing.add(key); // 404 / no tile for this day — don't retry
    } finally {
      this.loading.delete(key);
    }
  }

  /** Vessels at instant `t` (epoch ms); loads + prefetches tiles as a side effect. */
  positionsAt(tMs: number): VesselFix[] {
    const key = dayKey(tMs);
    const nextKey = dayKey(tMs + 86_400_000);
    const prevKey = dayKey(tMs - 86_400_000);
    void this.fetchDay(key);
    void this.fetchDay(nextKey); // prefetch next day
    void this.fetchDay(prevKey); // ...and previous (scrubbing back)

    const cur = this.tiles.get(key);
    const tSec = Math.floor(tMs / 1000);

    // Near a UTC day boundary, each vessel's track is split across two tiles and
    // falls into a ~1-2 min gap where neither renders it (day-N: t > last_kf;
    // day-N+1: t < first_kf). Stitch the adjacent tile's keyframes in so the
    // track stays continuous across midnight instead of vanishing + reappearing.
    const BOUNDARY_SEC = 300;
    const intoDay = tSec - Date.parse(`${key}T00:00:00Z`) / 1000;
    const nbKey = intoDay < BOUNDARY_SEC ? prevKey : 86_400 - intoDay < BOUNDARY_SEC ? nextKey : null;
    const nb = nbKey ? this.tiles.get(nbKey) : null;

    if (cur && nb && nbKey) {
      const mk = nbKey < key ? `${nbKey}|${key}` : `${key}|${nbKey}`;
      if (this.mergedKey !== mk) {
        const ordered = nbKey < key ? [nb, cur] : [cur, nb];
        this.mergedVessels = mergeVessels(ordered.map((s) => s.rawVessels));
        this.mergedKey = mk;
      }
      this.lastFleet = positionsFrom(this.mergedVessels!, tSec);
      return this.lastFleet;
    }

    if (cur) {
      this.lastFleet = cur.positionsAt(tSec);
      return this.lastFleet;
    }
    // Day genuinely has no tile → empty. Still loading → hold the last frame so
    // the whole fleet doesn't blink out while a day-tile streams in.
    return this.missing.has(key) ? [] : this.lastFleet;
  }

  status(tMs: number): "ready" | "loading" | "missing" {
    const key = dayKey(tMs);
    if (this.tiles.has(key)) return "ready";
    if (this.missing.has(key)) return "missing";
    return "loading";
  }
}
