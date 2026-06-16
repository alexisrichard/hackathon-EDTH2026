# HEIMDALL — Pitch Story, Slide Deck & Talk

> **Working document.** This is the *story* (narrative + slide-by-slide backdrop + speaker script) for the EDTH 2026 final pitch. Slides are **backdrops for a speaker** — minimal text, one striking visual each. The talk carries the words.
>
> Status: **V2** (rewritten after specialist review #1). See `## Revision log`.

---

## 0. The frame (assumptions — confirm)

| | |
|---|---|
| **Product name** | **Heimdall.ai** — the **wordmark** on every slide is `HEIMDALL.ai`; **spoken**, the speaker just says "Heimdall" (saying ".ai" aloud repeatedly is awkward). Norse watchman of the gods: sees across the world by day *and night*, hears the faintest sound, guards the bridge against what tries to slip across, sounds the horn when the threat comes. Used lightly, once. |
| **Format** | ~**5 minutes**, single speaker, slides as backdrop, **live app demo embedded** (~70s). 3-min compression in §7; sentences marked «cut» drop the 5-min read to a clean 5:00. |
| **Audience** | **Defense jury** — operators + MOD/NATO + defense VCs. Primary customer in the pitch: **NATO Critical Undersea Infrastructure Cell**, sold via the people who own the sensors. |
| **The one line** | *Heimdall tells you where to point your next satellite — and catches the ships that are lying about who they are.* |
| **Won't claim** | See §5. No live SAR inference on stage. No asserted *intent* for Yi Peng 3 (attribution is officially disputed — we say "suspect" and let the behavior speak). |

---

## 1. The story (the narrative arc)

One argument, nine beats. The spine: **a real crime that went unpunished → the world runs on these threads → it keeps happening, and deniability is the weapon → defenders are drowning, not blind → the catch is that ships lie → so we built three senses → each is blind alone → fused, they catch the lie → proof on a real incident → this is the cockpit, here's the wedge, here's where it goes.**

**1. Open inside the crime.** November 2024: two undersea cables — Finland–Germany, then Lithuania–Sweden — cut on consecutive days. The same bulk carrier had crossed both, on a track no normal cargo ship would fly. The investigations went nowhere. No charges. *"An accident."* That deniability **is** the weapon — and nobody was watching the one signal that would have caught it.

**2. The stakes — why a cable matters.** 99% of the world's intercontinental data — finance, the internet, military comms — runs through a few hundred cables on the seabed. Plus the pipelines that power Europe. Unguarded, unmonitored, trivially reachable.

**3. It keeps happening — cheap and deniable.** This wasn't a one-off. **Nine cuts in the Baltic since 2022** — Nord Stream, Balticconnector, C-Lion1, Estlink 2, Latvia–Sweden — roughly one every few months. The method is brutally cheap: a rusty hull and a dragged anchor — a few thousand euros to sever an artery worth billions that takes weeks to repair. Same asymmetry cheap drones brought to land war, now underwater.

**4. The real problem isn't watching — it's *choosing where to look*.** Defenders aren't blind; they're drowning. Thousands of vessels broadcasting every second. The ocean is too big, and the sensors that actually *see* — satellites — are too few and too costly to point everywhere. The real question is *where do I task my next pass, in the next hour?* That's the tip-and-cue problem, and the cueing layer barely exists. **We don't lack alerts. We lack prioritization.**

**5. And ships lie.** The one cheap, continuous, global signal is AIS — every ship broadcasting who and where it is. But AIS is *self-reported*. Spoof it, fake the identity, or switch it off. The cheapest signal is the one the adversary fully controls. A ship that wants to cut a cable just goes dark.

**6. Heimdall has three senses.**
   - **Ship Scoring — the memory.** Knows every vessel's class, history, sanctions / shadow-fleet status; scores how *out of character* its behavior is right now. **Strength:** context + history, every score explainable. **Blind spot:** it reasons on AIS — lie to it, and it believes the lie.
   - **SAR Vision — the eyes.** A detector we fine-tuned on satellite radar that picks out the ships on the actual water — through cloud, through darkness, whatever they're broadcasting. **Strength:** ground truth; radar can't be spoofed. **Blind spot:** a radar blob has no name, no history — and passes are scarce, so you must already know where to look.
   - **Geography — the map of what matters.** Every cable, pipeline, naval base, chokepoint as a criticality surface. **Strength:** turns "a ship slowed down" into "a ship slowed down *over the C-Lion1 crossing.*" **Blind spot:** alone it's just a map — everything near a cable looks busy.

**7. Alone, each is blind.** History gets lied to. Radar is anonymous. The map is noise.

**8. Fused, they catch the lie.** **AIS is what a ship *says*. SAR is what a ship *is*. The gap between them is the threat.** A radar contact with no AIS = a *dark vessel*, running silent where it shouldn't be. A vessel whose AIS appears from nowhere — no prior track, right at the scene, right on time = a *dark approach*, the classic evasion move. Lay geography over both, and the cueing engine ranks the one 50 km box that deserves the next pass — with a plain-language reason.

**9. Proof, then product, then where it goes.** Replay the real C-Lion1 / Yi Peng 3 incident: each sense alone shrugs; fused — and scored *blind*, with no look-ahead — Heimdall pulls the real culprit out of a thousand ships and ranks its box #1 the same morning, while the actual investigation took weeks and ended with no charges. That's the cockpit — a live "task-next" queue: *where, when, which sensor, why.* The doctrine and budget already exist (NATO CUI Cell, French seabed doctrine, EU cable mandate); the data is open. What's missing — the fusion-and-cueing layer — is exactly what we built. Today: the Baltic, AIS + radar. Tomorrow: every contested sea, every sense. **The seabed is the new front line. Heimdall is the watch.**

---

## 2. Slide-by-slide (the backdrop)

Backdrops only. Rule: **one image, ≤6 words.** The speaker carries the rest. ★ = core (keep in the 3-min cut).

| # | ★ | On-screen (visual) | On-screen text | Beat |
|---|---|---|---|---|
| 1 | ★ | Black. A dark SAR sea, one bright vessel blip. Wordmark fades in over it. | **HEIMDALL.ai** · *small:* seeing what ships hide | Cold open — the crime + the promise. |
| 2 | ★ | The real submarine-cable web glowing across a black ocean. | *99% of the world's data — down here* | Stakes: the world runs on threads on the seabed. |
| 3 | ★ | Baltic map; nine incident pins ignite with dates 2022→2026; a tiny anchor icon. | *Nine cuts. Since 2022. One sea.* | Pattern + asymmetry: cheap, deniable, relentless. |
| 4 | ★ | Ocean swarming with thousands of vessel dots; one lonely satellite. | *We don't lack alerts. We lack prioritization.* | The real problem: where to point the next pass. |
| 5 | ★ | One ship, two faces: a tidy AIS label vs a radar ghost behind it. | *AIS = what a ship **says*** | Ships lie; the cheap signal is the one they control. |
| 6 | ★ | Triptych of three glyphs lighting up in colour — memory · eye · map. Heimdall mark. | *Three senses. One watchman.* | Meet Heimdall; introduce the three. |
| 7 | ★ | A vessel trailing a dossier/track; a risk dial. | *Knows every ship's story* · *small:* …but only what AIS tells it | Sense 1 — scoring. Strength + blind spot. |
| 8 | ★ | A **real SAR tile** with yellow detection boxes on hulls. | *Ground truth. Can't be spoofed.* · *small:* …but a blob has no name | Sense 2 — SAR vision. Strength + blind spot. |
| 9 | ★ | The criticality heatmap; cables glowing through it. | *Knows what's worth protecting* · *small:* …but everything near a cable looks busy | Sense 3 — geography. Strength + blind spot. |
| 10 | ★ | The **same three glyphs**, now dimmed, each stamped red: ✗ LIED TO · ✗ ANONYMOUS · ✗ NOISE. | *Alone, each one is blind.* | The turn. (Visual callback to slide 6.) |
| 11 | ★ | Money slide. AIS layer + SAR layer; the **gap between them** lit red. | *SAR = what a ship **is.** The gap is the threat.* | The fusion / core insight. Make this hero-quality. |
| 12 | ★ | **LIVE APP** (or backup video). C-Lion1 replay. | — (full-bleed app) | Hero demo. Run-sheet in §4. |
| 13 | ★ | Freeze: the #1 cue box, its score + "why", suspect named — the cockpit UI itself. | *Scored blind. Ranked #1.* · *small:* point-in-time · no look-ahead | Verdict + product surface in one frame. |
| 14 | ★ | Three marks: NATO CUI Cell · FR seabed doctrine · EU cable mandate. | *Doctrine exists. The cueing layer doesn't.* | Why now + the wedge + team. |
| 15 | ★ | Back to black. Wordmark. Team line + the ask. | **HEIMDALL.ai** · *the watch for the seabed front* | Close (vision folded into the last line). |

**3-min cut = all ★ rows, drop nothing major;** instead compress the talk per §7.

---

## 3. The talk (speaker script)

> Core read ≈ **5:00–5:30**; drop the «cut» lines for a clean **5:00**. ~150 wpm, calm. **[brackets]** = stage direction / slide cue. Short sentences. Let visuals breathe. *Italic* numbers = lock before stage (§5).

**[Slide 1 — black, the blip]**
November 2024. Two undersea cables — Finland to Germany, then Lithuania to Sweden — cut on consecutive days. The same bulk carrier had crossed both, on a track no normal cargo ship would fly. The investigations went nowhere. No charges. "An accident." That deniability *is* the weapon. And nobody was watching the one signal that would have caught it.

**[Slide 2 — cable web]**
Ninety-nine percent of the world's data — your bank, your messages, military command — doesn't travel by satellite. It runs through a few hundred cables on the ocean floor. Unguarded. Unwatched.

**[Slide 3 — incidents igniting + anchor]**
And someone is hitting them. *Nine* cuts in the Baltic since 2022 — roughly one every few months. The method is brutally cheap: a rusty hull, a dragged anchor — a few thousand euros to sever an artery worth billions. «It's the same asymmetry cheap drones brought to the land war — now underwater.»

**[Slide 4 — swarm + one satellite]**
So — watch the ocean, right? Here's the thing: defenders aren't blind. They're drowning. Thousands of ships, broadcasting every second. The ocean is too big, and the sensors that actually *see* — satellites — are too few and too expensive to point everywhere. The real question isn't *what happened.* It's *where do I point my next satellite, in the next hour?* **We don't have an alert problem. We have a prioritization problem.**

**[Slide 5 — AIS label vs radar ghost]**
And it gets worse — because ships lie. The one cheap, constant signal we have is AIS: every ship announcing who it is. But AIS is self-reported. You can fake it. Spoof your identity. Or just switch it off. The cheapest signal we have is the one the adversary controls completely. A ship that wants to cut a cable simply goes dark.

**[Slide 6 — triptych]**
So we built Heimdall — named for the watchman of myth who could see in the dark and hear the faintest sound. Heimdall has three senses.

**[Slide 7 — scoring]**
First, **memory**. Our scoring engine knows every vessel's class, its history, whether it's flagged on a sanctions or shadow-fleet list — and scores how *out of character* it's behaving right now. Powerful, and every score is explainable. But it reasons on AIS. Lie to it, and it believes the lie.

**[Slide 8 — SAR tile with boxes]**
Second, **eyes**. We fine-tuned a vision model on satellite radar to pick out the ships on the water — through cloud, through dark, no matter what they're broadcasting. Radar is ground truth; you can't spoof it. But a radar blob has no name, no history — and passes are scarce, so you have to know where to look.

**[Slide 9 — criticality heatmap]**
Third, **the map of what matters** — every cable, pipeline, naval base. It turns "a ship slowed down" into "a ship slowed down *right over the C-Lion1 crossing.*" «But alone, it's just a map — everything near a cable looks busy.»

**[Slide 10 — three ✗]**
Here's the key. Each of these, alone, is blind. History gets lied to. Radar is anonymous. The map is noise.

**[Slide 11 — the gap, lit red]**
But fuse them, and the trick turns against the adversary. **AIS is what a ship says. SAR is what a ship is. And the gap between them is the threat.** A hull on radar with no AIS — that's a ship running silent. A signal that appears from nowhere, no history, right at the scene, right on time — that's a *dark approach.* Lay the map over both, and Heimdall ranks the one box that deserves your next satellite pass — and tells you why. Let me show you.

**[Slide 12 — LIVE DEMO. Run §4. ~70s.]**

**[Slide 13 — verdict freeze]**
Look at what just happened. On its history alone, an ordinary bulk carrier — nothing fired. On radar alone, one anonymous blob. But *together* — a dark approach, confirmed on radar, loitering over a live cable — Heimdall pulled that one ship out of a thousand and ranked it number one. And here's the part that matters: the engine is blind to the future. The score is point-in-time — only the data available that minute, no look-ahead. We didn't hand it the answer. Remember the opening? The real investigation took *weeks* and ended with no charges. Heimdall put a sensor on that exact box the same morning — knowing nothing about a cut. «And it's not a firehose: it's a ranked queue, capped to your tasking budget — prioritization, by design, can't drown you.» Every cue is transparent: the operator sees exactly *why* before they act. That's the cockpit.

**[Slide 14 — doctrine marks]**
And the timing's no accident. NATO has a Critical Undersea Infrastructure Cell. France has seabed-warfare doctrine. The EU has a cable mandate. The budget exists — the cueing layer doesn't. Everyone tracks ships and IDs them; *no one tells the scarce sensor where to look next.* That tasking decision is the layer we own — we sit on *top* of the trackers, not against them. And because the data is open, we deploy on day one — no feed to license. We're three engineers, one with years inside subsea cables, and this already runs on real incident data.

**[Slide 15 — black, wordmark]**
Today it's the Baltic, with AIS and radar. Tomorrow, every contested sea — and every sense. We're looking for one design partner — a navy or a cable operator — to point Heimdall at live water. Because in the end it's simple: **AIS is what a ship says. SAR is what a ship is. And the gap between them is the threat.** Heimdall is the watch. Thank you.

---

## 4. Demo run-sheet (slide 12)

Scripted, ~**70s**, no live-data dependency. **Backup video loaded and ready** — full shot list, capture specs, and screenshot plan in **[DEMO_VIDEO.md](DEMO_VIDEO.md)** (verified against the running app). Replay: **C-Lion1 / Yi Peng 3, 17–18 Nov 2024**.

| # | Action on screen | Say |
|---|---|---|
| 1 | App on the Baltic, replay clock just before the window; tracks + cables visible. Scrub forward. | "Real AIS, south of Sweden, the night of the incident — I'm running the clock forward. Nothing here knows a cut is coming; it's the same logic that would run on live water tonight." |
| 2 | Cue reticle appears; the #1 box jumps to the top of the cue panel. | "Heimdall just raised a cue — *this* box, top of the queue." |
| 3 | Open the cue: the **why** + the term bars (SAR, vessel-risk, anomaly, infra-proximity). | "Why: a dark approach, confirmed on radar, loitering over the cable crossing. Score *0.88*." |
| 4 | Click the driver vessel → suspect named (Yi Peng 3, MMSI 414270000), top of the alert feed. | "The suspect from the opening — pulled out of a thousand ships that night, scored blind." |
| 5 | *(Optional, «cut for 5:00»)* scrub back to Sept 2022 → Nord Stream; the zone lights on dark-density. | "And when there's no ship to name — Nord Stream — *over 150* radar contacts across the scene, zero AIS. Eighty-four in the top box alone. The zone still lights up." |

**Fallback rule:** if anything stalls >3 seconds, cut to the backup video and keep talking. Never debug on stage.

---

## 5. Honesty guardrails & numbers to lock

This jury knows maritime. Keep it true.

- **No asserted intent.** Yi Peng 3 attribution is officially **disputed** (Swedish inquiry inconclusive, no charges — `incidents.csv`). Say **"suspect,"** "a track no normal cargo ship would fly," "anchor-drag *pattern*." Never "they did it on purpose." The deniability angle is *stronger* anyway — make that the point.
- **SAR model is real but offline.** Say *"we fine-tuned a vision model on satellite radar"* and *"we ran it on the actual Sentinel-1 scene."* Do **not** imply live on-stage inference. (`train_yolov8_hrsid.py`, YOLOv8n/HRSID, on `feature/computer-vision`; outputs baked into the demo — standard, but don't misstate.)
- **Don't say "every hull."** A maritime juror knows SAR misses small/low-RCS hulls and false-alarms on wind/wake. Say *"the ships on the water,"* *"the ones broadcasting nothing."*
- **No "before the cut" claim — it's not true.** The C-Lion1 cue fires **2024-11-18 08:41Z**, and Yi Peng 3 had *already* cut the first cable (BCS East-West) the day before. Don't say "before the cut" or "while still approaching." The honest, *stronger* frame: **"scored blind, the engine pulled the real culprit out of a thousand ships the same morning — while the actual investigation took weeks and ended with no charges."** The win is the operational tip in time to *task a sensor*, vs. a forensic report weeks later. (The crisp "14 minutes later" line belongs to **Eagle S**, which is **not** in the live demo — don't mix scenarios.)
- **Numbers to lock (verified against the baked cue JSON):**
  - Cue score **0.88** ✓ — `c-lion1.json` top cue = 0.8849, displayed as "0.88". Quote freely.
  - Cue "why" reads verbatim: *"Yi Peng 3: SAR dark-approach/blackout, loitering/slow now, anomalous track record"* — the talk mirrors this. Terms: infra 0.74 · risk 0.83 · live 1.0 · sar 1.0.
  - Nord Stream: the **map shows 153** dark contacts total; the **#1 cue box "why" reads "84"**. Both true. Say **"over 150 across the scene, 84 in the top box."** Don't say just "84" while gesturing at the whole map.
  - Incident count = **9** (`incidents.csv`, 2022–2026). "Nine cuts" is supported; don't inflate.
  - SAR mAP50 **~0.91** — Q&A only, don't headline.
- **"99% of data"** — standard figure, fine.
- **Public-deck footnote:** OpenSanctions + Capella Open Data are non-commercial — attribution per `data/SOURCES.md` if shared publicly. Not needed spoken.

---

## 6. Visuals to build / source

The deck lives or dies on imagery. **Real Heimdall screenshots beat stock** — they prove it's real.

| Slide | Asset | Source |
|---|---|---|
| 1, 15 | Wordmark on black + a real SAR-sea blip | Crop a Sentinel-1 tile; set the type. |
| 2 | Submarine-cable web | TeleGeography style, or render `data/geo/cables.geojson` dark. |
| 3 | Baltic incident map, nine animated pins + anchor | Render from `data/reference/incidents.csv`. |
| 4 | Vessel-swarm + lone satellite | Screenshot the app at full Baltic zoom (thousands of tracks). |
| 5 | AIS label vs radar ghost | Composite — design. |
| 6 / 10 | Three-sense glyphs (colour) / same glyphs dimmed + ✗ | Design as a matched pair — the callback is the point. |
| 7–9 | The three senses | **App screenshots:** alert feed (7), real SAR tile w/ boxes (8), criticality heatmap (9). |
| 8 | SAR detection tile | Best real asset we have — make it hero-quality. |
| 11 | AIS-vs-SAR gap | **The money slide.** Two app layers, gap in red. The line *"AIS is what a ship says / SAR is what a ship is / the gap is the threat"* should be the **largest type in the entire deck** — it's the one phrase the jury must carry into the deliberation room, and it returns verbatim on slide 15. Do not rush this composite. |
| 12 | Live app + **backup video** | Record the C-Lion1 replay this week. |
| 13 | Cue freeze (cockpit) | App screenshot. |
| 14 | NATO / FR / EU marks | Official logos (fair use, small). |

**Design language:** dark operations-console aesthetic (matches the app). One accent for "threat" (the app's red). Heavy, confident type. **No bullet lists on slides — ever.**

---

## 7. The 3-minute cut

Keep all ★ slides; tighten the talk:
- **Beats 1–3 → ~25s:** *"November 2024: two Baltic cables cut on consecutive days, same ship, no charges — 'an accident.' It's happened nine times since 2022. Cheap, deniable, and nobody's watching the signal that would catch it."*
- Keep **the three senses + the fusion verbatim** — that's the whole idea.
- Demo to **45s**: steps 1, 2, 3, 4 only.
- Fold why-now/wedge into one line of the close: *"The doctrine and budget already exist — the cueing layer didn't. Now it does. We want one navy or cable operator to point it at live water."*

---

## 8. Q&A prep (the pitch is won here)

The five questions this jury *will* ask. Answer in one breath, then stop. The talk already pre-empts #2 (no-look-ahead) and partly #3 (capped queue) — these are the back-pocket versions.

1. **"How is this not Windward / Kpler / Starboard / Spire?"**
   *"They do detection and identity — who's on the water. We do tasking — which scarce sensor to point next, and why. We sit on top of trackers like those as the cueing layer, not against them. The tasking decision is the part nobody owns."*

2. **"You're replaying a known incident — that's hindsight, not prediction."**
   *"The score is point-in-time, no look-ahead — it only ever sees the data available at that minute. We didn't tell it the answer; we replayed the night and it surfaced the ship on its own, before the second cable was cut. It's the exact logic that would run on live water tonight."* (Also stated on stage.)

3. **"What's your false-positive rate? Won't operators drown in cues?"**
   *"We don't add alerts — we rank and cap. The output is a top-N task queue sized to the operator's actual tasking budget, not a feed. Prioritization, by construction, can't drown you — that's the whole point of the product."*

4. **"Open data means no moat."**
   *"Open data is an advantage — we deploy day one with no proprietary feed to license, anywhere in the world. The defensibility isn't the pixels; it's the fusion logic, the calibrated point-in-time scoring, and being embedded in the tasking loop. Whoever owns that decision owns the workflow."*

5. **"You can't task a satellite in an hour — revisit is days."**
   *"Cueing isn't only satellites. It's the next pass of whatever's reachable — SAR tasking, maritime patrol aircraft, a drone, a patrol boat. We rank against the revisit you actually have and make the scarce pass count. The point is allocation, not a specific sensor."*

**Other likely asks (one-liners):** *Accuracy?* SAR detector ~0.91 mAP50 on HRSID; scoring validated on held-out incidents. *Data rights for production?* OpenSanctions + Capella are non-commercial — swapped for licensed/commercial SAR (ICEYE/Umbra) at deployment. *Live feed?* AISStream for live AIS; SAR on tasking. *What if they spoof a plausible identity instead of going dark?* That's exactly what the behavioral-coherence score catches — declared class vs. observed behavior.

---

## Revision log

- **V1** — initial draft from grounded product facts (3 real senses + fusion; Heimdall framing; C-Lion1 hero).
- **V2** — specialist review #1 applied: cold open rewritten into the dated (honest, no-intent) crime; cut ~250 words toward 5:00 with «cut» markers; added wedge/moat + team beat (slide 14); fixed believability ("every hull" → "the ships on the water"; locked incident count to 9; Nord Stream "over 80"); sharpened verdict to "while still approaching"; merged cockpit + vision into verdict/close; differentiated slides 6↔10; flagged slide 11 as the hero composite.
- **V3** — specialist review #2 applied (scored 8/10, "wins" gated on the hindsight defense): added the **no-look-ahead / point-in-time** line to the verdict + demo step 1 (defuses the "hindsight not prediction" kill-shot — and it's true to the engine); pre-empted **false-positive / cue-overload** in the talk (capped ranked queue); rebuilt slide 14's punchline around *owning the tasking decision*, added incumbent differentiation ("on top of trackers, not against") and open-data-as-moat, and **killed "built it in a weekend"** (reads as toy to VCs) → "already runs on real incident data"; closed on the money line verbatim + made it the deck's largest type; added **§8 Q&A prep** with the five hardest jury questions and crisp answers.
