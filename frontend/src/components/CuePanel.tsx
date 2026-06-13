import type { ScenarioPayload, ZoneCue } from "../lib/cues";

interface Props {
  cues: ZoneCue[];
  scenario: ScenarioPayload | null;
  onTask: (cue: ZoneCue) => void;
}

const TERM_LABELS: [keyof ZoneCue["terms"], string][] = [
  ["infra", "infra"],
  ["vessel_risk", "risk"],
  ["live_anomaly", "live"],
  ["sar", "sar"],
  ["dark_density", "dark"],
];

const chipClass = (sensor: string) => (sensor.toLowerCase() === "optical" ? "optical" : "sar");

function TermBars({ terms }: { terms: ZoneCue["terms"] }) {
  return (
    <div className="cue-terms">
      {TERM_LABELS.map(([k, label]) => (
        <div key={k} className="term" title={`${label} ${terms[k].toFixed(2)}`}>
          <span className="tl">{label}</span>
          <span className="tbar">
            <span className="tfill" style={{ width: `${Math.round(terms[k] * 100)}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}

export default function CuePanel({ cues, scenario, onTask }: Props) {
  return (
    <>
      <div className="rail-head">
        <svg width="13" height="13" viewBox="0 0 24 24" style={{ color: "var(--sensor-sar)" }}>
          <path
            d="M4 8 V4 H8 M16 4 H20 V8 M20 16 V20 H16 M8 20 H4 V16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="square"
          />
          <circle cx="12" cy="12" r="2.2" fill="currentColor" />
        </svg>
        TASK-NEXT QUEUE
      </div>

      {scenario && cues.length ? (
        <>
          <div className="cue-scenario">
            {scenario.label} · cued as-of {scenario.at.slice(0, 16).replace("T", " ")}Z
          </div>
          {cues.map((c) => (
            <div key={c.rank} className={`cue-item ${c.rank === 1 ? "" : "upcoming"}`}>
              <div className="r1">
                <span className="rank">#{c.rank}</span>
                <span className={`chip ${chipClass(c.sensor)}`}>{c.sensor}</span>
                <span className="sc">{c.score.toFixed(2)}</span>
              </div>
              <div className="r2">
                BOX {c.bbox[0].toFixed(2)}–{c.bbox[2].toFixed(2)}E · {c.bbox[1].toFixed(2)}–{c.bbox[3].toFixed(2)}N
              </div>
              <div className="why">{c.why}</div>
              <TermBars terms={c.terms} />
              <button className="btn primary" onClick={() => onTask(c)}>
                Task {c.sensor}
              </button>
            </div>
          ))}
          <div className="cue-foot">{cues[0]?.disclaimer ?? "Defensive collection cue; not for targeting."}</div>
        </>
      ) : (
        <div className="cue-item upcoming">
          <div className="r1">
            <span className="rank">—</span>
            <span className="chip sar">SAR</span>
            <span className="sc">—</span>
          </div>
          <div className="why">
            No scored incident at this time. Scrub the timeline onto a flagged incident (C-Lion1 /
            Nord Stream) to see the engine's live task-next queue.
          </div>
        </div>
      )}
    </>
  );
}
