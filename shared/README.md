# shared/ — the contracts between lanes

These files are the **interfaces** that connect backend, scoring, and frontend. They change rarely and **only via PR + a ping to the team** — a silent change here breaks someone else's lane.

- [`api_contract.md`](api_contract.md) — the backend ↔ frontend API shape. Agree it Friday; mock against it until live.
- `scenarios.json` — named incident scenarios for the replay/demo (date, AOI bbox, suspect vessel, one-line narrative). Curate from `../data/reference/incidents.csv`.

Owner: Shared / Lead (Alexis). See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md) §4.
