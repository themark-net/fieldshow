# Fieldshow

A public marching-band workbench. An agent writes the musical idea and the pictures on the field. Existing open-source tools engrave the music and carry the drill. One page shows the score, the dots, and the optional uniform and flag notes together.

## Goals

- Fast iteration: text, MusicXML, and a field image go in. Parts, a `.om` drill file, MIDI, and a scrubbable field come out.
- No model inside the server. Grok Build, or any other agent, is the glue. `fieldshow prompt-card` is the contract it fills.
- Deploy the first copy on the LAN host `maximum`.

## Non-goals

- Replacing OpenMarch's editor.
- Selling charts or hosting copyrighted scores.
- Tracing marchers out of a photograph in this version.
