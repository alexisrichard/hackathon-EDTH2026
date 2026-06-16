import Mark from "./Mark";
import { fmtZ } from "../lib/clock";

interface Props {
  t: number;
  speed: number;
  /** max suspicion in the theatre right now — drives the status light */
  maxSuspicion: number;
}

export default function TopBar({ t, speed, maxSuspicion }: Props) {
  const status = maxSuspicion >= 0.9 ? "breach" : maxSuspicion >= 0.5 ? "alerting" : "nominal";
  const markColor =
    status === "breach" ? "var(--breach)" : status === "alerting" ? "var(--alert)" : "var(--cyan)";
  return (
    <header className="topbar">
      <div className="brand">
        <Mark size={22} color={markColor} />
        <b>HEIMDALL</b>
      </div>
      <div className="div" />
      <nav>
        <span className="on">THEATRE MAP</span>
        <span title="day-of work">INCIDENTS</span>
        <span title="day-of work">CUEING</span>
        <span title="day-of work">REPLAY</span>
      </nav>
      <div className="clock">
        <span className={`dot ${status}`} />
        {fmtZ(t)}&nbsp;&nbsp;REPLAY {speed}× · BALTIC/NORTH SEA
      </div>
    </header>
  );
}
