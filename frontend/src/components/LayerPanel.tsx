import { useEffect, useRef } from "react";
import {
  INFRA_CATS,
  INFRA_THEME_ORDER,
  catsInTheme,
  DEFAULT_OVERLAYS,
  VESSEL_GROUP_LABELS,
  type InfraCat,
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

/** Group header with a select-all / deselect-all master (indeterminate when mixed). */
function GroupHead({ title, states, onAll }: { title: string; states: boolean[]; onAll: (v: boolean) => void }) {
  const all = states.length > 0 && states.every(Boolean);
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

  const setInfra = (cat: InfraCat, v: boolean) => set({ infra: { ...overlays.infra, [cat]: v } });
  const setInfraMany = (cats: InfraCat[], v: boolean) => {
    const infra = { ...overlays.infra };
    cats.forEach((c) => (infra[c] = v));
    set({ infra });
  };

  return (
    <div className="float layer-panel">
      <button
        type="button"
        className="layer-default"
        onClick={() => onChange(DEFAULT_OVERLAYS)}
        title="Show only the relevant ships (not Other) + telecom cables + pipelines"
      >
        Default view
      </button>
      <GroupHead
        title="Geography"
        states={[overlays.geo.borders, overlays.geo.territorial, overlays.geo.eez]}
        onAll={(v) => set({ geo: { borders: v, territorial: v, eez: v } })}
      />
      <div className="layer-rows">
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
        <Row label="EEZ" checked={overlays.geo.eez} onToggle={() => set({ geo: { ...overlays.geo, eez: !overlays.geo.eez } })} />
        <Row label="Rescue zones (SRR)" checked={false} disabled hint="no open dataset yet — TODO" />
      </div>

      <div className="section-label">Infrastructure</div>
      {INFRA_THEME_ORDER.map((theme) => {
        const cats = catsInTheme(theme);
        return (
          <div key={theme} className="infra-theme">
            <GroupHead
              title={theme}
              states={cats.map((c) => overlays.infra[c])}
              onAll={(v) => setInfraMany(cats, v)}
            />
            <div className="layer-rows">
              {cats.map((c) => (
                <Row
                  key={c}
                  label={INFRA_CATS[c].label}
                  checked={overlays.infra[c]}
                  onToggle={() => setInfra(c, !overlays.infra[c])}
                />
              ))}
            </div>
          </div>
        );
      })}

      <GroupHead
        title="Vessels"
        states={vesselGroups.map((g) => overlays.vessels[g])}
        onAll={(v) =>
          set({
            vessels: { ...overlays.vessels, cargo: v, tanker: v, fishing: v, passenger: v, military: v, other: v },
          })
        }
      />
      <div className="layer-rows">
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
      </div>

      <div className="hd">Fishing</div>
      <div className="layer-rows">
        <Row
          label="Fishing intensity (HELCOM)"
          checked={overlays.fishing.intensity}
          onToggle={() => set({ fishing: { intensity: !overlays.fishing.intensity } })}
          hint="Where trawling actually happens — a 'fishing' vessel working outside these grounds is the tell. SW Baltic coverage."
        />
      </div>

      <GroupHead
        title="Cueing engine"
        states={[overlays.cueing.cues, overlays.cueing.sar]}
        onAll={(v) => set({ cueing: { cues: v, sar: v } })}
      />
      <div className="layer-rows">
        <Row
          label="Task-next cues"
          checked={overlays.cueing.cues}
          onToggle={() => set({ cueing: { ...overlays.cueing, cues: !overlays.cueing.cues } })}
          hint="The ranked task-next queue from the zone scoring engine — boxes to point a sensor at, brightest = #1. Lights up on a flagged incident day."
        />
        <Row
          label="SAR dark contacts"
          checked={overlays.cueing.sar}
          onToggle={() => set({ cueing: { ...overlays.cueing, sar: !overlays.cueing.sar } })}
          hint="Synthetic-aperture-radar detections with no AIS within 2 km — vessels with no broadcast identity. The Nord Stream signature."
        />
      </div>

      <div className="hd">Analysis</div>
      <div className="layer-rows">
        <Row
          label="Strategic heatmap"
          checked={overlays.analysis.heatmap}
          onToggle={() => set({ analysis: { heatmap: !overlays.analysis.heatmap } })}
        />
      </div>

      <GroupHead
        title="Incidents — dev"
        states={[overlays.incidentsDev.points, overlays.incidentsDev.coverage]}
        onAll={(v) => set({ incidentsDev: { points: v, coverage: v } })}
      />
      <div className="layer-rows">
        <Row
          label="Incident points (9)"
          checked={overlays.incidentsDev.points}
          onToggle={() =>
            set({ incidentsDev: { ...overlays.incidentsDev, points: !overlays.incidentsDev.points } })
          }
          hint="The 9 known Baltic seabed-infrastructure incidents, coloured by whether we have on-site AIS that day (green=reliable, amber=marginal, red=gap)."
        />
        <Row
          label="AIS coverage zone"
          checked={overlays.incidentsDev.coverage}
          onToggle={() =>
            set({ incidentsDev: { ...overlays.incidentsDev, coverage: !overlays.incidentsDev.coverage } })
          }
          hint="Where Danish AIS reliably receives vessels, derived from real day-files (≥30 distinct vessels/cell = reliable, 5–29 = marginal). Effectively nothing east of Gotland."
        />
      </div>
    </div>
  );
}
