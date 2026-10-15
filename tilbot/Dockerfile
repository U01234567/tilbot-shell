# Tilbot at the commit pinned in components.toml, with our patches applied.
# Built by compose.yaml; start_shell.py passes TILBOT_REPO and TILBOT_COMMIT.
# One image serves both the chat frontend and the backend.

# The Node version from Tilbot's own Dockerfile.
FROM node:26.7.0-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node 25 and newer no longer ship Corepack. Corepack installs the Yarn version that
# Tilbot's package.json names ("packageManager"), so we never pin Yarn twice.
RUN npm install --global corepack && corepack enable
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

# Server only: skip the desktop editor's Electron download.
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1

ARG TILBOT_REPO
ARG TILBOT_COMMIT
WORKDIR /tilbot
RUN git init --quiet \
    && git fetch --quiet --depth 1 "$TILBOT_REPO" "$TILBOT_COMMIT" \
    && git checkout --quiet FETCH_HEAD

# Applies every patch in patches/, and nothing when there is none. A patch that no longer
# applies stops the build here: regenerate it against the new commit.
COPY patches/ /patches/
RUN for patch in /patches/*.patch; do [ -e "$patch" ] || continue; git apply "$patch"; done


# The install command from Tilbot's own compose file, then the production build of the chat.
RUN yarn install --immutable \
    && yarn workspace frontend build
