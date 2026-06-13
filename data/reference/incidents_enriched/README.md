# Enriched incident dossiers

These files turn selected rows from `../incidents.csv` into traceable incident
dossiers for replay, scoring evaluation, and dashboard explanations.

They are defensive maritime-domain-awareness references. They must not be used
to label a vessel or crew as hostile. A vessel association, a physical cause,
criminal intent, and a court outcome are separate questions.

## Confidence scale

- `high`: directly supported by a competent authority or infrastructure owner.
- `medium`: supported by multiple observations, but timing, location, or legal
  interpretation is incomplete.
- `low`: preliminary, approximate, or based on a single indirect source.
- `unknown`: the available sources do not support a conclusion.

## Important fields

- `event_time`: the best replay anchor and its precision. It is not necessarily
  the exact instant of physical contact.
- `classification.physical_cause`: what physically damaged the asset.
- `classification.intent_assessment`: whether deliberate action is established.
- `classification.legal_status`: the latest legal or investigative status in
  the cited source set.
- `timeline`: separates the event, later technical findings, and later legal
  findings so the demo does not use hindsight as if it were known live.
- `evidence`: observations that can support an explainable cue.
- `local_data`: data already present in this repository. Weather values are
  model/reanalysis samples, not observations made aboard the vessel.
- `demo_guidance`: safe wording for a replay and the signals that a defensive
  cueing system could reasonably surface.

## Known limitations

- Coordinates are approximate centroids or segment midpoints, not forensic
  contact points.
- The repository does not yet contain validated AIS tracks for all three
  vessels. Do not invent missing tracks.
- Sentinel catalogue matches show scene availability, not proof that a scene
  depicts the vessel, anchor, or damage.
- The Global Fishing Watch summary has a validated exact identity match only
  for `VEZHEN` (`MMSI 229659000`, `IMO 9937270`). Similar `DE ZHEN` records are
  excluded as name collisions.
- Public findings can change. Each dossier records `last_reviewed_utc` and the
  source publication dates used.

