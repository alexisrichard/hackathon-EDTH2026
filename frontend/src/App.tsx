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
import { fetchLiveFrame, frameAt, loadCues, type CueData, type Frame, type ZoneCue } from "./lib/cues";

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
  const [cueData, setCueData] = useState<CueData | null>(null);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const liveSnap = useRef<number | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    loadGeoLayers()
      .then((g) => {
        setGeo(g);
        setGeoReady(true);
      })
      .catch((e: Error) => setErr(e.message));
    // The continuous cueing engine (zone_score --emit). Non-fatal if absent.
    loadCues()
      .then(setCueData)
      .catch((e: Error) => console.warn("cues unavailable:", e.message));
  }, []);

  // The frame the engine is showing right now. Inside a precomputed window
  // (C-Lion1 / Nord Stream) it's instant; ANY other instant is scored on demand by
  // the live backend (snapped to the 3h cadence + cached, so playback within a
  // window is free). No look-ahead either way.
  useEffect(() => {
    if (!cueData) return;
    const pre = frameAt(clock.t, cueData);
    if (pre) {
      liveSnap.current = null;
      setLiveLoading(false);
      setFrame(pre);
      return;
    }
    const snapped = Math.floor(clock.t / (3 * 3600 * 1000));
    if (snapped === liveSnap.current) return; // same re-task window → frame already set
    liveSnap.current = snapped;
    let cancelled = false;
    setLiveLoading(true);
    fetchLiveFrame(clock.t).then((f) => {
      if (cancelled) return;
      setLiveLoading(false);
      setFrame(f); // null if the backend is unreachable → fleet shows unscored
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock.t, cueData]);
  const risk = frame?.riskMap;

  // Vessels driving a current satellite tasking (and the hero) are always rendered,
  // even if their class group is toggled off — we never hide a flagged vessel.
  // (The real Yi Peng 3 broadcasts AIS type "other", so it would otherwise vanish.)
  const alwaysShow = useMemo(() => {
    const s = new Set<number>();
    if (frame?.heroMmsi) s.add(frame.heroMmsi);
    if (frame) for (const c of frame.taskings) for (const d of c.drivers) s.add(d.mmsi);
    return s;
  }, [frame]);

  // Real interpolated fleet, scored point-in-time by the engine. A vessel inside
  // the current snapshot's scored theatre carries its real vessel_risk; one outside
  // shows as unscored (never silently "safe").
  const vessels = useMemo<ScoredVessel[]>(() => {
    return (tiles.current?.positionsAt(clock.t) ?? [])
      .filter((v) => overlays.vessels[VESSEL_GROUPS[v.shipType]] || alwaysShow.has(v.mmsi))
      .map((v) => {
        const r = risk?.get(v.mmsi);
        if (r) return { ...v, suspicion: r.risk, why: r.explanation, breakdown: r, scored: true };
        return {
          ...v, suspicion: 0, scored: false,
          why: frame ? "Outside the scored theatre at this instant" : "No scored incident at this time",
        };
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock.t, overlays.vessels, tileVersion, frame, risk, alwaysShow]);
  const dayStatus = tiles.current?.status(clock.t) ?? "loading";

  const maxSuspicion = useMemo(
    () => (vessels.length ? Math.max(...vessels.map((v) => v.suspicion)) : 0),
    [vessels],
  );

  // The current satellite taskings + any SAR dark detections.
  const cues = useMemo<ZoneCue[]>(
    () => (frame && overlays.cueing.cues ? frame.taskings : []),
    [frame, overlays.cueing.cues],
  );
  const darkContacts = useMemo(
    () => (frame && overlays.cueing.sar ? frame.darkContacts : []),
    [frame, overlays.cueing.sar],
  );

  // Pin the alert feed's "PRIMARY CUE" only when the hero is genuinely the #1
  // tasking's top driver — so the pin can never lie.
  const primaryCueMmsi = useMemo(() => {
    const top = frame?.taskings?.[0]?.drivers?.[0]?.mmsi;
    return frame?.heroMmsi != null && top === frame.heroMmsi ? frame.heroMmsi : null;
  }, [frame]);

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
            suspectMmsi={frame?.heroMmsi ?? null}
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
          {liveLoading && (
            <div className="day-status live-scoring">
              <span className="ring small" /> scoring theatre…
            </div>
          )}
        </div>
        <aside className="rail">
          <AlertFeed t={clock.t} vessels={vessels} heroMmsi={primaryCueMmsi} onFocus={focusVessel} />
          <CuePanel frame={frame} t={clock.t} onTask={focusCue} />
        </aside>
      </div>
      <TimeScrubber clock={clock} />
    </div>
  );
}
