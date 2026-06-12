import {
  INFRA_THEMES,
  VESSEL_GROUP_LABELS,
  type OverlayState,
  type VesselGroup,
} from "../lib/overlays";

interface Props {
  overlays: OverlayState;
  onChange: (next: OverlayState) => void;
}

function Row({
  label,
  checked,
  onToggle,
  disabled,
  hint,
}: {
  label: string;
  checked: boolean;
  onToggle?: () => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <label className={disabled ? "disabled" : ""} title={hint}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
      {label}
    </label>
  );
}

export default function LayerPanel({ overlays, onChange }: Props) {
  const set = (next: Partial<OverlayState>) => onChange({ ...overlays, ...next });

  const vesselGroups = Object.keys(VESSEL_GROUP_LABELS) as VesselGroup[];

  return (
    <div className="float layer-panel">
      <div className="hd">Geography</div>
      <Row
        label="Country borders"
        checked={overlays.geo.borders}
        onToggle={() => set({ geo: { ...overlays.geo, borders: !overlays.geo.borders } })}
      />
      <Row
        label="Territorial seas (12nm)"
        checked={overlays.geo.territorial}
        onToggle={() => set({ geo: { ...overlays.geo, territorial: !overlays.geo.territorial } })}
      />
      <Row
        label="EEZ"
        checked={overlays.geo.eez}
        onToggle={() => set({ geo: { ...overlays.geo, eez: !overlays.geo.eez } })}
      />
      <Row label="Rescue zones (SRR)" checked={false} disabled hint="no open dataset yet — TODO" />

      <div className="hd">Infrastructure</div>
      {(Object.keys(INFRA_THEMES) as (keyof OverlayState["infra"])[]).map((theme) => (
        <Row
          key={theme}
          label={INFRA_THEMES[theme].label}
          checked={overlays.infra[theme]}
          onToggle={() => set({ infra: { ...overlays.infra, [theme]: !overlays.infra[theme] } })}
        />
      ))}

      <div className="hd">Vessels</div>
      {vesselGroups.map((g) => (
        <Row
          key={g}
          label={VESSEL_GROUP_LABELS[g]}
          checked={overlays.vessels[g]}
          onToggle={() => set({ vessels: { ...overlays.vessels, [g]: !overlays.vessels[g] } })}
        />
      ))}
      <Row
        label="Labels"
        checked={overlays.vessels.labels}
        onToggle={() => set({ vessels: { ...overlays.vessels, labels: !overlays.vessels.labels } })}
      />

      <div className="hd">Analysis</div>
      <Row
        label="Strategic heatmap"
        checked={overlays.analysis.heatmap}
        onToggle={() => set({ analysis: { heatmap: !overlays.analysis.heatmap } })}
      />
    </div>
  );
}
