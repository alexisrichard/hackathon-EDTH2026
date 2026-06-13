import type { ScoredVessel } from "../lib/trackStore";
import { bandForScore, colorHexForSuspicion } from "../types/encoding";
import { fmtZ } from "../lib/clock";

interface Props {
  t: number;
  vessels: ScoredVessel[];
  onFocus: (v: ScoredVessel) => void;
}

export default function AlertFeed({ t, vessels, onFocus }: Props) {
  const top = [...vessels].sort((a, b) => b.suspicion - a.suspicion).slice(0, 4);
  const anyBreach = top[0] && top[0].suspicion >= 0.9;
  return (
    <>
      <div className="rail-head">
        <span className={`dot ${anyBreach ? "breach" : top[0] && top[0].suspicion >= 0.5 ? "alerting" : "nominal"}`} />
        ALERT FEED
      </div>
      {top.map((v) => {
        const hex = colorHexForSuspicion(v.suspicion);
        return (
          <div
            key={v.mmsi}
            className="rail-item"
            style={{ borderLeftColor: hex }}
            onClick={() => onFocus(v)}
            title="center map on vessel"
          >
            <div className="r1">
              <span className="nm">{v.name}</span>
              <span className="sc" style={{ color: hex }}>
                {v.suspicion.toFixed(2)}
              </span>
            </div>
            <div className="r2">{v.why}</div>
            <div className="r3">
              {fmtZ(t).slice(11)} · {v.lat.toFixed(2)}N {v.lon.toFixed(2)}E · {bandForScore(v.suspicion).toUpperCase()}
            </div>
          </div>
        );
      })}
    </>
  );
}
