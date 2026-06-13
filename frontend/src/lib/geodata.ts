/**
 * Static map layers compiled by scripts/geo/build_web_layers.py into
 * frontend/public/data/. Each feature carries a v1 strategic score `s` (0-1)
 * — the seed of the unified criticality "heat score" (PLAN §5.2).
 */

import type { Feature, FeatureCollection, Geometry, Point } from "geojson";

export type GeoFeature = Feature<Geometry, Record<string, unknown>>;
export type FC = FeatureCollection<Geometry, Record<string, unknown>>;

export interface GeoLayers {
  jurisdiction: FC;
  infra: FC;
  poi: FC;
  zones: FC;
}

async function fetchJson(path: string): Promise<FC> {
  // no-store so a `build_web_layers.py` rebuild shows up on a normal reload
  // (Vite doesn't HMR files under public/, and the browser would otherwise
  // serve a stale cached copy).
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as FC;
}

export async function loadGeoLayers(): Promise<GeoLayers> {
  const [jurisdiction, infra, poi, zones] = await Promise.all([
    fetchJson("/data/jurisdiction.json"),
    fetchJson("/data/infra_lines.json"),
    fetchJson("/data/poi.json"),
    fetchJson("/data/zones.json"),
  ]);
  return { jurisdiction, infra, poi, zones };
}

/** Pull [lon, lat] out of a Point feature (poi.json is points-only). */
export function pointCoords(f: GeoFeature): [number, number] {
  return (f.geometry as Point).coordinates as [number, number];
}

export const CAT_LABELS: Record<string, string> = {
  telecom_cable: "Telecom cable",
  power_cable: "Power cable",
  pipeline: "Pipeline",
  naval_base: "Naval base",
  energy_terminal: "Energy terminal",
  power_plant: "Power plant",
  converter: "HVDC converter",
  restricted_zone: "Restricted / exercise zone",
  port: "Port",
  windfarm: "Wind farm",
  platform: "Platform",
  anchorage: "Anchorage",
};
