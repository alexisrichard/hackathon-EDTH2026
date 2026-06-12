import { useEffect, useRef } from "react";
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

/** Group header with a select-all / deselect-all master checkbox
 *  (indeterminate when the group is mixed). */
function GroupHead({ title, states, onAll }: { title: string; states: boolean[]; onAll: (v: boolean) => void }) {
  const all = states.every(Boolean);
  const none = states.every((s) => !s);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = !all && !none;
  }, [all, none]);
  return (
    <div className="hd hd-row">
      <label title={all ? "deselect all" : "select all"}>
        <input ref={ref} type="checkbox" checked={all} onChange={() => onAll(!all)} />
        {title}
      </label>
    </div>
  );
}

export default function LayerPanel({ overlays, onChange }: Props) {
  const set = (next: Partial<OverlayState>) => onChange({ ...overlays, ...next });
  const vesselGroups = Object.keys(VESSEL_GROUP_LABELS) as VesselGroup[];
  const infraThemes = Object.keys(INFRA_THEMES) as (keyof OverlayState["infra"])[];

  const setAllGeo = (v: boolean) => set({ geo: { borders: v, territorial: v, eez: v } });
  const setAllInfra = (v: boolean) =>
    set({ infra: { energy: v, telecom: v, transport: v, military: v } });
  const setAllVessels = (v: boolean) =>
    set({
      vessels: {
        ...overlays.vessels,
        cargo: v,
        tanker: v,
        fishing: v,
        passenger: v,
        military: v,
        other: v,
      },
    });

  return (
    <div className="float layer-panel">
      <GroupHead
        title="Geography"
        states={[overlays.geo.borders, overlays.geo.territorial, overlays.geo.eez]}
        onAll={setAllGeo}
      />
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

      <GroupHead title="Infrastructure" states={infraThemes.map((t) => overlays.infra[t])} onAll={setAllInfra} />
      {infraThemes.map((theme) => (
        <Row
          key={theme}
          label={INFRA_THEMES[theme].label}
          checked={overlays.infra[theme]}
          onToggle={() => set({ infra: { ...overlays.infra, [theme]: !overlays.infra[theme] } })}
        />
      ))}

      <GroupHead title="Vessels" states={vesselGroups.map((g) => overlays.vessels[g])} onAll={setAllVessels} />
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
