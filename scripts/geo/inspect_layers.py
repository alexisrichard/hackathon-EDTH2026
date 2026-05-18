"""Quick sanity check on fetched OSM layers.

For each GeoJSON in data/geo/, print:
  - feature count
  - geometry type breakdown
  - tag-key frequency
  - any features whose tags contain known infrastructure names
    (Nord Stream, Balticconnector, Estlink, C-Lion1, etc.)
"""

import json
from collections import Counter
from pathlib import Path

KNOWN = [
    "nord stream", "balticconnector", "estlink", "norned", "nordbalt",
    "swepol", "c-lion", "c-lion1", "bcs east", "yamal",
    "kaliningrad", "baltiysk", "kronstadt",
]


def inspect(path: Path) -> None:
    print(f"\n=== {path.name} ===")
    gj = json.loads(path.read_text(encoding="utf-8"))
    feats = gj["features"]
    print(f"  features: {len(feats)}")
    geom_types = Counter(f["geometry"]["type"] for f in feats)
    print(f"  geometry: {dict(geom_types)}")

    tag_counter: Counter[str] = Counter()
    for f in feats:
        for k in f["properties"]:
            tag_counter[k] += 1
    top_tags = tag_counter.most_common(12)
    print(f"  top tags: {top_tags}")

    hits = []
    for f in feats:
        text = " ".join(str(v).lower() for v in f["properties"].values())
        for needle in KNOWN:
            if needle in text:
                name = f["properties"].get("name") or f["properties"].get("operator") or f["properties"].get("ref") or "(no name)"
                hits.append((needle, name, f["properties"].get("osm_id")))
                break
    if hits:
        print(f"  named-infrastructure hits ({len(hits)}):")
        for needle, name, osm_id in hits[:15]:
            print(f"    [{needle}] {name}  {osm_id}")
    else:
        print("  named-infrastructure hits: none")


def main() -> None:
    for p in sorted(Path("data/geo").glob("*.geojson")):
        inspect(p)


if __name__ == "__main__":
    main()
