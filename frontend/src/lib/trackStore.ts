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
