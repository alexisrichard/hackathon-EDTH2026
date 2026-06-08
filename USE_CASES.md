# Use cases — generalizing the cueing engine

**Status: forward-looking / vision.** This is *not* the committed EDTH 2026 scope (that's the
Baltic undersea-infrastructure maritime cueing engine — see [`PLAN.md`](PLAN.md)). This document
captures where the same core idea generalizes, as input for the pitch ("our approach is a general
platform, not a one-trick maritime demo") and for possible future direction.

---

## The pattern we actually built

The maritime "dark vessel" detector is one instance of a general capability:

> **Non-cooperative target detection.** Every *cooperative* tracking system — AIS for ships,
> ADS-B for planes, IFF, transponders, registries, license plates — can be **switched off or
> spoofed**. The universal high-value signal is when a **passive sensor (camera, RF, radar,
> acoustic) sees something the declared picture says isn't there, or contradicts it.** That gap
> *is* the threat.

Two force-multipliers stack on top:

1. **Online / livestream data is cheap, abundant, real-time, and dual-use** — public webcams,
   ADS-B/AIS aggregators, SDRs, social feeds, satellite revisit. → "democratized ISR" without
   classified sensors.
2. **Drones add the actuator *and* a mobile sensor** — close the OODA loop:
   **detect → dispatch → confirm → act.**

Every use case below is the same engine: **ingest a live sensor → detect → fuse against an
authoritative layer → cue.** Only the sensors, the registry, and the "dark-X" definition change.

---

## Use-case catalog

### ✈️ Air domain — the direct analog

| Use case | Live feed | Fuse with | "Dark-X" signal → payoff |
|---|---|---|---|
| **Dark aircraft** | SDR receiving ADS-B + airport/border cameras | OpenSky flight registry | On radar/camera but squawking *no* transponder → smuggling flight, border incursion |
| **Transponder spoofing** | ADS-B / AIS + RF direction-finding + camera bearing | Declared position vs. RF/optical bearing | Declared position disagrees with where the signal/optics put it → spoofing (live Baltic / Kaliningrad threat) |

### 🚁 Drones — as sensor *and* actuator

| Use case | Live feed | Fuse with | Signal → payoff |
|---|---|---|---|
| **Cue → recon-drone loop** | Any upstream sensor cue | AOI tasking | Anomaly raises a cue → drone auto-launches, flies to the box, IDs it. Closes the OODA loop — the cueing engine *with an actuator* |
| **Onboard detection + change detection** | Drone video (YOLO/supervision onboard) | Prior pass / known-asset map | "3 new vehicles at this site since yesterday" → order-of-battle from a quadcopter |
| **Counter-UAS over infrastructure** | Acoustic + RF + camera mesh around a base/plant | Authorized-flight registry / NOTAM / drone IDs | Unregistered drone over a substation → intercept (possibly by a friendly drone) |

### 📡 RF / SIGINT

| Use case | Live feed | Fuse with | Signal → payoff |
|---|---|---|---|
| **Silent-zone emissions** | SDR spectrum sweep | Expected-emitter DB + terrain/asset map | Comms or radar emissions from a "empty" square → hidden unit. The RF dark vessel |
| **Jammer localization** | Multiple SDR receivers | Triangulation / TDOA | Locate a jammer in real time → cue a drone to go image it |

### 🌐 OSINT / open-data fusion

| Use case | Live feed | Fuse with | Signal → payoff |
|---|---|---|---|
| **Open-source order-of-battle** | ADS-B (cargo flights) + AIS (ro-ro) + rail-cam networks + port webcams | Unit / asset database | Adversary military buildup detected from entirely public streams (how analysts tracked logistics into Ukraine — automated) |
| **Vehicle-of-interest re-ID** | Public traffic-camera network | Plate / vehicle re-identification | Track a vehicle of interest across a city's camera network |
| **Event geolocation** | Social-media video + nearest public webcam + satellite revisit | Geolocation / basemap | Confirm and geolocate a reported convoy/strike within minutes |

### 🏭 Critical infrastructure (land)

| Use case | Live feed | Fuse with | Signal → payoff |
|---|---|---|---|
| **Pipeline / grid / rail sabotage watch** | Fixed cameras + patrolling drones | Maintenance schedule + authorized-personnel list | Intruder, illegal tap, or sabotage. The *onshore* twin of the cable mission |
| **Base / depot perimeter** | Perimeter cameras + RF | Duty roster + vehicle whitelist | Insider and intruder detection |

### 🛰️ Space domain awareness

| Use case | Live feed | Fuse with | Signal → payoff |
|---|---|---|---|
| **Dark satellite** | Optical / radio telescope feeds | Public satellite catalog (TLE / Celestrak) | Satellite maneuvers off-catalog or appears uncatalogued → the dark vessel, in orbit |

---

## Top picks (strong, not just cool)

1. **GPS / AIS / ADS-B spoofing detection** — reuses our AIS pipeline directly, addresses a live
   Baltic threat, and is a "we already have the data" pitch.
2. **The cue → recon-drone loop** — the dramatic, demo-able evolution of what we built; a closed
   OODA loop lands well with judges.
3. **Open-source order-of-battle fusion** — biggest "wow, all from public data" factor.

---

## Pitch framing

> *"We built it for Baltic undersea cables — but it's a general **non-cooperative-detection
> platform**. The same engine ingests any live sensor, fuses it against the authoritative picture,
> and cues. Here it is for air, RF, space, and autonomous drones."*

Showing the maritime demo **generalizes** is often what separates a winning hackathon pitch from a
one-trick one.

---

## What reuses our existing EDTH stack

How fast each could be prototyped given what we've already built (AIS pipeline, AISStream live
consumer, Sentinel imagery, infrastructure/criticality geo-layers, camera capture/resolve tooling):

| Use case | Reuses |
|---|---|
| Transponder/AIS spoofing | **AIS pipeline + AISStream consumer** almost directly — add an RF/optical bearing cross-check |
| Cue → recon-drone loop | The **whole cueing-engine concept** + camera detection; swap the actuator |
| Open-source order-of-battle | **AIS** + **camera capture/resolve tooling** + **Sentinel imagery** |
| Dark aircraft | Mirror of the AIS approach with **ADS-B (OpenSky)** — same fusion architecture, new registry |
| Counter-UAS / infra watch | The **criticality / infrastructure geo-layer** scoring + camera detection |
| Dark satellite | New sensor + catalog, but the **same detect-vs-registry core** |
