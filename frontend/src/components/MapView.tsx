/**
 * The theatre map: EOX Sentinel-2 cloudless basemap (MapLibre) with deck.gl
 * data layers overlaid — thematic overlays (geography / infrastructure /
 * vessels / analysis), the real interpolated AIS fleet, and the live cue box.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, IconLayer, PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import type { Layer, PickingInfo } from "@deck.gl/core";

import { colorForSensor, colorForSuspicion, shapeForShipType } from "../types/encoding";
import type { GeoLayers, GeoFeature } from "../lib/geodata";
import { CAT_LABELS, pointCoords } from "../lib/geodata";
import { buildIconAtlas, ROTATABLE } from "../lib/icons";
import { enabledCats, type OverlayState } from "../lib/overlays";
import type { ScoredVessel } from "../lib/trackStore";
import type { DarkContact, ZoneCue } from "../lib/cues";

interface Props {
  t: number;
  vessels: ScoredVessel[]; // already group-filtered + scored by App
  geo: GeoLayers | null;
  overlays: OverlayState;
  cues: ZoneCue[]; // the real ranked task-next queue
  darkContacts: DarkContact[]; // SAR detections with no AIS
  suspectMmsi: number | null;
  onMapReady: (map: maplibregl.Map) => void;
}

const EOX_ATTRIBUTION =
  '<a href="https://s2maps.eu">Sentinel-2 cloudless by EOX (CC-BY 4.0)</a> · Marine Regions (CC-BY) · © OSM (ODbL) · EMODnet';

const MAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    eox: {
      type: "raster",
      tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg"],
      tileSize: 256,
      attribution: EOX_ATTRIBUTION,
      maxzoom: 14,
    },
  },
  layers: [
    { id: "void", type: "background", paint: { "background-color": "#060A12" } },
    { id: "eox", type: "raster", source: "eox" },
  ],
};

const INFRA_COLORS: Record<string, [number, number, number, number]> = {
  telecom_cable: [65, 227, 255, 150],
  power_cable: [47, 214, 181, 165],
  pipeline: [255, 176, 46, 120],
};

/** Corner-bracket paths for the cue box (brand reticle, in map coords). */
function cueBracketPaths(b: [number, number, number, number]): [number, number][][] {
  const [x0, y0, x1, y1] = b;
  const ax = (x1 - x0) * 0.28;
  const ay = (y1 - y0) * 0.28;
  return [
    [[x0, y0 + ay], [x0, y0], [x0 + ax, y0]],
    [[x1 - ax, y0], [x1, y0], [x1, y0 + ay]],
    [[x1, y1 - ay], [x1, y1], [x1 - ax, y1]],
    [[x0 + ax, y1], [x0, y1], [x0, y1 - ay]],
  ];
}

interface ZoneLabel {
  pos: [number, number];
  code: string;
  zone: string;
}

/** Label anchors along jurisdiction lines — territory codes at 1/3 and 2/3 of
 *  each feature's longest line part, so zones read without hovering. */
function zoneLabelAnchors(geo: GeoLayers): ZoneLabel[] {
  const out: ZoneLabel[] = [];
  for (const f of geo.jurisdiction.features) {
    const zone = String(f.properties.zone);
    if (zone === "border") continue; // land borders are self-explanatory
    const code = String(f.properties.code ?? "?");
    const g = f.geometry;
    const parts: [number, number][][] =
      g.type === "LineString"
        ? [g.coordinates as [number, number][]]
        : g.type === "MultiLineString"
          ? (g.coordinates as [number, number][][])
          : [];
    const longest = parts.sort((a, b) => b.length - a.length).slice(0, 2);
    for (const part of longest) {
      if (part.length < 12) continue;
      for (const frac of [0.33, 0.66]) {
        const v = part[Math.floor(part.length * frac)];
        out.push({ pos: [v[0], v[1]], code, zone });
      }
    }
  }
  return out;
}

const CONTRIB_LABELS: Record<string, string> = {
  behavioral_history: "behaviour",
  identity_risk: "identity",
  sar_mismatch: "SAR mismatch",
};

function getTooltip(info: PickingInfo): { html: string } | null {
  const o = info.object as Record<string, unknown> | GeoFeature | undefined;
  if (!o) return null;
  // SAR dark contact — a radar detection with no AIS (no MMSI, no properties).
  if ((o as { mmsi?: number }).mmsi === undefined && (o as { confidence?: unknown }).confidence !== undefined
      && (o as { lon?: unknown }).lon !== undefined && (o as GeoFeature).properties === undefined) {
    const d = o as unknown as { confidence: number | null };
    return {
      html: `<b>SAR dark contact</b><br/>radar return, no AIS within 2 km<br/><span style="color:#8FA3B8">confidence ${d.confidence != null ? d.confidence.toFixed(2) : "—"} · identity unknown</span>`,
    };
  }
  if ((o as { mmsi?: number }).mmsi !== undefined) {
    const v = o as unknown as ScoredVessel;
    const head = `<b>${v.name}</b> · ${v.shipType.toUpperCase()}<br/>MMSI ${v.mmsi} · ${v.sog.toFixed(1)} kn · COG ${Math.round(v.cog)}°`;
    if (!v.scored || !v.breakdown) {
      return { html: `${head}<br/><span style="color:#8FA3B8">${v.why}</span>` };
    }
    const b = v.breakdown;
    const factors = Object.entries(b.contributions)
      .filter(([, val]) => val > 0.001)
      .sort((a, c) => c[1] - a[1])
      .map(([k, val]) => `${CONTRIB_LABELS[k] ?? k} +${val.toFixed(2)}`)
      .join(" · ");
    return {
      html: `${head}<br/>risk <b>${v.suspicion.toFixed(2)}</b> · confidence ${b.confidence.toFixed(2)} · ${b.prior_days}d prior<br/><span style="color:#8FA3B8">${factors || "no prior signal"}</span><br/><span style="color:#5E7088">${v.why}</span>`,
    };
  }
  const f = o as GeoFeature;
  const p = f.properties ?? {};
  if (p.id !== undefined && p.coverage !== undefined) {
    const cov = String(p.coverage);
    const covTxt =
      p.vessels_80km !== undefined
        ? `${cov.toUpperCase()} — ${Number(p.vessels_80km)} vessels ≤80 km, nearest ${p.nearest_km ?? "?"} km`
        : cov.toUpperCase();
    return {
      html: `<b>${Number(p.n)}. ${String(p.short)}</b> · ${String(p.date)}${p.time_utc ? " " + String(p.time_utc) + "Z" : ""}<br/>${String(p.name)}<br/>${String(p.vessel)} (${String(p.flag)}) · ${String(p.status)}<br/><span style="color:#8FA3B8">AIS this day: <b>${covTxt}</b></span>`,
    };
  }
  if (p.tier !== undefined) {
    return {
      html: `<b>AIS coverage · ${String(p.tier)}</b><br/>≥${Number(p.min_vessels)} distinct vessels/cell over ${Number(p.n_days)} sample days`,
    };
  }
  if (p.fhr !== undefined) {
    return { html: `<b>Fishing intensity</b><br/>${Number(p.fhr).toFixed(0)} fishing-hours / cell (HELCOM 2020)` };
  }
  if (p.cat === "shipping_lane") {
    return { html: `<b>Shipping lane</b><br/>Traffic separation scheme · ${String(p.name ?? "")}` };
  }
  if (p.cat !== undefined) {
    const n = Number(p.n ?? 1);
    const extra = p.kind ? ` · ${String(p.kind)}` : n > 1 ? ` · ${n} sites merged` : "";
    return {
      html: `<b>${String(p.name ?? "—")}</b><br/>${CAT_LABELS[String(p.cat)] ?? p.cat}${extra} · strategic <b>${Number(p.s).toFixed(2)}</b>`,
    };
  }
  if (p.zone !== undefined) {
    const kind =
      p.zone === "eez" ? "EEZ boundary" : p.zone === "territorial" ? "Territorial sea (12 nm)" : "Country border";
    return { html: `${kind} · ${String(p.territory)}` };
  }
  return null;
}

function buildLayers(
  t: number,
  vessels: ScoredVessel[],
  geo: GeoLayers | null,
  ov: OverlayState,
  zoneLabels: ZoneLabel[],
  cues: ZoneCue[],
  darkContacts: DarkContact[],
  suspectMmsi: number | null,
): Layer[] {
  const layers: Layer[] = [];
  const { atlas, mapping } = buildIconAtlas();

  // ---- fishing intensity heatmap (green — where trawling actually happens) ----
  if (geo && ov.fishing.intensity) {
    layers.push(
      new HeatmapLayer({
        id: "fishing-intensity",
        data: geo.fishing.features,
        getPosition: (f: GeoFeature) => pointCoords(f),
        getWeight: (f: GeoFeature) => Number(f.properties.fhr),
        radiusPixels: 40,
        intensity: 1,
        threshold: 0.05,
        colorRange: [
          [16, 70, 55, 60],
          [24, 120, 90, 110],
          [60, 170, 110, 150],
          [150, 210, 90, 180],
          [220, 235, 130, 205],
          [245, 250, 170, 230],
        ],
      }),
    );
  }

  // ---- analysis: unified strategic heatmap (all POIs, theme-independent) ----
  if (geo && ov.analysis.heatmap) {
    layers.push(
      new HeatmapLayer({
        id: "strategic-heat",
        data: geo.poi.features,
        getPosition: (f: GeoFeature) => pointCoords(f),
        getWeight: (f: GeoFeature) => Number(f.properties.s) ** 2,
        radiusPixels: 56,
        intensity: 1.1,
        threshold: 0.04,
        colorRange: [
          [56, 142, 211, 40],
          [46, 196, 182, 80],
          [255, 209, 102, 120],
          [239, 138, 56, 160],
          [230, 57, 70, 200],
          [230, 57, 70, 240],
        ],
      }),
    );
  }

  // ---- AIS coverage zone (dev) — base wash under everything else ----
  if (geo && ov.incidentsDev.coverage && geo.coverage.features.length) {
    layers.push(
      new GeoJsonLayer({
        id: "ais-coverage",
        data: geo.coverage,
        stroked: true,
        filled: true,
        getFillColor: (f: GeoFeature) =>
          f.properties.tier === "reliable" ? [47, 214, 181, 40] : [255, 176, 46, 26],
        getLineColor: (f: GeoFeature) =>
          f.properties.tier === "reliable" ? [47, 214, 181, 150] : [255, 176, 46, 110],
        getLineWidth: 1,
        lineWidthUnits: "pixels",
        pickable: true,
      }),
    );
  }

  // ---- geography ----
  if (geo) {
    const zones: [keyof OverlayState["geo"], string, [number, number, number, number], number, boolean][] = [
      // [toggle, zone, color, width, dashed] — deliberately light: context, not content
      ["borders", "border", [143, 163, 184, 60], 0.8, false],
      ["eez", "eez", [90, 116, 160, 110], 1.0, false],
      ["territorial", "territorial", [143, 163, 184, 85], 0.9, true],
    ];
    for (const [key, zone, color, width, dashed] of zones) {
      if (!ov.geo[key]) continue;
      layers.push(
        new GeoJsonLayer({
          id: `geo-${zone}`,
          data: { ...geo.jurisdiction, features: geo.jurisdiction.features.filter((f) => f.properties.zone === zone) },
          stroked: true,
          filled: false,
          getLineColor: color,
          getLineWidth: width,
          lineWidthUnits: "pixels",
          pickable: true,
          ...(dashed
            ? { extensions: [new PathStyleExtension({ dash: true })], getDashArray: [5, 4], dashJustified: false }
            : {}),
        } as never),
      );
    }
    const visibleLabels = zoneLabels.filter(
      (l) => (l.zone === "eez" && ov.geo.eez) || (l.zone === "territorial" && ov.geo.territorial),
    );
    if (visibleLabels.length) {
      layers.push(
        new TextLayer({
          id: "zone-codes",
          data: visibleLabels,
          getPosition: (d: ZoneLabel) => d.pos,
          getText: (d: ZoneLabel) => (d.zone === "eez" ? `${d.code} EEZ` : d.code),
          getSize: 8.5,
          getColor: [143, 163, 184, 150],
          fontFamily: "'JetBrains Mono', monospace",
          characterSet: "auto",
          background: true,
          getBackgroundColor: [6, 10, 18, 140],
          backgroundPadding: [3, 1],
        }),
      );
    }
  }

  // ---- infrastructure (per-category) ----
  if (geo) {
    const lineCats = enabledCats(ov.infra, "line");
    const poiCats = enabledCats(ov.infra, "point");

    // restricted / military zones (polygons)
    if (ov.infra.restricted_zone) {
      layers.push(
        new GeoJsonLayer({
          id: "restricted-zones",
          data: geo.zones,
          stroked: true,
          filled: true,
          getFillColor: [255, 69, 56, 26],
          getLineColor: [255, 69, 56, 150],
          getLineWidth: 1.2,
          lineWidthUnits: "pixels",
          extensions: [new PathStyleExtension({ dash: true })],
          getDashArray: [4, 3],
          pickable: true,
        } as never),
      );
    }
    // solid infrastructure lines (cables, pipelines)
    const solidCats = new Set([...lineCats].filter((c) => c !== "shipping_lane"));
    if (solidCats.size) {
      layers.push(
        new GeoJsonLayer({
          id: "infra-lines",
          data: { ...geo.infra, features: geo.infra.features.filter((f) => solidCats.has(String(f.properties.cat))) },
          stroked: true,
          filled: false,
          getLineColor: (f: GeoFeature) => INFRA_COLORS[String(f.properties.cat)] ?? [143, 163, 184, 120],
          getLineWidth: (f: GeoFeature) => (String(f.properties.cat) === "pipeline" ? 1.6 : 1.1),
          lineWidthUnits: "pixels",
          pickable: true,
        }),
      );
    }
    // shipping lanes — dashed, muted (routing context, not a target)
    if (lineCats.has("shipping_lane")) {
      layers.push(
        new GeoJsonLayer({
          id: "shipping-lanes",
          data: { ...geo.infra, features: geo.infra.features.filter((f) => f.properties.cat === "shipping_lane") },
          stroked: true,
          filled: false,
          getLineColor: [125, 150, 190, 95],
          getLineWidth: 1,
          lineWidthUnits: "pixels",
          extensions: [new PathStyleExtension({ dash: true })],
          getDashArray: [6, 5],
          dashJustified: false,
          pickable: true,
        } as never),
      );
    }
    if (poiCats.size) {
      layers.push(
        new ScatterplotLayer({
          id: "infra-pois",
          data: geo.poi.features.filter((f) => poiCats.has(String(f.properties.cat))),
          getPosition: (f: GeoFeature) => pointCoords(f),
          // clustered sites render slightly larger (sqrt-ish growth, capped)
          getRadius: (f: GeoFeature) =>
            (1.6 + Number(f.properties.s) * 4.4) * (1 + Math.min(Number(f.properties.n ?? 1), 25) * 0.035),
          radiusUnits: "pixels",
          getFillColor: (f: GeoFeature) => {
            const [r, g, b] = colorForSuspicion(Number(f.properties.s));
            return [r, g, b, 195];
          },
          pickable: true,
        }),
      );
    }
  }

  // ---- vessels (already group-filtered upstream) ----
  if (vessels.length) {
    layers.push(
      new IconLayer({
        id: "vessels",
        data: vessels,
        iconAtlas: atlas,
        iconMapping: mapping,
        getIcon: (v: ScoredVessel) => shapeForShipType(v.shipType),
        getPosition: (v: ScoredVessel) => [v.lon, v.lat],
        getSize: (v: ScoredVessel) => 13 + v.suspicion * 10,
        sizeUnits: "pixels",
        getColor: (v: ScoredVessel) => {
          const [r, g, b] = colorForSuspicion(v.suspicion);
          // Dead-reckoned (AIS-dark / frozen) fixes render dim and fade further
          // the deeper into the gap, so reacquisition (a position jump) lands
          // while ~invisible instead of as a confident teleport.
          const alpha = v.dark ? Math.max(15, Math.round(180 * (1 - v.darkness))) : 235;
          return [r, g, b, alpha];
        },
        getAngle: (v: ScoredVessel) => (ROTATABLE.has(shapeForShipType(v.shipType)) ? -v.cog : 0),
        pickable: true,
        updateTriggers: { getPosition: t, getColor: t, getAngle: t, getSize: t },
      }),
    );
    if (ov.vessels.labels) {
      // Cap labels HARD: the tasked vessels (what the satellites watch) + the hero
      // + a few top-risk, ≤ LABEL_CAP total. Labelling every ≥0.45 vessel was ~78
      // text-laid-out glyphsets re-rendered EVERY frame — it froze the main thread
      // when zoomed in during playback. A handful of labels is also more legible.
      const LABEL_CAP = 12;
      const labelSet = new Set<number>();
      if (suspectMmsi != null) labelSet.add(suspectMmsi);
      for (const c of cues) for (const d of c.drivers) labelSet.add(d.mmsi);
      for (const v of vessels.filter((v) => v.suspicion >= 0.6 && !labelSet.has(v.mmsi)).sort((a, b) => b.suspicion - a.suspicion)) {
        if (labelSet.size >= LABEL_CAP) break;
        labelSet.add(v.mmsi);
      }
      const labelled = vessels.filter((v) => labelSet.has(v.mmsi));
      layers.push(
        new TextLayer({
          id: "vessel-labels",
          data: labelled,
          getPosition: (v: ScoredVessel) => [v.lon, v.lat],
          getText: (v: ScoredVessel) => `${v.name} · ${v.suspicion.toFixed(2)}`,
          getSize: 10.5,
          getColor: (v: ScoredVessel) => (v.suspicion >= 0.75 ? [230, 57, 70, 255] : [143, 163, 184, 255]),
          getPixelOffset: [0, -20],
          fontFamily: "'JetBrains Mono', monospace",
          background: true,
          getBackgroundColor: [6, 10, 18, 215],
          backgroundPadding: [4, 2],
          updateTriggers: { getPosition: t },
        }),
      );
    }
  }

  // ---- incident points (dev) — the 9 known incidents, coloured by AIS coverage ----
  if (geo && ov.incidentsDev.points && geo.incidents.features.length) {
    const covColor: Record<string, [number, number, number]> = {
      reliable: [46, 196, 132],
      marginal: [255, 176, 46],
      gap: [230, 57, 70],
      unknown: [143, 163, 184],
    };
    layers.push(
      new ScatterplotLayer({
        id: "incident-points",
        data: geo.incidents.features,
        getPosition: (f: GeoFeature) => pointCoords(f),
        getRadius: 6,
        radiusUnits: "pixels",
        stroked: true,
        getLineColor: [255, 255, 255, 230],
        lineWidthUnits: "pixels",
        getLineWidth: 1.5,
        getFillColor: (f: GeoFeature) => {
          const [r, g, b] = covColor[String(f.properties.coverage)] ?? covColor.unknown;
          return [r, g, b, 235];
        },
        pickable: true,
      }),
      new TextLayer({
        id: "incident-labels",
        data: geo.incidents.features,
        getPosition: (f: GeoFeature) => pointCoords(f),
        getText: (f: GeoFeature) => `${f.properties.n}·${String(f.properties.short)}`,
        getSize: 10,
        getColor: [233, 240, 247, 255],
        getTextAnchor: "start" as const,
        getAlignmentBaseline: "center" as const,
        getPixelOffset: [10, 0],
        fontFamily: "'JetBrains Mono', monospace",
        characterSet: "auto",
        background: true,
        getBackgroundColor: [6, 10, 18, 205],
        backgroundPadding: [4, 2],
      }),
    );
  }

  // ---- SAR dark-vessel detections — radar contacts with no AIS (no identity) ----
  if (darkContacts.length) {
    layers.push(
      new ScatterplotLayer({
        id: "sar-dark-contacts",
        data: darkContacts,
        getPosition: (d: DarkContact) => [d.lon, d.lat],
        getRadius: 4,
        radiusUnits: "pixels",
        radiusMinPixels: 2.5,
        stroked: true,
        getLineColor: [230, 57, 70, 220],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        getFillColor: (d: DarkContact) => [230, 57, 70, 70 + Math.round((d.confidence ?? 0.5) * 120)],
        pickable: true,
      }),
    );
  }

  // ---- the real task-next queue — ranked cue boxes (brightest = #1) ----
  if (cues.length) {
    const sar = colorForSensor("SAR");
    const pulse = 0.7 + 0.3 * Math.sin(t / 400);
    layers.push(
      new PathLayer({
        id: "cue-boxes",
        data: cues.flatMap((c) =>
          cueBracketPaths(c.bbox).map((path) => ({ path, rank: c.rank })),
        ),
        getPath: (d: { path: [number, number][] }) => d.path,
        getColor: (d: { rank: number }) =>
          [...sar, d.rank === 1 ? 240 : 150] as [number, number, number, number],
        getWidth: (d: { rank: number }) => (d.rank === 1 ? 2.4 : 1.6),
        widthUnits: "pixels",
        opacity: pulse,
        updateTriggers: { getPath: cues.map((c) => c.bbox.join(",")).join("|") },
      }),
      new TextLayer({
        id: "cue-tags",
        data: cues,
        getPosition: (c: ZoneCue) => [c.bbox[0], c.bbox[3]],
        getText: (c: ZoneCue) => `#${c.rank} · ${c.sensor} · ${c.score.toFixed(2)}`,
        getSize: (c: ZoneCue) => (c.rank === 1 ? 11 : 9.5),
        getColor: [...sar, 255] as [number, number, number, number],
        getTextAnchor: "start" as const,
        getAlignmentBaseline: "bottom" as const,
        getPixelOffset: [0, -6],
        fontFamily: "'JetBrains Mono', monospace",
        characterSet: "auto",
        background: true,
        getBackgroundColor: [6, 10, 18, 220],
        backgroundPadding: [5, 3],
        updateTriggers: { getText: cues.map((c) => `${c.rank}:${c.score}`).join("|") },
      }),
    );
  }

  return layers;
}

export default function MapView({ t, vessels, geo, overlays, cues, darkContacts, suspectMmsi, onMapReady }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [cursor, setCursor] = useState<{ lon: number; lat: number } | null>(null);

  const zoneLabels = useMemo(() => (geo ? zoneLabelAnchors(geo) : []), [geo]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: MAP_STYLE,
      center: [16.5, 58.2],
      zoom: 4.5,
      minZoom: 3.4,
      maxZoom: 13,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const overlay = new MapboxOverlay({ layers: [], getTooltip });
    map.addControl(overlay);
    map.on("mousemove", (e) => setCursor({ lon: e.lngLat.lng, lat: e.lngLat.lat }));
    // dev console access + error capture (harmless in prod)
    (window as unknown as Record<string, unknown>).__map = map;
    // Belt-and-suspenders: some embedded browsers don't fire maplibre's own
    // resize tracking — observe the container explicitly (only after the
    // style is up; resizing mid-style-load can wedge the load).
    const ro = new ResizeObserver(() => {
      if (map.isStyleLoaded()) map.resize();
    });
    map.once("load", () => {
      map.resize();
      ro.observe(container.current!);
    });
    mapRef.current = map;
    overlayRef.current = overlay;
    onMapReady(map);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    overlayRef.current?.setProps({
      layers: buildLayers(t, vessels, geo, overlays, zoneLabels, cues, darkContacts, suspectMmsi),
    });
  }, [t, vessels, geo, overlays, zoneLabels, cues, darkContacts, suspectMmsi]);

  return (
    <div className="map-wrap">
      <div ref={container} className="map-root" />
      <div className="float legend">
        <div className="hd">Strategic / suspicion</div>
        <div className="bar" />
        <div className="ends">
          <span>0.0 CALM</span>
          <span>1.0 CRITICAL</span>
        </div>
      </div>
      <div className="float coords">
        {cursor ? `${cursor.lat.toFixed(2)}°N ${cursor.lon.toFixed(2)}°E` : "BALTIC / NORTH SEA"} · EOX S2 CLOUDLESS
      </div>
    </div>
  );
}
