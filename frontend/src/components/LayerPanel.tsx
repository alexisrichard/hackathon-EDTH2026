import type { LayerToggles } from "./MapView";

interface Props {
  toggles: LayerToggles;
  onChange: (next: LayerToggles) => void;
}

const LABELS: [keyof LayerToggles, string][] = [
  ["jurisdiction", "Jurisdictions (EEZ · 12nm)"],
  ["infrastructure", "Cables & pipelines"],
  ["geopoints", "Geopoints (scored)"],
  ["heatmap", "Strategic heatmap"],
  ["vessels", "AIS vessels"],
  ["labels", "Vessel labels"],
];

export default function LayerPanel({ toggles, onChange }: Props) {
  return (
    <div className="float layer-panel">
      <div className="hd">Overlays</div>
      {LABELS.map(([key, label]) => (
        <label key={key}>
          <input
            type="checkbox"
            checked={toggles[key]}
            onChange={(e) => onChange({ ...toggles, [key]: e.target.checked })}
          />
          {label}
        </label>
      ))}
    </div>
  );
}
