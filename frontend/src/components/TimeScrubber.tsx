import { useCallback, useEffect, useRef } from "react";
import type { ReplayClock } from "../lib/clock";
import { INCIDENTS, WINDOW_END, WINDOW_START, fmtZ } from "../lib/clock";

const SPAN = WINDOW_END - WINDOW_START;
const STEP_SECONDS = 30; // one frame = the AIS keyframe-thinning interval
const STEP_FAST_SECONDS = 3600; // coarse tier — ±1 h

export default function TimeScrubber({ clock }: { clock: ReplayClock }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const frac = (clock.t - WINDOW_START) / SPAN;

  // Latest clock via ref so step() / keyboard handlers stay stable (the clock
  // object is a fresh literal every frame while playing).
  const clockRef = useRef(clock);
  clockRef.current = clock;

  // Step the clock by a fixed delta and pause, so you can inspect a precise
  // instant frame by frame.
  const step = useCallback((deltaSec: number) => {
    const c = clockRef.current;
    if (c.playing) c.toggle();
    c.seek(c.t + deltaSec * 1000);
  }, []);

  // ←/→ step a frame; Shift+←/→ jump ±1 h (keyboard equivalents of the buttons).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        step(e.shiftKey ? STEP_FAST_SECONDS : STEP_SECONDS);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        step(e.shiftKey ? -STEP_FAST_SECONDS : -STEP_SECONDS);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);

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
      <div className="transport">
        <button
          className="step-btn step-fast"
          onClick={() => step(-STEP_FAST_SECONDS)}
          title="back 1 hour · Shift+← · pauses"
        >
          ◀◀
        </button>
        <button
          className="step-btn"
          onClick={() => step(-STEP_SECONDS)}
          title={`previous frame (−${STEP_SECONDS}s) · ← · pauses`}
        >
          ◀
        </button>
        <button className="play-btn" onClick={clock.toggle} title={clock.playing ? "pause" : "play"}>
          <span className={clock.playing ? "pause" : "tri"} />
        </button>
        <button
          className="step-btn"
          onClick={() => step(STEP_SECONDS)}
          title={`next frame (+${STEP_SECONDS}s) · → · pauses`}
        >
          ▶
        </button>
        <button
          className="step-btn step-fast"
          onClick={() => step(STEP_FAST_SECONDS)}
          title="forward 1 hour · Shift+→ · pauses"
        >
          ▶▶
        </button>
      </div>
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
        {INCIDENTS.map((inc) => {
          const left = ((inc.t - WINDOW_START) / SPAN) * 100;
          return <div key={inc.label} className="tick" style={{ left: `${left}%` }} title={inc.label} />;
        })}
        <div className="handle" style={{ left: `${frac * 100}%` }} />
      </div>
      <span className="scrub-time">
        {fmtZ(clock.t)} <em>/ DANISH AIS · 2022–2026</em>
      </span>
    </footer>
  );
}
