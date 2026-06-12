/**
 * The theatre map: EOX Sentinel-2 cloudless basemap (MapLibre) with deck.gl
 * data layers overlaid — jurisdictions, infrastructure, scored geopoints,
 * the optional strategic heatmap, the mock AIS fleet, and the live cue box.
 */
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, IconLayer, PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import type { Layer, PickingInfo } from "@deck.gl/core";

import { colorForSuspicion, colorForSensor } from "../types/encoding";
import { shapeForShipType } from "../types/encoding";
import type { GeoLayers, GeoFeature } from "../lib/geodata";
import { CAT_LABELS, pointCoords } from "../lib/geodata";
import { buildIconAtlas, ROTATABLE } from "../lib/icons";
import type { MockVesselState } from "../mock/fleet";
import { CUE_BBOX, CUE_FIRES_T, EAGLE_S_MMSI } from "../mock/fleet";
import { BREACH_T, fmtZ } from "../lib/clock";

export interface LayerToggles {
  jurisdiction: boolean;
  infrastructure: boolean;
  geopoints: boolean;
  heatmap: boolean;
  vessels: boolean;
  labels: boolean;
}

interface Props {
  t: number;
  vessels: MockVesselState[];
  geo: GeoLayers | null;
  toggles: LayerToggles;
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

function getTooltip(info: PickingInfo): { html: string } | null {
  const o = info.object as Record<string, unknown> | GeoFeature | undefined;
  if (!o) return null;
  if ((o as { mmsi?: number }).mmsi !== undefined) {
    const v = o as unknown as MockVesselState;
    return {
      html: `<b>${v.name}</b> · ${v.shipType.toUpperCase()}<br/>MMSI ${v.mmsi} · ${v.sog.toFixed(1)} kn · COG ${Math.round(v.cog)}°<br/>suspicion <b>${v.suspicion.toFixed(2)}</b><br/><span style="color:#8FA3B8">${v.why}</span>`,
    };
  }
  const f = o as GeoFeature;
  const p = f.properties ?? {};
  if (p.cat !== undefined) {
    return {
      html: `<b>${String(p.name ?? "—")}</b><br/>${CAT_LABELS[String(p.cat)] ?? p.cat} · strategic <b>${Number(p.s).toFixed(2)}</b>`,
    };
  }
  if (p.zone !== undefined) {
    return {
      html: `${p.zone === "eez" ? "EEZ boundary" : "Territorial sea (12 nm)"} · ${String(p.territory)}`,
    };
  }
  return null;
}

function buildLayers(t: number, vessels: MockVesselState[], geo: GeoLayers | null, toggles: LayerToggles): Layer[] {
  const layers: Layer[] = [];
  const { atlas, mapping } = buildIconAtlas();

  if (geo && toggles.heatmap) {
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

  if (geo && toggles.jurisdiction) {
    layers.push(
      new GeoJsonLayer({
        id: "eez",
        data: { ...geo.jurisdiction, features: geo.jurisdiction.features.filter((f) => f.properties.zone === "eez") },
        stroked: true,
        filled: false,
        getLineColor: [90, 116, 160, 200],
        getLineWidth: 1.4,
        lineWidthUnits: "pixels",
        pickable: true,
      }),
      new GeoJsonLayer({
        id: "territorial",
        data: {
          ...geo.jurisdiction,
          features: geo.jurisdiction.features.filter((f) => f.properties.zone === "territorial"),
        },
        stroked: true,
        filled: false,
        getLineColor: [143, 163, 184, 135],
        getLineWidth: 1,
        lineWidthUnits: "pixels",
        extensions: [new PathStyleExtension({ dash: true })],
        getDashArray: [5, 4],
        dashJustified: false,
        pickable: true,
      } as never),
    );
  }

  if (geo && toggles.infrastructure) {
    layers.push(
      new GeoJsonLayer({
        id: "infra",
        data: geo.infra,
        stroked: true,
        filled: false,
        getLineColor: (f: GeoFeature) => INFRA_COLORS[String(f.properties.cat)] ?? [143, 163, 184, 120],
        getLineWidth: (f: GeoFeature) => (String(f.properties.cat) === "pipeline" ? 1.6 : 1.1),
        lineWidthUnits: "pixels",
        pickable: true,
      }),
    );
  }

  if (geo && toggles.geopoints) {
    layers.push(
      new ScatterplotLayer({
        id: "poi",
        data: geo.poi.features,
        getPosition: (f: GeoFeature) => pointCoords(f),
        getRadius: (f: GeoFeature) => 1.6 + Number(f.properties.s) * 4.4,
        radiusUnits: "pixels",
        getFillColor: (f: GeoFeature) => {
          const [r, g, b] = colorForSuspicion(Number(f.properties.s));
          return [r, g, b, 195];
        },
        pickable: true,
      }),
    );
  }

  if (toggles.vessels) {
    layers.push(
      new IconLayer({
        id: "vessels",
        data: vessels,
        iconAtlas: atlas,
        iconMapping: mapping,
        getIcon: (v: MockVesselState) => shapeForShipType(v.shipType),
        getPosition: (v: MockVesselState) => [v.lon, v.lat],
        getSize: (v: MockVesselState) => 13 + v.suspicion * 10,
        sizeUnits: "pixels",
        getColor: (v: MockVesselState) => {
          const [r, g, b] = colorForSuspicion(v.suspicion);
          return [r, g, b, 235];
        },
        getAngle: (v: MockVesselState) => (ROTATABLE.has(shapeForShipType(v.shipType)) ? -v.cog : 0),
        pickable: true,
        updateTriggers: { getPosition: t, getColor: t, getAngle: t, getSize: t },
      }),
    );
  }

  if (toggles.labels && toggles.vessels) {
    const labelled = vessels.filter((v) => v.suspicion >= 0.45 || v.mmsi === EAGLE_S_MMSI);
    layers.push(
      new TextLayer({
        id: "vessel-labels",
        data: labelled,
        getPosition: (v: MockVesselState) => [v.lon, v.lat],
        getText: (v: MockVesselState) => `${v.name} · ${v.suspicion.toFixed(2)}`,
        getSize: 10.5,
        getColor: (v: MockVesselState) => (v.suspicion >= 0.75 ? [230, 57, 70, 255] : [143, 163, 184, 255]),
        getPixelOffset: [0, -20],
        fontFamily: "'JetBrains Mono', monospace",
        background: true,
        getBackgroundColor: [6, 10, 18, 215],
        backgroundPadding: [4, 2],
        updateTriggers: { getPosition: t, getText: t, getColor: t },
      }),
    );
  }

  // SAR cue box — fires before the breach, the product's hero gesture
  if (t >= CUE_FIRES_T) {
    const sar = colorForSensor("SAR");
    layers.push(
      new PathLayer({
        id: "cue-box",
        data: cueBracketPaths(CUE_BBOX).map((path) => ({ path })),
        getPath: (d: { path: [number, number][] }) => d.path,
        getColor: [...sar, 235] as [number, number, number, number],
        getWidth: 2.2,
        widthUnits: "pixels",
        opacity: 0.7 + 0.3 * Math.sin(t / 400),
      }),
      new TextLayer({
        id: "cue-tag",
        data: [{ pos: [CUE_BBOX[0], CUE_BBOX[3]] }],
        getPosition: (d: { pos: [number, number] }) => d.pos,
        getText: () =>
          t < BREACH_T ? `CUE-01 · SAR · TASK BY ${fmtZ(BREACH_T).slice(11, 16)}Z` : "CUE-01 · SAR · BREACH 14:00Z",
        getSize: 10,
        getColor: t < BREACH_T ? [...sar, 255] as [number, number, number, number] : [255, 69, 56, 255],
        getTextAnchor: "start" as const,
        getAlignmentBaseline: "bottom" as const,
        getPixelOffset: [0, -6],
        fontFamily: "'JetBrains Mono', monospace",
        background: true,
        getBackgroundColor: [6, 10, 18, 220],
        backgroundPadding: [5, 3],
        updateTriggers: { getText: t >= BREACH_T, getColor: t >= BREACH_T },
      }),
    );
  }

  return layers;
}

export default function MapView({ t, vessels, geo, toggles, onMapReady }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [cursor, setCursor] = useState<{ lon: number; lat: number } | null>(null);

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
    const errs: string[] = [];
    (window as unknown as Record<string, unknown>).__mapErrors = errs;
    map.on("error", (e) => errs.push(String((e as { error?: Error }).error?.message ?? e.type)));
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
    overlayRef.current?.setProps({ layers: buildLayers(t, vessels, geo, toggles) });
  }, [t, vessels, geo, toggles]);

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
        {cursor
          ? `${cursor.lat.toFixed(2)}°N ${cursor.lon.toFixed(2)}°E`
          : "BALTIC / NORTH SEA"}{" "}
        · EOX S2 CLOUDLESS
      </div>
    </div>
  );
}
