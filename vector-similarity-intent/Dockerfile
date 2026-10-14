# vector-similarity-intent at the commit pinned in components.toml, with our patches applied.
# Built by compose.yaml; start_shell.py passes the REPO and COMMIT build arguments.
# The steps mirror the upstream Dockerfile: CPU-only torch first, then the app.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG REPO
ARG COMMIT
WORKDIR /app
RUN git init --quiet \
    && git fetch --quiet --depth 1 "$REPO" "$COMMIT" \
    && git checkout --quiet FETCH_HEAD

# Applies every patch in patches/, and nothing when there is none. A patch that no longer
# applies stops the build here: regenerate it against the new commit.
COPY patches/ /patches/
RUN for patch in /patches/*.patch; do [ -e "$patch" ] || continue; git apply "$patch"; done

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-torch-cpu.txt \
    && pip install --no-cache-dir -r requirements.txt

ARG PORT=8081
ENV PORT=$PORT
CMD fastapi run --port $PORT
