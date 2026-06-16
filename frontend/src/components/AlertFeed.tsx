import type { ScoredVessel } from "../lib/trackStore";
import { bandForScore, colorHexForSuspicion } from "../types/encoding";
import { fmtZ } from "../lib/clock";

interface Props {
  t: number;
  vessels: ScoredVessel[];
  heroMmsi: number | null;
  onFocus: (v: ScoredVessel) => void;
}

const CONTRIB_LABELS: Record<string, string> = {
  behavioral_history: "behaviour",
  identity_risk: "identity",
  sar_mismatch: "SAR",
};

/** The dominant interpretable factors behind a vessel's risk (engine output). */
function factors(v: ScoredVessel): string {
  if (!v.breakdown) return "";
  return Object.entries(v.breakdown.contributions)
    .filter(([, val]) => val > 0.001)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([k, val]) => `${CONTRIB_LABELS[k] ?? k} +${val.toFixed(2)}`)
    .join(" · ");
}

export default function AlertFeed({ t, vessels, heroMmsi, onFocus }: Props) {
  // Only vessels the engine actually scored (inside the active theatre).
  const scored = vessels.filter((v) => v.scored && v.suspicion > 0);
  // Pin the scenario's primary cue vessel (the named #1 task-next driver) to the
  // top — honestly, not because its raw prior is highest (it isn't), but because
  // it's the cue the engine surfaced. The rest follow by point-in-time risk.
  const hero = heroMmsi != null ? scored.find((v) => v.mmsi === heroMmsi) : undefined;
  const rest = scored.filter((v) => v.mmsi !== heroMmsi).sort((a, b) => b.suspicion - a.suspicion);
  const top = (hero ? [hero, ...rest] : rest).slice(0, 4);
  const anyBreach = top[0] && top[0].suspicion >= 0.9;

  return (
    <>
      <div className="rail-head">
        <span className={`dot ${anyBreach ? "breach" : top[0] && top[0].suspicion >= 0.5 ? "alerting" : "nominal"}`} />
        ALERT FEED
      </div>
      {top.length === 0 ? (
        <div className="rail-item" style={{ borderLeftColor: "var(--ink-dim, #5E7088)" }}>
          <div className="r2">No scored vessels at this instant — scrub onto a flagged incident.</div>
        </div>
      ) : (
        top.map((v) => {
          const hex = colorHexForSuspicion(v.suspicion);
          const fac = factors(v);
          return (
            <div
              key={v.mmsi}
              className="rail-item"
              style={{ borderLeftColor: hex }}
              onClick={() => onFocus(v)}
              title="center map on vessel"
            >
              <div className="r1">
                <span className="nm">
                  {v.mmsi === heroMmsi && <span className="primary-tag">PRIMARY CUE</span>}
                  {v.name}
                </span>
                <span className="sc" style={{ color: hex }}>
                  {v.suspicion.toFixed(2)}
                </span>
              </div>
              <div className="r2">{v.why}</div>
              {fac && <div className="r2 factors">{fac}</div>}
              <div className="r3">
                {fmtZ(t).slice(11)} · {v.lat.toFixed(2)}N {v.lon.toFixed(2)}E · {bandForScore(v.suspicion).toUpperCase()}
              </div>
            </div>
          );
        })
      )}
    </>
  );
}
