import { useEffect, useMemo, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";

import TopBar from "./components/TopBar";
import MapView, { type LayerToggles } from "./components/MapView";
import AlertFeed from "./components/AlertFeed";
import CuePanel from "./components/CuePanel";
import TimeScrubber from "./components/TimeScrubber";
import LayerPanel from "./components/LayerPanel";

import { useReplayClock } from "./lib/clock";
import { loadGeoLayers, type GeoLayers } from "./lib/geodata";
import { fleetAt, CUE_BBOX, type MockVesselState } from "./mock/fleet";

const DEFAULT_TOGGLES: LayerToggles = {
  jurisdiction: true,
  infrastructure: true,
  geopoints: true,
  heatmap: false,
  vessels: true,
  labels: true,
};

export default function App() {
  const clock = useReplayClock();
  const [geo, setGeo] = useState<GeoLayers | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [toggles, setToggles] = useState<LayerToggles>(DEFAULT_TOGGLES);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    loadGeoLayers()
      .then(setGeo)
      .catch((e: Error) => setGeoError(e.message));
  }, []);

  const vessels = useMemo(() => fleetAt(clock.t), [clock.t]);
  const maxSuspicion = useMemo(() => Math.max(...vessels.map((v) => v.suspicion)), [vessels]);

  const focusVessel = (v: MockVesselState) => {
    mapRef.current?.flyTo({ center: [v.lon, v.lat], zoom: 8.2, duration: 1200 });
  };
  const focusCue = () => {
    mapRef.current?.fitBounds(
      [
        [CUE_BBOX[0] - 0.4, CUE_BBOX[1] - 0.25],
        [CUE_BBOX[2] + 0.4, CUE_BBOX[3] + 0.25],
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
            toggles={toggles}
            onMapReady={(m) => {
              mapRef.current = m;
            }}
          />
          <LayerPanel toggles={toggles} onChange={setToggles} />
          {!geo && (
            <div className="loading">
              <div className="ring" />
              {geoError ? `GEO LAYERS FAILED: ${geoError}` : "LOADING THEATRE DATA"}
            </div>
          )}
        </div>
        <aside className="rail">
          <AlertFeed t={clock.t} vessels={vessels} onFocus={focusVessel} />
          <CuePanel t={clock.t} onTask={focusCue} />
        </aside>
      </div>
      <TimeScrubber clock={clock} />
    </div>
  );
}
