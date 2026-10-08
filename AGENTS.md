# Agents

Fieldshow is glue. You write JSON and run the CLI. You do not add a model client inside the server.

Read `docs/PROMPT-CARD.md` and `docs/ARCHITECTURE.md` before editing. Tests in `tests/` are the behavior spec. A change that breaks them is a bug, not a new style.

## Commands

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
fieldshow prompt-card
fieldshow demo -o examples/fanfare.json
fieldshow build examples/fanfare.json -o /tmp/show.json
fieldshow serve --show /tmp/show.json --port 8876
```

## Ownership

- `src/fieldshow/model.py`, `design.py`, `cli.py`, `drill/image.py`: stable. Extend them only when a test needs a new field.
- `src/fieldshow/music/`: arranger and MusicXML.
- `src/fieldshow/drill/chart.py` and `openmarch.py`: geometry and `.om`.
- `src/fieldshow/web/`: the integrated page.

## Deploy

`maximum` (10.42.0.238), user `mark`, Docker Compose, port 8876. See `docs/ops/deploy-maximum.md`.
