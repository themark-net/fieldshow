FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY docs ./docs
RUN pip install --no-cache-dir .

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        musescore3 \
        lilypond \
        poppler-utils \
        fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen
ENV XDG_RUNTIME_DIR=/tmp/runtime
RUN mkdir -p /tmp/runtime && chmod 1777 /tmp/runtime
