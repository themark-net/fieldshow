# ADR 0002: Open-source tools with agent glue

- Status: Accepted
- Date: 2026-10-07

## Context

The show has three products that already have mature tools: notation, drill files, and a picture of the field. The new work is making an agent able to drive them in one pass, then see music, drill, and design together.

## Decision

- This repository is MIT.
- Arrangement and MusicXML/MIDI go through music21 (BSD-3).
- Drill export is the OpenMarch public JSON schema (Apache-2.0), vendored as `src/fieldshow/data/openmarch-schema.json`. Files use `.om`.
- The integrated view is a small FastAPI page in this repo. It reads the same show document.
- The language model stays outside the process. It writes the intent JSON described in `docs/PROMPT-CARD.md`.

## Rejected alternatives

- Fork OpenMarch (AGPL-3.0 Electron app). Deploying and modifying it is a different project, and linking it would force this repo onto AGPL. Writing their documented schema gets the file into their editor without that.
- CalChart (GPL, C++/wx, Cal Band continuity language). Harder to script, and the continuity model is specific to one band.
- Call a hosted model from the server. The operator is already an agent. A second model inside the request path adds a key, a failure mode, and a wait. Local weights can be a later option. They are not required to run a show.
- Put LilyPond or MuseScore in the first container. MusicXML is enough for engraving elsewhere. A PDF image can be added when a show needs paper parts.

## Consequences

`.om` opens in OpenMarch. MusicXML opens in MuseScore or LilyPond's importers. This app does not edit drill with a mouse beyond what the page needs to scrub and inspect. Design notes are text and colors, not a uniform CAD model.
