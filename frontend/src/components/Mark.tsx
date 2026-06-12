/** HEIMDALL mark — R5 Apex Cue (brand/heimdall_brand_identity.html §02).
 *  Acts as a status light: cyan watching · amber alerting · red breach. */

interface Props {
  size?: number;
  color?: string;
}

export default function Mark({ size = 22, color = "var(--cyan)" }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" style={{ color, flex: "none" }}>
      <rect x="25.5" y="85.5" width="9" height="9" fill="currentColor" />
      <g fill="none" stroke="currentColor" strokeWidth="6.5" strokeLinecap="butt" strokeLinejoin="miter">
        <path d="M51.25 84.30 L48.05 71.95 L35.70 68.75" />
        <path d="M66.71 80.16 L61.17 58.83 L39.84 53.29" />
        <path d="M82.16 76.01 L77.28 57.22" />
        <path d="M43.99 37.84 L62.78 42.72" />
      </g>
      <path
        d="M64.79 42.21 V36.21 H70.79 M77.79 36.21 H83.79 V42.21 M83.79 49.21 V55.21 H77.79 M70.79 55.21 H64.79 V49.21"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.2"
        strokeLinecap="square"
      />
    </svg>
  );
}
