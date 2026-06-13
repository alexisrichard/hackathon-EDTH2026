import { useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";

import TopBar from "./components/TopBar";
import MapView from "./components/MapView";
import AlertFeed from "./components/AlertFeed";
import CuePanel from "./components/CuePanel";
import TimeScrubber from "./components/TimeScrubber";
import LayerPanel from "./components/LayerPanel";

import { useReplayClock } from "./lib/clock";
import { loadGeoLayers, type GeoLayers } from "./lib/geodata";
import { DEFAULT_OVERLAYS, VESSEL_GROUPS, type OverlayState } from "./lib/overlays";
import { TileManager, type ScoredVessel } from "./lib/trackStore";
import {
  activeScenario,
  loadScenarios,
  riskByMmsi,
  type ScenarioPayload,
  type ZoneCue,
} from "./lib/cues";

const TILES_BASE = "/data/ais_v2"; // stitched, self-aligned tiles (no runtime merge)

export default function App() {
  const clock = useReplayClock();
  const [geo, setGeo] = useState<GeoLayers | null>(null);
  const [overlays, setOverlays] = useState<OverlayState>(DEFAULT_OVERLAYS);
  const [tileVersion, setTileVersion] = useState(0);
  const tiles = useRef<TileManager | null>(null);
  if (!tiles.current) tiles.current = new TileManager(TILES_BASE, () => setTileVersion((v) => v + 1));
  const [geoReady, setGeoReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioPayload[]>([]);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    loadGeoLayers()
      .then((g) => {
        setGeo(g);
        setGeoReady(true);
      })
      .catch((e: Error) => setErr(e.message));
    // Real cueing-engine output (zone_score --emit). Non-fatal if absent.
    loadScenarios()
      .then(setScenarios)
      .catch((e: Error) => console.warn("cues unavailable:", e.message));
  }, []);

  // The scenario whose evaluation day matches the clock — its real cues + scores
  // light up. Opens on the C-Lion1 / Yi Peng 3 moment, so it's live by default.
  const active = useMemo(() => activeScenario(clock.t, scenarios), [clock.t, scenarios]);
  const risk = useMemo(() => riskByMmsi(active), [active]);

  // Vessels that drive a task-next cue (and the hero) are always rendered, even if
  // their class group is toggled off — we never hide a flagged vessel because of a
  // class filter. (The real Yi Peng 3 broadcasts AIS type "other", so it would
  // otherwise vanish with the Other group off.)
  const alwaysShow = useMemo(() => {
    const s = new Set<number>();
    if (active?.hero_mmsi) s.add(active.hero_mmsi);
    if (active) for (const c of active.cues) for (const d of c.drivers) s.add(d.mmsi);
    return s;
  }, [active]);

  // Real interpolated fleet, scored point-in-time by the engine (no look-ahead).
  // A vessel inside the active scenario's theatre carries its real vessel_risk +
  // interpretable breakdown; one outside the scored theatre shows as unscored.
  const vessels = useMemo<ScoredVessel[]>(() => {
    return (tiles.current?.positionsAt(clock.t) ?? [])
      .filter((v) => overlays.vessels[VESSEL_GROUPS[v.shipType]] || alwaysShow.has(v.mmsi))
      .map((v) => {
        const r = risk.get(v.mmsi);
        if (r) {
          return { ...v, suspicion: r.breakdown.risk, why: r.breakdown.explanation,
                   breakdown: r.breakdown, scored: true };
        }
        return {
          ...v, suspicion: 0, scored: false,
          why: active ? "Outside the scored theatre at this instant" : "No scored incident at this time",
        };
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock.t, overlays.vessels, tileVersion, active, risk, alwaysShow]);
  const dayStatus = tiles.current?.status(clock.t) ?? "loading";

  const maxSuspicion = useMemo(
    () => (vessels.length ? Math.max(...vessels.map((v) => v.suspicion)) : 0),
    [vessels],
  );

  // The real task-next queue + SAR dark detections for the active scenario.
  const cues = useMemo<ZoneCue[]>(
    () => (active && overlays.cueing.cues ? active.cues : []),
    [active, overlays.cueing.cues],
  );
  const darkContacts = useMemo(
    () => (active && overlays.cueing.sar ? active.dark_contacts : []),
    [active, overlays.cueing.sar],
  );

  const focusVessel = (v: { lon: number; lat: number }) =>
    mapRef.current?.flyTo({ center: [v.lon, v.lat], zoom: 8.2, duration: 1200 });
  const focusCue = (cue: ZoneCue) => {
    const [x0, y0, x1, y1] = cue.bbox;
    mapRef.current?.fitBounds(
      [
        [x0 - 0.4, y0 - 0.25],
        [x1 + 0.4, y1 + 0.25],
      ],
      { duration: 1200, maxZoom: 8.5 },
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
            cues={cues}
            darkContacts={darkContacts}
            suspectMmsi={active?.hero_mmsi ?? null}
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
          <AlertFeed t={clock.t} vessels={vessels} heroMmsi={active?.hero_mmsi ?? null} onFocus={focusVessel} />
          <CuePanel cues={cues} scenario={active} onTask={focusCue} />
        </aside>
      </div>
      <TimeScrubber clock={clock} />
    </div>
  );
}
