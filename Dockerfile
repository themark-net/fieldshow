FROM python:3.12-slim

# LilyPond engraves part PDFs during `fieldshow build` (ADR 0004).
# musicxml2ly ships in the lilypond package. The server only serves the files.
# Installed before the sources so a code change does not reinstall it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends lilypond \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY docs ./docs
RUN pip install --no-cache-dir .

ENV FIELDSHOW_SHOW=/app/examples/fanfare.json
EXPOSE 8876
CMD ["sh", "-c", "fieldshow serve --show ${FIELDSHOW_SHOW} --host 0.0.0.0 --port 8876"]
