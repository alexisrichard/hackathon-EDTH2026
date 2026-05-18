# Kaggle maritime datasets — investigation TODO

Found via Kaggle search "maritime" / "AIS anomaly". Kaggle dataset pages are
JS-rendered; details require either visiting in a browser OR using the Kaggle
API (`pip install kaggle`, then `~/.kaggle/kaggle.json` with API token from
https://www.kaggle.com/settings/account).

## Datasets to evaluate, in priority order

| # | Slug | Why it might be valuable | Source URL |
|---|------|--------------------------|------------|
| 1 | `eminserkanerdonmez/ais-dataset` | Kattegat Strait — IS in our Baltic bbox; could include vessel transitions through a chokepoint | https://www.kaggle.com/datasets/eminserkanerdonmez/ais-dataset |
| 2 | `aswinjose/ais-maritime-data` | Generic AIS — may have pre-labeled anomaly examples | https://www.kaggle.com/datasets/aswinjose/ais-maritime-data |
| 3 | `marsalanakhtar/ais-data-for-ships` | Same — AIS positions to test pipeline | https://www.kaggle.com/datasets/marsalanakhtar/ais-data-for-ships |
| 4 | `dhirajpatra/shipping-automatic-identification-system-ais` | Same | https://www.kaggle.com/datasets/dhirajpatra/shipping-automatic-identification-system-ais |
| 5 | `gauravduttakiit/vessel-identification` | Vessel metadata / labeled ship types — useful for class-coherence model | https://www.kaggle.com/datasets/gauravduttakiit/vessel-identification |
| 6 | `ibrahimonmars/global-cargo-ships-dataset` | Cargo ships specifically — vessel registry stub | https://www.kaggle.com/datasets/ibrahimonmars/global-cargo-ships-dataset |
| 7 | `siddharthkumarsah/ships-in-aerial-images` | Optical ship detection — could train Sentinel-2 dark-vessel detector | https://www.kaggle.com/datasets/siddharthkumarsah/ships-in-aerial-images |
| 8 | `vinayakshanawad/ships-dataset` | Ship images dataset | https://www.kaggle.com/datasets/vinayakshanawad/ships-dataset |

## Setting up Kaggle access

```bash
pip install kaggle
# Get your API token from https://www.kaggle.com/settings/account ("Create New API Token")
# Save the downloaded kaggle.json to ~/.kaggle/kaggle.json (chmod 600 on macOS/Linux)
mkdir -p ~/.kaggle && mv kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json  # macOS/Linux only

# Then list files or download
kaggle datasets files eminserkanerdonmez/ais-dataset
kaggle datasets download -d eminserkanerdonmez/ais-dataset -p data/reference/raw/kaggle/
unzip data/reference/raw/kaggle/ais-dataset.zip -d data/reference/raw/kaggle/ais-dataset/
```

## Priority for the demo

**Highest leverage** if it pans out: #1 Kattegat dataset — it's literally
in our bbox. Could provide a labeled sample to benchmark our pipeline
against, or expose vessel-behavior patterns at a Baltic chokepoint we'd
otherwise need to derive from raw Danish AIS.

**Skip for now**: #7/#8 ship-image datasets — useful only if we pivot to
optical satellite detection during the hackathon. Defer.

## What to do once you have Kaggle access set up

For each promising dataset, run:
```bash
kaggle datasets metadata eminserkanerdonmez/ais-dataset    # licence, last update
kaggle datasets files eminserkanerdonmez/ais-dataset       # file list + sizes
```

If license is permissive (CC0, CC-BY, or "Other - see description"),
download and add a row to `data/SOURCES.md` with the license and source URL.
If license is unclear, default to research-only use and DO NOT bake into
anything redistributable.
