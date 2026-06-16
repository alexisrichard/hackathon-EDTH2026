/**
 * Thematic overlay model — what the layer panel toggles and the map renders.
 *
 *   Geography       country borders · territorial seas (12nm) · EEZ
 *   Infrastructure  per-category toggles grouped under Energy · Telecom ·
 *                   Transport · Military (each theme has a select-all master)
 *   Vessels         filter by class group + labels
 *   Analysis        the unified strategic heatmap
 */
import type { ShipType } from "../types/models";

// ---- infrastructure: one toggle per real category, grouped by theme --------
export type InfraCat =
  | "telecom_cable"
  | "power_cable"
  | "pipeline"
  | "power_plant"
  | "converter"
  | "energy_terminal"
  | "platform"
  | "windfarm"
  | "port"
  | "anchorage"
  | "shipping_lane"
  | "naval_base"
  | "restricted_zone";

export type InfraKind = "line" | "point" | "zone";
export type InfraTheme = "Energy" | "Telecom" | "Transport" | "Military";

export interface InfraCatMeta {
  theme: InfraTheme;
  label: string;
  kind: InfraKind;
}

export const INFRA_CATS: Record<InfraCat, InfraCatMeta> = {
  pipeline: { theme: "Energy", label: "Pipelines", kind: "line" },
  power_cable: { theme: "Energy", label: "Power cables", kind: "line" },
  power_plant: { theme: "Energy", label: "Power plants (incl. nuclear)", kind: "point" },
  converter: { theme: "Energy", label: "HVDC converters", kind: "point" },
  energy_terminal: { theme: "Energy", label: "Terminals / refineries", kind: "point" },
  platform: { theme: "Energy", label: "Offshore platforms", kind: "point" },
  windfarm: { theme: "Energy", label: "Wind farms", kind: "point" },
  telecom_cable: { theme: "Telecom", label: "Submarine cables", kind: "line" },
  port: { theme: "Transport", label: "Ports (commercial/naval)", kind: "point" },
  shipping_lane: { theme: "Transport", label: "Shipping lanes (TSS)", kind: "line" },
  anchorage: { theme: "Transport", label: "Anchorages", kind: "point" },
  naval_base: { theme: "Military", label: "Naval bases", kind: "point" },
  restricted_zone: { theme: "Military", label: "Restricted / exercise zones", kind: "zone" },
};

export const INFRA_CAT_KEYS = Object.keys(INFRA_CATS) as InfraCat[];
export const INFRA_THEME_ORDER: InfraTheme[] = ["Energy", "Telecom", "Transport", "Military"];

export function catsInTheme(theme: InfraTheme): InfraCat[] {
  return INFRA_CAT_KEYS.filter((c) => INFRA_CATS[c].theme === theme);
}

export type InfraState = Record<InfraCat, boolean>;

export interface OverlayState {
  geo: { borders: boolean; territorial: boolean; eez: boolean };
  infra: InfraState;
  vessels: {
    cargo: boolean;
    tanker: boolean;
    fishing: boolean;
    passenger: boolean;
    military: boolean;
    other: boolean;
    labels: boolean;
  };
  fishing: { intensity: boolean };
  analysis: { heatmap: boolean };
  /** The cueing engine's live output: task-next boxes + SAR dark-vessel detections. */
  cueing: { cues: boolean; sar: boolean };
  /** Dev-only diagnostics: the 9 known incidents + where we actually have AIS. */
  incidentsDev: { points: boolean; coverage: boolean };
}

/** Everything-on preset — the full layer set. Not the startup state (that's the
 *  focused DEFAULT_OVERLAYS below); kept for reference / a future "show all". */
export const ALL_OVERLAYS: OverlayState = {
  geo: { borders: true, territorial: true, eez: true },
  infra: {
    telecom_cable: true,
    power_cable: true,
    pipeline: true,
    power_plant: true,
    converter: true,
    energy_terminal: true,
    platform: true,
    windfarm: true,
    port: true,
    shipping_lane: true,
    anchorage: false, // off by default — shadow-fleet loitering context, toggle on as needed
    naval_base: true,
    restricted_zone: true,
  },
  vessels: { cargo: true, tanker: true, fishing: true, passenger: true, military: true, other: true, labels: true },
  fishing: { intensity: false }, // big contextual heatmap — off by default
  analysis: { heatmap: false },
  cueing: { cues: true, sar: true },
  incidentsDev: { points: false, coverage: false }, // dev diagnostics — off by default
};

/**
 * The startup default + the panel's "Default view" preset: only the relevant
 * ships (everything but Other) plus the two cut-prone infra lines — telecom
 * cables + pipelines. Everything else (geography, other infra, fishing/analysis/
 * dev overlays) off.
 */
export const DEFAULT_OVERLAYS: OverlayState = {
  geo: { borders: false, territorial: false, eez: false },
  infra: {
    telecom_cable: true,
    pipeline: true,
    power_cable: false,
    power_plant: false,
    converter: false,
    energy_terminal: false,
    platform: false,
    windfarm: false,
    port: false,
    shipping_lane: false,
    anchorage: false,
    naval_base: false,
    restricted_zone: false,
  },
  vessels: { cargo: true, tanker: true, fishing: true, passenger: true, military: true, other: false, labels: true },
  fishing: { intensity: false },
  analysis: { heatmap: false },
  cueing: { cues: true, sar: true }, // the product — on by default
  incidentsDev: { points: false, coverage: false },
};

/** Enabled categories of a given render kind. */
export function enabledCats(infra: InfraState, kind: InfraKind): Set<string> {
  return new Set(INFRA_CAT_KEYS.filter((c) => INFRA_CATS[c].kind === kind && infra[c]));
}

// ---- vessels ---------------------------------------------------------------
export type VesselGroup = Exclude<keyof OverlayState["vessels"], "labels">;

export const VESSEL_GROUPS: Record<ShipType, VesselGroup> = {
  cargo: "cargo",
  dredger: "cargo",
  tanker: "tanker",
  fishing: "fishing",
  passenger: "passenger",
  ropax: "passenger",
  high_speed: "passenger",
  military: "military",
  law_enforcement: "military",
  search_and_rescue: "military",
  tug: "other",
  pilot: "other",
  port_tender: "other",
  anti_pollution: "other",
  pleasure: "other",
  research: "other",
  wing_in_ground: "other",
  other: "other",
  unknown: "other",
};

export const VESSEL_GROUP_LABELS: Record<VesselGroup, string> = {
  cargo: "Cargo / bulk",
  tanker: "Tankers",
  fishing: "Fishing",
  passenger: "Passenger / RoPax",
  military: "Military / gov",
  other: "Other",
};
