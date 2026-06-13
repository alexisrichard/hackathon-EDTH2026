import { useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";

import TopBar from "./components/TopBar";
import MapView, { type Cue } from "./components/MapView";
import AlertFeed from "./components/AlertFeed";
import CuePanel from "./components/CuePanel";
import TimeScrubber from "./components/TimeScrubber";
import LayerPanel from "./components/LayerPanel";

import { useReplayClock } from "./lib/clock";
import { loadGeoLayers, type GeoLayers } from "./lib/geodata";
import { DEFAULT_OVERLAYS, VESSEL_GROUPS, type OverlayState } from "./lib/overlays";
import { TileManager, type VesselFix } from "./lib/trackStore";
import { scoreFix, cueFor, SUSPECT_MMSI } from "./lib/scenario";
import { colorForSensor } from "./types/encoding";

const TILES_BASE = "/data/ais";
const CUE_THRESHOLD = 0.6;

// A scored vessel = a real interpolated fix + interim suspicion.
export interface Vessel extends VesselFix {
  suspicion: number;
  why: string;
}

export default function App() {
  const clock = useReplayClock();
  const [geo, setGeo] = useState<GeoLayers | null>(null);
  const [overlays, setOverlays] = useState<OverlayState>(DEFAULT_OVERLAYS);
  const [tileVersion, setTileVersion] = useState(0);
  const tiles = useRef<TileManager | null>(null);
  if (!tiles.current) tiles.current = new TileManager(TILES_BASE, () => setTileVersion((v) => v + 1));
  const [geoReady, setGeoReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    loadGeoLayers()
      .then((g) => {
        setGeo(g);
        setGeoReady(true);
      })
      .catch((e: Error) => setErr(e.message));
  }, []);

  // Real interpolated fleet + interim scores, filtered by vessel-class group.
  // tileVersion in deps so a freshly-arrived day-tile re-renders the fleet.
  const vessels = useMemo<Vessel[]>(() => {
    return (tiles.current?.positionsAt(clock.t) ?? [])
      .filter((v) => overlays.vessels[VESSEL_GROUPS[v.shipType]])
      .map((v) => ({ ...v, ...scoreFix(v) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock.t, overlays.vessels, tileVersion]);
  const dayStatus = tiles.current?.status(clock.t) ?? "loading";

  const maxSuspicion = useMemo(
    () => (vessels.length ? Math.max(...vessels.map((v) => v.suspicion)) : 0),
    [vessels],
  );

  // Cue follows the hottest vessel above threshold (the tasking recommendation).
  const cue = useMemo<Cue | null>(() => {
    const top = vessels.reduce<Vessel | null>((a, v) => (a && a.suspicion >= v.suspicion ? a : v), null);
    if (!top || top.suspicion < CUE_THRESHOLD) return null;
    return {
      bbox: cueFor(top.lon, top.lat),
      label: `CUE-01 · SAR · ${top.name.toUpperCase()}`,
      color: colorForSensor("SAR"),
    };
  }, [vessels]);

  const focusVessel = (v: { lon: number; lat: number }) =>
    mapRef.current?.flyTo({ center: [v.lon, v.lat], zoom: 8.2, duration: 1200 });
  const focusCue = () => {
    if (!cue) return;
    const [x0, y0, x1, y1] = cue.bbox;
    mapRef.current?.fitBounds(
      [
        [x0 - 0.4, y0 - 0.25],
        [x1 + 0.4, y1 + 0.25],
      ],
      { duration: 1200 },
    );
  };

  return (
    <div className="app">
      <TopBar t={clock.t} speed={clock.speed} maxSuspicion={maxSuspicion} />
      <div className="app-main">
        <div style={{ position: "relative", minWidth: 0, display: "flex" }}>
          <MapView
            t={clock.t}
            vessels={vessels}
            geo={geo}
            overlays={overlays}
            cue={cue}
            suspectMmsi={SUSPECT_MMSI}
            onMapReady={(m) => {
              mapRef.current = m;
            }}
          />
          <LayerPanel overlays={overlays} onChange={setOverlays} />
          {!geoReady && (
            <div className="loading">
              <div className="ring" />
              {err ? `LOAD FAILED: ${err}` : "LOADING THEATRE"}
            </div>
          )}
          {geoReady && dayStatus !== "ready" && (
            <div className="day-status">
              {dayStatus === "loading" ? "▣ streaming AIS…" : "○ no AIS tile for this day"}
            </div>
          )}
        </div>
        <aside className="rail">
          <AlertFeed t={clock.t} vessels={vessels} onFocus={focusVessel} />
          <CuePanel cue={cue} suspicion={maxSuspicion} onTask={focusCue} />
        </aside>
      </div>
      <TimeScrubber clock={clock} />
    </div>
  );
}
