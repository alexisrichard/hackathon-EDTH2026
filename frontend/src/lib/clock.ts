/**
 * Replay clock — sim time driven by requestAnimationFrame.
 *
 * V1 window: the Eagle S / Estlink 2 day (2024-12-25, held-out incident).
 * The window will become scenario-driven (shared/scenarios.json) later.
 */
import { useEffect, useRef, useState } from "react";

export const WINDOW_START = Date.UTC(2024, 11, 25, 10, 0, 0);
export const WINDOW_END = Date.UTC(2024, 11, 25, 16, 0, 0);
/** Ground truth: Estlink 2 went down 2024-12-25 ~14:00Z (cue must fire BEFORE). */
export const BREACH_T = Date.UTC(2024, 11, 25, 14, 0, 0);
export const DEFAULT_T = Date.UTC(2024, 11, 25, 13, 10, 0);

export const SPEEDS = [1, 10, 60, 300, 900];

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
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(60);
  const last = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      last.current = null;
      return;
    }
    let raf = 0;
    const step = (now: number) => {
      if (last.current !== null) {
        const dt = (now - last.current) * speed;
        setT((prev) => {
          const next = prev + dt;
          return next >= WINDOW_END ? WINDOW_START : next; // loop the replay
        });
      }
      last.current = now;
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
