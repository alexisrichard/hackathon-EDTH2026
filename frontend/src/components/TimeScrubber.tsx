import { useCallback, useRef } from "react";
import type { ReplayClock } from "../lib/clock";
import { BREACH_T, WINDOW_END, WINDOW_START, fmtZ } from "../lib/clock";

export default function TimeScrubber({ clock }: { clock: ReplayClock }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const frac = (clock.t - WINDOW_START) / (WINDOW_END - WINDOW_START);
  const breachFrac = (BREACH_T - WINDOW_START) / (WINDOW_END - WINDOW_START);

  const seekFromEvent = useCallback(
    (clientX: number) => {
      const el = trackRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
      clock.seek(WINDOW_START + f * (WINDOW_END - WINDOW_START));
    },
    [clock],
  );

  return (
    <footer className="scrub">
      <button className="play-btn" onClick={clock.toggle} title={clock.playing ? "pause" : "play"}>
        <span className={clock.playing ? "pause" : "tri"} />
      </button>
      <button className="speed" onClick={clock.cycleSpeed} title="cycle replay speed">
        {clock.speed}×
      </button>
      <div
        ref={trackRef}
        className="track"
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          seekFromEvent(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) seekFromEvent(e.clientX);
        }}
      >
        <div className="rail-line" />
        <div className="played" style={{ width: `${frac * 100}%` }} />
        <div className="tick" style={{ left: `${breachFrac * 100}%` }} title="Estlink 2 cut — 14:00Z" />
        <div className="tick-label" style={{ left: `${breachFrac * 100}%` }}>
          ESTLINK 2
        </div>
        <div className="handle" style={{ left: `${frac * 100}%` }} />
      </div>
      <span className="scrub-time">
        {fmtZ(clock.t)} <em>/ EAGLE S REPLAY · HELD-OUT INCIDENT</em>
      </span>
    </footer>
  );
}
