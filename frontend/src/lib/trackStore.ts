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
  dark: boolean; // inside an AIS gap
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

export class TrackStore {
  private vessels: RawVessel[] = [];
  meta: TrackTile["meta"] | null = null;

  async load(url: string): Promise<void> {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    const tile = (await res.json()) as TrackTile;
    this.vessels = tile.vessels;
    this.meta = tile.meta;
  }

  get window(): [number, number] | null {
    return this.meta ? [this.meta.start, this.meta.end] : null;
  }

  /** All vessels present at instant `t` (epoch seconds), interpolated. */
  positionsAt(t: number): VesselFix[] {
    const out: VesselFix[] = [];
    for (const v of this.vessels) {
      const kf = v.kf;
      const n = kf.length;
      if (n === 0 || t < kf[0][0] || t > kf[n - 1][0]) continue;

      // binary search for segment [i, i+1] with kf[i].t <= t <= kf[i+1].t
      let lo = 0,
        hi = n - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (kf[mid][0] <= t) lo = mid;
        else hi = mid;
      }
      const a = kf[lo];
      const b = kf[hi];
      const span = b[0] - a[0] || 1;
      const f = Math.max(0, Math.min(1, (t - a[0]) / span));
      const lon = a[1] + (b[1] - a[1]) * f;
      const lat = a[2] + (b[2] - a[2]) * f;
      const sog = a[3] + (b[3] - a[3]) * f;
      const brg = bearing(a[1], a[2], b[1], b[2]);
      const cog = Number.isNaN(brg) ? a[4] : brg;

      let dark = false;
      for (const [g0, g1] of v.gaps) {
        if (t >= g0 && t <= g1) {
          dark = true;
          break;
        }
      }

      const shipType = (SHIP_TYPES.has(v.type as ShipType) ? v.type : "unknown") as ShipType;
      out.push({ mmsi: v.mmsi, name: v.name, shipType, lon, lat, cog, sog, dark });
    }
    return out;
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
    void this.fetchDay(key);
    void this.fetchDay(dayKey(tMs + 86_400_000)); // prefetch next day
    const store = this.tiles.get(key);
    return store ? store.positionsAt(Math.floor(tMs / 1000)) : [];
  }

  status(tMs: number): "ready" | "loading" | "missing" {
    const key = dayKey(tMs);
    if (this.tiles.has(key)) return "ready";
    if (this.missing.has(key)) return "missing";
    return "loading";
  }
}
