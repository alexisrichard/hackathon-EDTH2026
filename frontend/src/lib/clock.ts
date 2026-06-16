/**
 * Replay clock — sim time driven by requestAnimationFrame.
 *
 * Spans the full AIS archive (2022-01 → 2026-05). Track tiles are loaded per
 * day on demand (see TileManager), so the clock ranges over years while only a
 * day's worth of keyframes is ever in memory.
 */
import { useEffect, useRef, useState } from "react";

// Full archive window.
export const WINDOW_START = Date.UTC(2022, 0, 1, 0, 0, 0);
export const WINDOW_END = Date.UTC(2026, 4, 20, 0, 0, 0);
// Open on the catch: the 09:00 re-tasking where Yi Peng 3 becomes satellite #1.
// (Scrub back to 11-17 to watch the routine re-taskings in the lead-up.)
export const DEFAULT_T = Date.UTC(2024, 10, 18, 9, 0, 0);

// Catalogued Baltic undersea-infra incidents — ticks on the scrubber.
export const INCIDENTS: { t: number; label: string }[] = [
  { t: Date.UTC(2022, 8, 26), label: "NORD STREAM" },
  { t: Date.UTC(2023, 9, 8), label: "BALTICCONNECTOR" },
  { t: Date.UTC(2024, 10, 17), label: "C-LION1 / YI PENG 3" },
  { t: Date.UTC(2024, 11, 25), label: "ESTLINK 2 / EAGLE S" },
  { t: Date.UTC(2025, 0, 26), label: "LV–SE CABLE" },
];

// Replay speeds (× real time). Top speeds make multi-year scrubbing usable.
export const SPEEDS = [60, 600, 3600, 21600, 86400];

export interface ReplayClock {
  t: number;
  playing: boolean;
  speed: number;
  toggle: () => void;
  cycleSpeed: () => void;
  seek: (t: number) => void;
}

export function useReplayClock(): ReplayClock {
  const [t, setT] = useState(DEFAULT_T);
  const [playing, setPlaying] = useState(false); // start paused on the hero moment
  const [speed, setSpeed] = useState(600);
  const last = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      last.current = null;
      return;
    }
    let raf = 0;
    // Throttle the data-layer re-render to ~25 fps. At 60 fps the full recompute +
    // deck render (800 vessels, labels, cues) can't fit in a 16 ms frame when zoomed
    // in, so the rAF loop monopolises the main thread and overlay toggles/clicks
    // starve. Positions interpolate smoothly at 25 fps; `last` is the last RENDER
    // time so `dt` stays accurate regardless of the throttle.
    const FRAME_MS = 40;
    const step = (now: number) => {
      if (last.current === null) {
        last.current = now;
      } else if (now - last.current >= FRAME_MS) {
        const dt = (now - last.current) * speed;
        last.current = now;
        setT((prev) => {
          const next = prev + dt;
          return next >= WINDOW_END ? WINDOW_START : next;
        });
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      last.current = null;
    };
  }, [playing, speed]);

  return {
    t,
    playing,
    speed,
    toggle: () => setPlaying((p) => !p),
    cycleSpeed: () => setSpeed((s) => SPEEDS[(SPEEDS.indexOf(s) + 1) % SPEEDS.length]),
    seek: (next: number) => setT(Math.max(WINDOW_START, Math.min(WINDOW_END, next))),
  };
}

export function fmtZ(t: number): string {
  return new Date(t).toISOString().slice(0, 19).replace("T", " ") + "Z";
}

/** UTC date key "YYYY-MM-DD" for the day containing epoch-ms t (tile filename). */
export function dayKey(t: number): string {
  return new Date(t).toISOString().slice(0, 10);
}
