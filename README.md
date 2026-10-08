# Fieldshow

Marching-band music, drill, and show design in one show file.

An agent writes a short JSON intent: a melody, chords, and shapes on the field. Fieldshow arranges a high-school wind and battery score with [music21](https://github.com/cuthbertLab/music21), writes [OpenMarch](https://openmarch.com/) `.om` drill, and serves one page that scrubs the dots against the parts. Uniform and flag notes ride along on that same page.

The model stays outside this program. `fieldshow prompt-card` is the contract a session fills. That is the whole integration: text, a MusicXML import, or a field image in, then the CLI.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
fieldshow prompt-card
fieldshow build examples/fanfare.json -o /tmp/gate.json
fieldshow export-om /tmp/gate.json -o /tmp/gate.om
fieldshow export-musicxml /tmp/gate.json -o /tmp/gate.musicxml
fieldshow serve --show /tmp/gate.json --port 8876
```

The sample tune, Gate Fanfare, is original.

OpenMarch's desktop app is separate and AGPL. This repo is MIT and only vendors their Apache-2.0 show schema. See `docs/adr/0002-oss-glue.md`.

The lab copy runs on `maximum` at `http://10.42.0.238:8876/`. Deploy notes: `docs/ops/deploy-maximum.md`.
