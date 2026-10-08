FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY docs ./docs
RUN pip install --no-cache-dir .

ENV FIELDSHOW_SHOW=/app/examples/fanfare.json
EXPOSE 8876
CMD ["sh", "-c", "fieldshow serve --show ${FIELDSHOW_SHOW} --host 0.0.0.0 --port 8876"]
