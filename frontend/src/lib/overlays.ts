/**
 * Thematic overlay model — what the layer panel toggles and the map renders.
 *
 *   Geography       country borders · territorial seas (12nm) · EEZ
 *                   (rescue/SRR zones: no open dataset found yet — TODO)
 *   Infrastructure  Energy · Telecom · Transport · Military (POI cats + lines)
 *   Vessels         filter by class group + labels
 *   Analysis        the unified strategic heatmap
 */
import type { ShipType } from "../types/models";

export interface OverlayState {
  geo: { borders: boolean; territorial: boolean; eez: boolean };
  infra: { energy: boolean; telecom: boolean; transport: boolean; military: boolean };
  vessels: {
    cargo: boolean;
    tanker: boolean;
    fishing: boolean;
    passenger: boolean;
    military: boolean;
    other: boolean;
    labels: boolean;
  };
  analysis: { heatmap: boolean };
}

export const DEFAULT_OVERLAYS: OverlayState = {
  geo: { borders: true, territorial: true, eez: true },
  infra: { energy: true, telecom: true, transport: true, military: true },
  vessels: { cargo: true, tanker: true, fishing: true, passenger: true, military: true, other: true, labels: true },
  analysis: { heatmap: false },
};

/** Infrastructure themes — which POI categories + line categories they own. */
export const INFRA_THEMES: Record<
  keyof OverlayState["infra"],
  { label: string; lines: string[]; pois: string[] }
> = {
  energy: {
    label: "Energy (pipelines · terminals · platforms · wind)",
    lines: ["pipeline", "power_cable"],
    pois: ["energy_terminal", "platform", "windfarm"],
  },
  telecom: { label: "Telecom (submarine cables)", lines: ["telecom_cable"], pois: [] },
  transport: {
    label: "Transport (ports · anchorages · lights · chokepoints)",
    lines: [],
    pois: ["port", "anchorage", "lighthouse", "chokepoint"],
  },
  military: { label: "Military (naval bases)", lines: [], pois: ["naval_base"] },
};

export type VesselGroup = Exclude<keyof OverlayState["vessels"], "labels">;

/** Ship class → filter group. */
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
