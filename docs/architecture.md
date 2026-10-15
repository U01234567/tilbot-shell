# Architecture

How the parts fit together, where everything lives, and the contract between the shell and Tilbot.

## The parts

```
                          participant's browser
               https://SHELL_HOST │      │ https://BOT_HOST (inside the shell's iframe)
                                  ▼      ▼
                          ┌────────────────────┐
                          │       Caddy        │  HTTPS, security headers, blocked routes
                          └────────────────────┘
                              │             │
                              ▼             ▼
   Postgres ◀── shell (Django)          Tilbot frontend ──ws──▶ Tilbot backend ──▶ Mongo
  (encrypted)        ▲                                        (+ our patches)
                     │                                                │
                     └──────── /bridge/save, /bridge/log ─────────────┘
                                   (inside the Docker network)

   vector-similarity-intent service: phase 3, called only by the shell (not running yet)
```

- **The shell is the hub.** Tilbot only calls the shell, and only the shell will call the vector-similarity-intent service.
- **Participants see two sites.** The shell at `SHELL_HOST` handles sign-up, sign-in and the chat page. Tilbot at `BOT_HOST` is only ever shown inside the shell's chat page, in an iframe.
- **Tilbot's researcher dashboard is not public.** It sits on port 8081, which only `compose.dev.yaml` publishes, and only to `127.0.0.1`.

## Where everything goes

| Path | What it holds | Change it when… |
|---|---|---|
| `components.toml` | Tilbot and vector-similarity-intent service: repo, pinned commit, notes | moving to a newer upstream commit |
| `compose.yaml` | every service as it runs for real | adding a service or a volume |
| `compose.dev.yaml` | only what differs in development | changing how development runs |
| `start_shell.py` | `up` (with `.env`, secrets and checks), `trust`, `updates`, `lock`, or any `docker compose` command | adding a routine task |
| `proxy/Caddyfile` | HTTPS, security headers, which routes are public | adding a public page or a host |
| `tilbot/Dockerfile` | builds Tilbot at the pinned commit with our patches | Tilbot changes how it builds |
| `tilbot/patches/` | our changes to Tilbot, one concern per patch | Tilbot lacks something we need |
| `vector-similarity-intent/Dockerfile` | builds the intent service at the pinned commit | it changes how it builds |
| `vector-similarity-intent/patches/` | our changes to it, same rules; empty for now | it lacks something we need |
| `shell/config/` | Django settings, URLs, the study loader (`project.py`) | adding a setting or an app |
| `shell/templates/`, `shell/static/` | shared page layout and the shell's CSS | changing the look of every page |
| `shell/accounts/` | participant codes, sign-up, sign-in, lockout | changing how participants get in |
| `shell/records/` | answers and transcripts, encrypted | storing a new kind of participant data |
| `shell/bridge/` | the chat page and the endpoints Tilbot calls | changing the contract with Tilbot |
| `shell/phase1_collect/` | rules after each answer: valid? follow-ups? | changing how answers are judged |
| `shell/phase2_feedback/` | feedback (placeholder) | building phase 2 |
| `shell/phase3_questions/` | questions answered from the knowledge base (placeholder) | building phase 3 |
| `shell/monitor/` | staff dashboard (placeholder) | building the overview |
| `project-example/` | the shape of `/project/`, with dummy content | the project format changes |
| `/project/` | the real study, not committed | the research team changes a setting |
| `docs/` | this file, `decisions.md`, `operations.md` | something here is no longer true |

Every fixed component has its own root folder: `shell/` is ours, `tilbot/` and `vector-similarity-intent/` each hold a build file and a `patches/` folder. The build applies whatever patches exist, so a folder stays in use when upstream merges our patches and the patch files are deleted.

A folder becomes a Django app (listed in `INSTALLED_APPS`) only when it has models, pages or URLs. `phase1_collect` holds plain Python rules, so it isn't one.

## The bridge contract

Tilbot calls the shell from its server, inside the Docker network (`http://shell:8000/...`). Every call is a form POST and carries:

| Field | Set by | Meaning |
|---|---|---|
| `participant_id` | patch 0001 / 0002 | the signed token from the chat URL (`bridge/tokens.py`), never the participant's code |
| `bridge_secret` | patch 0001 / 0002, from `BRIDGE_SECRET` | must equal `BRIDGE_SECRET` in `.env`; nobody types it |

**`POST /bridge/save`**: one phase-1 answer.

| Field | From | Example |
|---|---|---|
| `item` | Processing-block parameter | `Q01` |
| `user_input` | the participant's answer, sent by Tilbot | `7` |

The shell replies with `{"intent": "saved"}` or `{"intent": "high"}`, but only after the answer is committed. Any problem (wrong secret, bad token, unknown item, an answer off the scale) gets a 4xx reply.

**`POST /bridge/log`**: one conversation event, sent by Tilbot's `ShellLogger` (patch 0002).

| Field | Meaning |
|---|---|
| `conversation` | one random id per Tilbot conversation |
| `seq` | order within that conversation |
| `event` | `message_bot`, `message_user`, `session_end`, … |
| `detail` | the message text, stored encrypted |

## Phase 1 in Tilbot's editor

Open the editor from Tilbot's dashboard, with the pencil icon next to the project.

**Once per project:** under Settings, open External processing and add a link:

- **Name:** `shell-save`
- **Address:** `http://shell:8000/bridge/save`. Tilbot adds the participant and the secret only to addresses that start with `SHELL_URL` (`http://shell:8000/bridge/`, set in `compose.yaml`).
- **Send the user's input:** on
- **Send the connectors:** off

**Per question:**

1. **An MC block with the question.** Give it one connector per answer option on the item's scale (for a 0–10 item: `0` to `10`), all pointing to step 2.
2. **A Processing block "save Q01".** It uses the external link `shell-save`, with one parameter: `item` = `Q01`. Its connectors:
   - `saved` → the next question
   - `high` → this item's follow-up blocks, which end at the next question
   - *else* → a block "Something went wrong, let's try that again", which leads back to the question

Tilbot follows *else* when a call fails, so a failed save can never move on silently.

Labels match on "contains", so `saved` and `high` must never be part of another label on the same block.

The save calls only work in a chat opened from the shell's chat page, because only that page gives Tilbot a participant token. In the editor's simulator every save goes to *else*. For the same reason the dot on Settings turns red: the editor can't reach the shell, which is expected.

## The Caddyfile, line by line

- **`{$SHELL_HOST} { … }`** is the shell. `encode gzip` compresses responses.
- **The `header` block** sets the security headers:
  - `Content-Security-Policy` allows only the shell's own scripts and styles, and frames only from `BOT_HOST`. Inline styles are allowed for Django's own pages. `frame-ancestors 'none'` stops other sites from framing the shell.
  - `Strict-Transport-Security` tells browsers to use HTTPS only.
  - `X-Content-Type-Options` and `Referrer-Policy` are standard hardening.
- **`handle /bridge/*`** answers 404 from outside, because Tilbot reaches the bridge inside Docker.
- **`handle /static/*`** serves CSS and images from the shared `static` volume, filled by `collectstatic`.
- **The last `handle`** passes everything else to Django.
- **`{$BOT_HOST} { … }`** is Tilbot's chat:
  - `frame-ancestors` lets only the shell show it.
  - `@public` lists the only paths participants need; everything else answers 404.
  - Inside `route`, the API, websocket and project files go to the backend, and pages go to the frontend.
- **`:8081 { … }`** is Tilbot complete with its dashboard, on plain HTTP. It is reachable only where a compose file publishes port 8081, which is `127.0.0.1` in development.
