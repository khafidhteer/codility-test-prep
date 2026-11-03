# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Stage 1 builds the app: database, content checks, single-file HTML.
# Stage 2 is the runtime: python slim plus two files. No pip installs at all.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /src
COPY content ./content
COPY build ./build

# Fails the build if any reference solution stops returning rows, if the bank
# drops below 5x the exam draw, or if content contains placeholders.
RUN python build/gen_db.py \
 && python build/verify.py \
 && python build/build_app.py


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    BIND=0.0.0.0 \
    SECURE_COOKIE=1

WORKDIR /app
COPY app/server.py ./app/server.py
COPY --from=build /src/app ./app

# Run as a non-root user with no shell home.
RUN useradd --system --uid 10001 --no-create-home lab \
 && chown -R lab:lab /app
USER lab

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

CMD ["python", "app/server.py"]
