/**
 * TypeScript mirror of the backend pydantic domain models (1:1).
 *
 * Source of truth is `backend/app/models/`. Keep these in sync — the API
 * contract (`shared/api_contract.md`) is the agreed shape. Conventions: coords
 * are `[lon, lat]` (EPSG:4326), times are ISO-8601 UTC strings.
 */

// ---- Enums (mirror backend/app/models/enums.py) --------------------------------

/** Normalized vessel class. Keys of the shared `ship_type_to_shape` encoding. */
export type ShipType =
  | "tanker"
  | "cargo"
  | "fishing"
  | "passenger"
  | "ropax"
  | "tug"
  | "pleasure"
  | "high_speed"
  | "military"
  | "law_enforcement"
  | "search_and_rescue"
  | "research"
  | "dredger"
  | "pilot"
  | "port_tender"
  | "anti_pollution"
  | "wing_in_ground"
  | "other"
  | "unknown";

/** Normalized navigational status. */
export type NavStatus =
  | "under_way_using_engine"
  | "under_way_sailing"
  | "at_anchor"
  | "moored"
  | "aground"
  | "engaged_in_fishing"
  | "restricted_maneuverability"
  | "constrained_by_draught"
  | "not_under_command"
  | "unknown";

/** ISR sensor a cue recommends tasking. */
export type SensorType = "SAR" | "optical" | "AIS" | "DAS";

/** Discrete suspicion bands for legends / alert grouping. */
export type SuspicionBand = "calm" | "watch" | "elevated" | "high" | "critical";

/** A bbox is [min_lon, min_lat, max_lon, max_lat], EPSG:4326. */
export type BBox = [number, number, number, number];

/** RGB triple [r, g, b], each 0–255. */
export type RGB = [number, number, number];

// ---- Vessel (mirror vessel.py) -------------------------------------------------

export interface Vessel {
  mmsi: number;
  name: string | null;
  imo: number | null;
  callsign: string | null;
  ship_type: ShipType;
  cargo_type: string | null;
  length: number | null;
  width: number | null;
  draught: number | null;
  flag: string | null;
  destination: string | null;
}

export interface VesselPosition {
  /** ISO-8601 UTC timestamp. */
  t: string;
  lon: number;
  lat: number;
  sog: number | null;
  cog: number | null;
  heading: number | null;
  nav_status: NavStatus;
}

export interface VesselTrack {
  vessel: Vessel;
  /** Positions ordered ascending by time. */
  track: VesselPosition[];
}

// ---- Scoring (mirror scoring.py) -----------------------------------------------

export interface ScoreBreakdown {
  kinematic_anomaly: number;
  /** 1 = perfectly normal, 0 = totally incoherent. Formula uses (1 − this). */
  class_coherence: number;
  local_criticality: number;
  dark_modifier: number;
  why: string;
  /** Composite suspicion in [0, 1] (computed field on the backend). */
  suspicion: number;
}

export interface DisplayHints {
  /** deck.gl shape key derived from ship_type. */
  shape: string;
  /** RGB derived from the suspicion score. */
  color: RGB;
  /** Same color as a #rrggbb string. */
  color_hex: string;
  band: SuspicionBand;
}

export interface ScoredVessel {
  vessel: Vessel;
  /** Instant the score is evaluated at (ISO-8601 UTC). */
  t: string;
  position: VesselPosition;
  breakdown: ScoreBreakdown;
  display: DisplayHints;
}

// ---- Geo / cueing (mirror geo.py) ----------------------------------------------

export interface GridCell {
  cell_id: string;
  bbox: BBox;
  h3: string | null;
  /** Static strategic importance (1 = over a cable/base). */
  criticality: number;
  /** Dynamic value-of-tasking score. */
  cue_score: number;
  driver_mmsis: number[];
}

export interface CriticalityGrid {
  t: string;
  bbox: BBox;
  cells: GridCell[];
}

export interface CueRecommendation {
  rank: number;
  cell_id: string | null;
  bbox: BBox;
  t: string;
  sensor: SensorType;
  score: number;
  driver_mmsis: number[];
  why: string;
}

// ---- Scenario / incident (mirror scenario.py) ----------------------------------

export interface Scenario {
  id: string;
  name: string;
  start: string;
  end: string;
  bbox: BBox;
  suspect_mmsi: number | null;
  incident_id: string | null;
  narrative: string | null;
  held_out: boolean;
}

export interface Incident {
  incident_id: string;
  name: string;
  date_utc: string;
  time_utc: string | null;
  lat: number;
  lon: number;
  vessel_name: string | null;
  vessel_flag: string | null;
  vessel_type: string | null;
  infrastructure_name: string | null;
  infrastructure_type: string | null;
  region: string | null;
  attribution_status: string | null;
  narrative: string | null;
  sources: string[];
}

// ---- Response envelopes (mirror responses.py) ----------------------------------

export interface VesselsResponse {
  vessels: VesselTrack[];
}
export interface ScoresResponse {
  /** Evaluated instant echoed back (ISO-8601 UTC); null when there are no results. */
  t: string | null;
  scores: ScoredVessel[];
}
export interface CuesResponse {
  /** Evaluated instant echoed back (ISO-8601 UTC); null when there are no results. */
  t: string | null;
  cues: CueRecommendation[];
}
export interface ScenariosResponse {
  scenarios: Scenario[];
}
export interface IncidentsResponse {
  incidents: Incident[];
}
export interface GeoResponse {
  grid: CriticalityGrid;
}
export interface HealthResponse {
  status: string;
  data_source: string;
  version: string;
}
