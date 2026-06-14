import type { Frame, ZoneCue } from "../lib/cues";

interface Props {
  frame: Frame | null;
  t: number;
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

/** "in 2h10m" until the next re-tasking. */
function untilNext(t: number, nextRetaskTs: number | null): string | null {
  if (nextRetaskTs == null) return null;
  const ms = nextRetaskTs - t;
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function CuePanel({ frame, t, onTask }: Props) {
  const taskings = frame?.taskings ?? [];
  const continuous = frame?.isTimeseries && frame.cadenceH != null;
  const next = untilNext(t, frame?.nextRetaskTs ?? null);

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
        {continuous ? `SATELLITE TASKING · ${frame!.nSat}×` : "TASK-NEXT QUEUE"}
      </div>

      {frame && taskings.length ? (
        <>
          <div className="cue-scenario">
            {continuous ? (
              <>
                {frame.label} · re-task every {frame.cadenceH}h · current {frame.at.slice(5, 16).replace("T", " ")}Z
                {next && <span className="cue-next"> · next in {next}</span>}
              </>
            ) : (
              <>{frame.label} · cued as-of {frame.at.slice(0, 16).replace("T", " ")}Z</>
            )}
          </div>
          {taskings.map((c) => (
            <div key={c.rank} className={`cue-item ${c.rank === 1 ? "" : "upcoming"}`}>
              <div className="r1">
                <span className="rank">{continuous ? `SAT ${c.rank}` : `#${c.rank}`}</span>
                <span className={`chip ${chipClass(c.sensor)}`}>{c.sensor}</span>
                <span className="sc">{c.score.toFixed(2)}</span>
              </div>
              <div className="r2">
                BOX {c.bbox[0].toFixed(2)}–{c.bbox[2].toFixed(2)}E · {c.bbox[1].toFixed(2)}–{c.bbox[3].toFixed(2)}N
              </div>
              <div className="why">{c.why}</div>
              <TermBars terms={c.terms} />
              <button className="btn primary" onClick={() => onTask(c)}>
                Point {c.sensor} here
              </button>
            </div>
          ))}
          <div className="cue-foot">{taskings[0]?.disclaimer ?? "Defensive collection cue; not for targeting."}</div>
        </>
      ) : (
        <div className="cue-item upcoming">
          <div className="r1">
            <span className="rank">—</span>
            <span className="chip sar">SAR</span>
            <span className="sc">—</span>
          </div>
          <div className="why">
            No active cues here — either an empty theatre, or the live backend isn't running.
            Start it: <code>cd backend &amp;&amp; uvicorn app.main:app --port 8077</code>. Precomputed
            windows (C-Lion1 2024-11-17/18, Nord Stream 2022-09-26) work without it.
          </div>
        </div>
      )}
    </>
  );
}
