/**
 * Track store — replays real AIS by interpolating between keyframes.
 *
 * Tiles are the STITCHED tiles (`scripts/ingest/stitch_tracks.py`): de-spiked,
 * with global gaps and a shared keyframe at every midnight a vessel crosses. So
 * each day-tile is self-contained and aligns exactly with its neighbours at the
 * seam — the app renders ONE tile, no runtime stitching, continuous by
 * construction. (All the old cross-tile merge logic now lives in the build.)
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

// A residual MMSI-collision can still leave a segment implying impossible speed;
// freeze rather than streak the vessel across the map. (Spikes are de-spiked in
// the build; this is just a render-time safety net.)
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

function bearing(lon0: number, lat0: number, lon1: number, lat1: number): number {
  const coslat = Math.cos((((lat0 + lat1) / 2) * Math.PI) / 180);
  const dx = (lon1 - lon0) * coslat;
  const dy = lat1 - lat0;
  if (dx === 0 && dy === 0) return NaN;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

/** Interpolate every vessel's fix at instant `t` (epoch seconds) within one tile. */
function positionsFrom(vessels: RawVessel[], t: number): VesselFix[] {
  const out: VesselFix[] = [];
  for (const v of vessels) {
    const kf = v.kf;
    const n = kf.length;
    if (n === 0 || t < kf[0][0] || t > kf[n - 1][0]) continue;

    let lo = 0,
      hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (kf[mid][0] <= t) lo = mid;
      else hi = mid;
    }
    const a = kf[lo];
    const b = kf[hi];

    // Across an AIS gap (we don't know the path) or an implausible segment, hold
    // at the last fix and fade out as the gap elapses — never glide through land.
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
 * Windowed tile streaming — one day-tile per UTC day, LRU-cached, with the next
 * and previous day prefetched so the midnight tile-switch is instant. Because the
 * tiles are stitched (shared seam keyframes), rendering just the current day is
 * continuous — no merge.
 */
export class TileManager {
  private tiles = new Map<string, TrackStore>();
  private loading = new Set<string>();
  private missing = new Set<string>();
  private maxResident = 8;
  private lastFleet: VesselFix[] = [];

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

  positionsAt(tMs: number): VesselFix[] {
    const key = dayKey(tMs);
    void this.fetchDay(key);
    void this.fetchDay(dayKey(tMs + 86_400_000)); // prefetch next day
    void this.fetchDay(dayKey(tMs - 86_400_000)); // ...and previous (scrubbing back)
    const store = this.tiles.get(key);
    if (store) {
      this.lastFleet = store.positionsAt(Math.floor(tMs / 1000));
      return this.lastFleet;
    }
    // Day still streaming → hold the last frame so the fleet doesn't blink while a
    // tile loads; only blank if the day genuinely has no tile.
    return this.missing.has(key) ? [] : this.lastFleet;
  }

  status(tMs: number): "ready" | "loading" | "missing" {
    const key = dayKey(tMs);
    if (this.tiles.has(key)) return "ready";
    if (this.missing.has(key)) return "missing";
    return "loading";
  }
}
