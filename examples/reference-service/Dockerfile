# Container runtime for the reference upload service. Honors $PORT.
#
# Unsupported reference example: one illustrative way to wrap the
# Context Architecture Blueprint library behind an upload surface. Build from the
# REPOSITORY ROOT so the engine package, sample corpus, and config come along:
#   docker build -f examples/reference-service/Dockerfile -t cab-reference-service .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY examples/reference-service/requirements.txt ./examples/reference-service/requirements.txt
RUN pip install --no-cache-dir -r examples/reference-service/requirements.txt

# The supported engine (library + CLI), its bundled sample corpus, and config.
COPY src ./src
COPY corpora ./corpora
COPY config ./config
# The reference service module itself.
COPY examples/reference-service/app.py ./app.py

# Non-root for least privilege.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
