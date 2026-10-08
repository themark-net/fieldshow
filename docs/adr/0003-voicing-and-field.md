# ADR 0003: Fixed voicing and step coordinates

- Status: Accepted
- Date: 2026-10-07

## Context

An agent needs an arranger it can re-run and a field grid a drill file can store. Both have to be deterministic so a test can fail when the voicing or the geometry changes.

## Decision

- Block voicing: melody on the high voices, thirds and fifths in octave 3, roots in octave 2, then the usual transpositions. Battery is a fixed accent pattern.
- Football field, 8-to-5 (22.5 inch steps). x from the 50, audience left negative. y from the front sideline. Front hash at 32 steps. Straight-line moves between sets.
- Shapes are line, block, and arc only.

## Rejected alternatives

- Close-position voicing under the melody. More musical on some chords, and harder to assert. A later arranger can add a `voicing` field without breaking the file version if the default stays this one.
- College-only or high-school-only hash marks as the only legal y. The hash is a checkpoint in the export. Shapes may stand anywhere on the grid.
- Freehand per-marcher paths as the only input. The agent can still express them as one-person lines. Named shapes keep the common pictures short.

## Consequences

The demo fanfare is blocky on purpose. It is a contract test, not a competitive chart. Richer voicing and step-size warnings are open questions, not silent behavior.
