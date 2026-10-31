# plan: stall and spin comparison

status: phase 1 done 2026-10-31 (first session, all three aircraft; see WORKLOG). next: phase 3 analysis; phase 2 sources still open.

## question

How do stalls and spins behave in three MSFS 2024 aircraft, and how does that compare with each aircraft's POH and with real-world behaviour?

- Asobo C172SP Classic
- WBSim C152
- A2A Comanche 250 (PA-24)

Same method as the glider project: record with SimConnect, compare with published data, report the gaps rather than guessing causes.

## what we compare

- **Stall speeds**: power off flaps up / full flaps, power on, against the POH stall speed tables.
- **Stall warning margin**: kt and AoA between the warning and the break. POHs typically give 5–10 kt for the horn.
- **Stall character**: pitch break, wing drop, how much each aircraft resists or invites a spin.
- **Spins**: entry, rate (s per turn), attitude, height per turn, and recovery (turns and height to recover with standard PARE inputs).
- **Repeatability**: left vs right, run to run.

Real-world references for spin rate and height per turn are scarce. POHs give the procedure but rarely numbers. Flight-test reports, NASA spin studies and instructor references may help; collect them in `data/sources/` with citations, as with the glider manuals.

## phases

1. **profile and telemetry** (this phase)
   - the high-rate recorder (`msfsdiag.telemetry.recorder`, ~60 Hz, every sim frame, one data definition)
   - the test card [doc/TESTCARD-stall-spin.md](../../doc/TESTCARD-stall-spin.md)
   - a first session in the C172 to shake out the profile and markers
2. **sources**: POH stall speed tables, spin limits and procedures for the three aircraft, plus any real-world spin data. Catalog in `data/sources/sources.json`; stall speeds into `data/aircraft/*.json` (stall table, Vne, g limits, spin approval).
3. **test-point detection**: split a session into points (pause markers, landing-light markers), detect warning, break, spin entry, recovery start and end, and compute the measures on the test card.
4. **reports**: per session, a timeline of AoA, IAS, pitch, bank, yaw rate, g and altitude with the detected events. Across aircraft, a comparison page: stall speeds vs POH, spin rate, height per turn, turns to recover.
5. **findings and examples**.

## risks and open questions

- **Third-party flight models** (A2A Accu-Sim, WBSim) may compute some values themselves. The recorder reads standard simvars; check they respond (AoA, stall warning, rates) in each aircraft.
- **IAS near the stall**: real pitot-static systems read wrong at high AoA; the sim may or may not model it. Record IAS, TAS and AoA.
- **Pilot technique** dominates spin entry. The test card fixes the inputs; the control positions are recorded so entries can be compared.
- **Weight and CG** change spin behaviour. Record them; keep loading consistent (pilot, half fuel).
