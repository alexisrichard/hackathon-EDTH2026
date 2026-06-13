import type { Cue } from "./MapView";

interface Props {
  cue: Cue | null;
  suspicion: number;
  onTask: () => void;
}

export default function CuePanel({ cue, suspicion, onTask }: Props) {
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
      <div className={`cue-item ${cue ? "" : "upcoming"}`}>
        <div className="r1">
          <span className="rank">#1</span>
          <span className="chip sar">SAR</span>
          <span className="sc">{cue ? suspicion.toFixed(2) : "—"}</span>
        </div>
        {cue ? (
          <>
            <div className="r2">
              BOX {cue.bbox[0].toFixed(2)}–{cue.bbox[2].toFixed(2)}E · {cue.bbox[1].toFixed(2)}–{cue.bbox[3].toFixed(2)}N
            </div>
            <div className="why">{cue.label.replace("CUE-01 · SAR · ", "")} driving cell score — recommend a SAR pass.</div>
            <button className="btn primary" onClick={onTask}>
              Task
            </button>
          </>
        ) : (
          <div className="why">No active recommendation — engine watching the theatre.</div>
        )}
      </div>
      <div className="cue-item upcoming">
        <div className="r1">
          <span className="rank">#2</span>
          <span className="chip optical">OPTICAL</span>
          <span className="sc">—</span>
        </div>
        <div className="why">Awaiting scoring-tier output (Côme's engine).</div>
      </div>
    </>
  );
}
