import { CUE_BBOX, CUE_FIRES_T } from "../mock/fleet";
import { BREACH_T } from "../lib/clock";

interface Props {
  t: number;
  onTask: () => void;
}

export default function CuePanel({ t, onTask }: Props) {
  const live = t >= CUE_FIRES_T;
  const [x0, y0, x1, y1] = CUE_BBOX;
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
      <div className={`cue-item ${live ? "" : "upcoming"}`}>
        <div className="r1">
          <span className="rank">#1</span>
          <span className="chip sar">SAR</span>
          <span className="sc">{live ? (t >= BREACH_T ? "1.00" : "0.93") : "—"}</span>
        </div>
        <div className="r2">
          BOX {x0.toFixed(2)}–{x1.toFixed(2)}E · {y0.toFixed(2)}–{y1.toFixed(2)}N
        </div>
        <div className="why">
          {live
            ? "EAGLE S driving cell score; pass window closes 14:00Z."
            : "No active recommendation — engine watching the theatre."}
        </div>
        <button className="btn primary" disabled={!live} onClick={onTask}>
          Task
        </button>
      </div>
      <div className="cue-item upcoming">
        <div className="r1">
          <span className="rank">#2</span>
          <span className="chip optical">OPTICAL</span>
          <span className="sc">0.41</span>
        </div>
        <div className="r2">BOX 24.60–24.95E · 59.40–59.60N</div>
        <div className="why">Anchorage drift cluster; daylight window ok.</div>
        <button className="btn secondary">Task</button>
      </div>
    </>
  );
}
