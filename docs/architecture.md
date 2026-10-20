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
                     └───── /bridge/save, /bridge/log, /bridge/ask ───┘
                     │             (inside the Docker network)
                     ▼
   vector-similarity-intent: phase 3, called only by the shell, only when project/knowledge.xlsx exists

   docker-proxy: lets the shell's system page read Docker (containers, resource use, logs), nothing else
```

- **The shell is the hub.** Tilbot only calls the shell, and only the shell calls the vector-similarity-intent service.
- **Participants see two sites.** The shell at `SHELL_HOST` handles sign-up, sign-in and the chat page. Tilbot at `BOT_HOST` is only ever shown inside the shell's chat page, in an iframe.
- **The system page shows all of this live.** `/researcher/system` draws these parts and who calls whom, each green, orange or red by its health check, with its CPU, memory and latest log lines (`shell/monitor/system.py`). The shell reads Docker only through `docker-proxy`, which passes on just those three readings (ETHICS.md, "The system page").
- **Tilbot's researcher dashboard is not public.** It sits on port 8081, which only `compose.dev.yaml` publishes, and only to `127.0.0.1`.
- **The shell's pages look like Tilbot, on a light purple background.** That background and the white cards (`shell/static/css/shell.css`) mark every page the shell serves, and so controls and secures; what shows without it is Tilbot's (its dashboard, and the chat inside the iframe). The researcher pages always carry the mark `tilbot-shell <version> · researcher` and never take the study's colours. The participant pages take the study's colours from `project/theme/tokens.css`, and carry the mark `· development` only while `SHELL_ENV=development`: participants of a real study never see the software's name. The chat inside the iframe can take the study's look too, from `project/theme/tilbot.css` (patch 0009).

## Where everything goes

| Path | What it holds | Change it when… |
|---|---|---|
| `components.toml` | Tilbot and vector-similarity-intent service: repo, pinned commit, notes | moving to a newer upstream commit |
| `compose.yaml` | every service as it runs for real | adding a service or a volume |
| `compose.dev.yaml` | only what differs in development | changing how development runs |
| `start_shell.py` | `up` (with `.env`, secrets and checks), `trust`, `researcher`, `backup`, `restore`, `updates`, `update`, `erase`, `lock`, or any `docker compose` command | adding a routine task |
| `proxy/Caddyfile` | HTTPS, security headers, which routes are public | adding a public page or a host |
| `tilbot/Dockerfile` | builds Tilbot at the pinned commit with our patches | Tilbot changes how it builds |
| `tilbot/patches/` | our changes to Tilbot, one concern per patch | Tilbot lacks something we need |
| `vector-similarity-intent/Dockerfile` | builds the intent service at the pinned commit | it changes how it builds |
| `vector-similarity-intent/patches/` | our changes to it, same rules; empty for now | it lacks something we need |
| `shell/config/` | Django settings, URLs, the study loader (`project.py`) | adding a setting or an app |
| `shell/templates/`, `shell/static/` | shared page layout, the shell's CSS, and `js/chat.js` (opens the results) | changing the look of every page |
| `shell/accounts/` | participant codes, sign-up, sign-in, lockout | changing how participants get in |
| `shell/records/` | answers, questions asked and transcripts, encrypted; `backup_cipher`, which encrypts backups with the same key | storing a new kind of participant data |
| `shell/bridge/` | the chat page and the endpoints Tilbot calls | changing the contract with Tilbot |
| `shell/phase1_collect/` | rules after each answer: valid? follow-ups? | changing how answers are judged |
| `shell/phase2_feedback/` | the results: scale scores (`scoring.py`, pure functions) and the panel beside the chat | changing how results are scored or shown |
| `shell/phase3_questions/` | matching a question to the knowledge base, through vector-similarity-intent (`matching.py`) | changing how questions are matched or answered |
| `shell/monitor/` | the researcher dashboard: counts, the data export (`export.py`), removing data (`removal.py`, also used by `erase`), and the system page (`system.py`) | adding a researcher page |
| `project-example/` | the shape of `project/`, with dummy content | the project format changes |
| `project/` | the real study, not committed | the research team changes a setting |
| `docs/` | this file, `decisions.md`, `operations.md` | something here is no longer true |

Every fixed component has its own root folder: `shell/` is ours, `tilbot/` and `vector-similarity-intent/` each hold a build file and a `patches/` folder. The build applies whatever patches exist, so a folder stays in use when upstream merges our patches and the patch files are deleted.

A folder becomes a Django app (listed in `INSTALLED_APPS`) only when it has models, pages or URLs. `phase1_collect` and `phase3_questions` hold plain Python, so they aren't.

## Our patches to Tilbot

Each patch is one concern, applied to the pinned commit at build time (`tilbot/patches/`), and offered upstream.

| Patch | Changes | Why it matters for a review |
|---|---|---|
| `0001-forward-participant` | Tilbot adds the participant token and the bridge secret to calls to the shell, and only to those | the shell knows who answered; the secret is never typed into a flowchart |
| `0002-shell-logger` | conversation events go to the shell instead of MongoDB; the dashboard's logging switch is hidden | no transcript is ever stored in plain text |
| `0003-embed-cross-origin` | the chat works when embedded by another site | a bug fix; nothing about data |
| `0004-safe-variable-sql` | Tilbot's data tables are read with parameters instead of pasted text | closes an SQL injection a participant could use through the chat |
| `0005-browser-editor` | the flowchart editor works in the browser, against the server, for your own projects only | researchers need no desktop app; every editor route checks the login |
| `0006-admin-password` | the first admin password comes from `.env`; Tilbot refuses to create the account without one | no `admin`/`admin` default |
| `0007-clickable-links` | web addresses (`https://…`) in chat messages become links that open in a new tab | the message is split into text and addresses and shown as text: no HTML is built from it |
| `0008-dashboard-icons` | the dashboard's Delete and Import icons find their project also when the click lands on a line of the icon | a bug fix: before, deleting a project often did nothing |
| `0009-study-theme` | Tilbot's pages load `/study-theme/tilbot.css` after their own styles: the study's `project/theme/tilbot.css`, served by Caddy on `BOT_HOST` | the chat can take the study's colours and font without changing Tilbot's code; a study without the file keeps Tilbot's look |
| `0010-quiet-console` | Tilbot's log no longer prints what a participant typed (its input, the matched text, and its own logger's details) | participants' messages stayed in the container logs, readable by anyone with Docker on the machine and on the system page |
| `0011-chat-chart` | a text line `[[line …]]` in a bot message is drawn as a small line with a dot, the chart of the results in the chat; as text, no HTML | how the results look in the chat; the line stays readable as text in a transcript |

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

The shell stores these lines only when `project.toml` has `transcripts.enabled = true`; otherwise it answers 204 and keeps nothing.

**`POST /bridge/feedback`**: the results at the end of the questionnaire (phase 2), as `feedback.toml`'s `show` says.

| Field | From | Example |
|---|---|---|
| `part` | Processing-block parameter | `story`, then `chart` |

With `part=story` the shell notes that the results were shown, and how, and replies `{"intent": "panel"}`, or `{"intent": "chat", "connector_label": "<the story>"}`. With `part=chart` it replies `{"intent": "chat"}` or `{"intent": "both"}`, with the chart as the label. A participant who hasn't answered every item yet gets a 4xx reply.

## Phase 1 in Tilbot's editor

Open the editor from Tilbot's dashboard, with the pencil icon next to the project.

**Once per project:** under Settings, open External processing and add two links. Tilbot adds the participant and the secret only to addresses that start with `SHELL_URL` (`http://shell:8000/bridge/`, set in `compose.yaml`). "Send the connectors" stays off for both.

| Name | Address | Send the user's input |
|---|---|---|
| `shell-status` | `http://shell:8000/bridge/status` | off |
| `shell-save` | `http://shell:8000/bridge/save` | on |
| `shell-feedback` | `http://shell:8000/bridge/feedback` | off |

The bot's name and avatar, shown in the header above the chat, are under Settings too ("Name").

**The first block: has this participant answered everything already?** Make a Processing block "status" the starting block. It uses `shell-status`, without parameters, and has three connectors:
- `returning` → a block like "Welcome back! You answered all the questions already", then on to the questions of phase 3 (or the end). A returning participant doesn't see the results again.
- `new` → the welcome and the first question
- *else* → also the welcome: in the editor's simulator, which can't reach the shell, the questionnaire simply starts

**Per question:**

1. **An MC block with the question.** Give it one connector per answer option on the item's scale, all pointing to step 2. The connector labels are the numbers (for a 0–10 item: `0` to `10`), or exactly the words in the item's `labels` in `questionnaire.toml` (for example `Not at all` to `Very much`); the shell turns the words into numbers.
2. **A Processing block "save Q01".** It uses the external link `shell-save`, with one parameter: `item` = `Q01`. Its connectors:
   - `saved` → the next question
   - `high` → this item's follow-up blocks, which end at the next question
   - *else* → a block "Something went wrong, let's try that again", which leads back to the question

Tilbot follows *else* when a call fails, so a failed save can never move on silently.

Labels match on "contains", so `saved` and `high` must never be part of another label on the same block.

The save calls only work in a chat opened from the shell's chat page, because only that page gives Tilbot a participant token. In the editor's simulator every save goes to *else*. For the same reason the dot on Settings turns red: the editor can't reach the shell, which is expected.

`project-example/tilbot/example.tilbot` is all of the above, ready to import, ending with the results below. A participant has finished the questionnaire once every item of `questionnaire.toml` has an answer, so the flowchart must ask every item there.

## Phase 2: the results

A study with `project/feedback.toml` shows the participant's results once, at the end of the questionnaire, when every item is answered. The file lists the scales (which items, which direction, the threshold) and the texts; `project-example/feedback.toml` explains each line. The shell scores each scale from the latest answers: the mean of the answers' places on their scales, times 100, turned around for a `reverse` scale, once at least half of its items are answered. That is the EORTC QLQ-C30 method. No score is shown; the export has them, in their official direction.

`show` in the file chooses how, and one flowchart serves all three, because it asks the shell:

- **`panel`**: a panel beside the chat (over it on a phone). A title, one sentence, and per scale a card with its name, a word for how it went (`worth_discussing` or `fine`), one line and the answers behind it. Every line runs from worse (left) to better (right), whatever the scale's own direction, with the words of its `ends` underneath and a dot where the participant is; it is light orange up to the threshold and light green after it, with a thin mark at the threshold. A card worth discussing gets an orange edge; a scale without a threshold gets a neutral dot and no word. Under the line, the scale's questions (their `text` in `questionnaire.toml`) with the participant's answers, in the words of the buttons. A × closes it; the button "results" below the chat opens and closes it again during that visit.
- **`chat`**: two chat messages. First a short story: the `[story]` opening, one sentence per scale (its `story.fine`, `story.worth` or, without a threshold, `story.neutral`, with the blanks `{name}`, `{answers}` and `{Q01}` filled in from the answers), and the closing. Rule-based: every sentence is the study's own (`phase2_feedback/story.py`). Then a small chart: per scale its name and word, and the same line as on the panel, drawn in the chat by patch 0011 from a text line like `[[line Much pain|No pain|66.7|75.0|worth]]`.
- **`both`**: the story and the chart in the chat, and the panel as well.

**In the flowchart,** after the last question (`project-example/tilbot/example.tilbot` has all of it):

1. A block "Thank you for your answers!", then a Processing block "feedback" with `shell-feedback` and the parameter `part` = `story`. Its connectors:
   - `panel` → on to phase 3 or the end, with the event "Message to parent window", message `show_results` and no parameters
   - `chat` → an Auto block whose content is the previous connector's label (the story)
   - *else* → a block "I can't show your results right now", then on
2. After the story, a Processing block "chart" with `shell-feedback` and `part` = `chart`. Its connectors:
   - `chat` → an Auto block with the previous connector's label (the chart), with the event message `done`
   - `both` → the same block, with the event message `show_results`
   - *else* → the same block as above
3. After the chart, on to phase 3 or the end.

The chat page checks that a message comes from Tilbot's own frame. `show_results` loads `/results` from the shell; `done` tells the page that the questionnaire is over, so leaving it needs no warning.

**What passes through Tilbot:** with `panel`, nothing: the message carries no data, and `/results` answers only a signed-in participant, with their own answers. With `chat` and `both`, the story and the chart go from the shell through Tilbot's server to the chat, like the answers of phase 3, and are kept in the transcript, encrypted, when the study keeps transcripts. The shell notes each time the results are shown, and how; the export has it as `feedback.csv`.

## Phase 3: questions

A study with `project/knowledge.xlsx` answers the participant's own questions. The first sheet has one question per row, under a row with these column names:

| Column | Holds | Required |
|---|---|---|
| `id` | a short name for the entry, used in the export | yes |
| `topic` | a group, for the researcher's overview | no |
| `question` | the question as a participant might ask it | yes |
| `phrasings` | other ways to ask the same, one per line (Alt+Enter in Excel) | no |
| `answer` | the answer, exactly as the participant will read it | yes |
| `link` | a web address shown under the answer, clickable (patch 0007) | no |

`project-example/knowledge-example.xlsx` is a filled-in example: rename a copy to `knowledge.xlsx` to switch phase 3 on. With the file present, `start_shell.py` also starts vector-similarity-intent; its first start downloads the language model (about 500 MB, once). The model is Dutch by default; a study in another language sets `INTENT_MODEL` in `.env` to a sentence-transformers model for its language.

The shell sends the participant's question and every question and phrasing to vector-similarity-intent, which returns the one closest in meaning, or nothing when none is close enough. The participant gets that entry's answer word for word: nothing is generated.

**In Tilbot's editor**, once per project, add a second external link under Settings, External processing: name `shell-ask`, address `http://shell:8000/bridge/ask`, send the user's input on, send the connectors off. Then:

1. **A Text block** "Heb je nog een vraag?", whose *else* connector leads to step 2.
2. **A Processing block "ask"**, using `shell-ask`, without parameters. Its connectors:
   - `answered` → an Automatically proceed block whose text is the variable "previous connector label": the shell sends the answer as that label. It leads back to step 1.
   - `unknown` → a block saying the bot has no answer (and who does), back to step 1
   - `busy` → a block saying to try again in an hour: one participant may ask 30 questions an hour (`QUESTIONS_PER_HOUR` in `bridge/views.py`), back to step 1
   - *else* → "Something went wrong, let's try that again", back to step 1

The shell keeps every question with the entry it was matched to (table `records_question`); the question's text only when the study keeps transcripts.

## The Caddyfile, line by line

- **`{$SHELL_HOST} { … }`** is the shell. `encode gzip` compresses responses.
- **The `header` block** sets the security headers:
  - `Content-Security-Policy` allows only the shell's own script and style files (no inline scripts or styles), and frames only from `BOT_HOST`. `frame-ancestors 'none'` stops other sites from framing the shell.
  - `Strict-Transport-Security` tells browsers to use HTTPS only, for a year (`HSTS_MAX_AGE` in `compose.yaml`). In development the age is 0: on `localhost` it would also force HTTPS on every other local project, and 0 makes browsers forget an earlier one.
  - `X-Content-Type-Options` and `Referrer-Policy` are standard hardening.
- **`handle /bridge/*`** answers 404 from outside, because Tilbot reaches the bridge inside Docker.
- **`@dashboards`** answers 404 for `/researcher/` and `/dashboard`, with a line saying where the dashboards are: on the researcher port.
- **`handle /static/*`** serves CSS and images from the shared `static` volume, filled by `collectstatic`. `Cache-Control: no-cache` makes the browser ask each time whether a file changed (a short "not modified" when it didn't), so after an update nobody sees the old CSS.
- **The last `handle`** passes everything else to Django.
- **`{$BOT_HOST} { … }`** is Tilbot's chat:
  - `frame-ancestors` lets only the shell show it.
  - `handle_path /study-theme/*` serves the study's `project/theme/` folder (as collected into the `static` volume), so Tilbot's pages can load `tilbot.css` and the fonts next to it (patch 0009).
  - `@public` lists the only paths participants need; everything else answers 404.
  - Inside `route`, the API, websocket and project files go to the backend, and pages go to the frontend.
- **`:8081 { … }`** is the researcher port, on plain HTTP: the shell's researcher dashboard under `/researcher/` (with their CSS under `/static/`), and Tilbot complete with its dashboard for everything else. It is reachable only where a compose file publishes port 8081, which is `127.0.0.1` in development. The public shell site answers 404 for both dashboards.

## Words used in these docs

- **Shell:** our Django application, everything around Tilbot.
- **Researcher dashboard** (`/researcher/`, ours): counts and the data export. **Tilbot's dashboard** (the rest of port 8081): projects and the flowchart editor. `python start_shell.py researcher` gives a person one name and password for both.
- **Project folder** vs **Tilbot project:** the folder `project/` holds the study's settings; the Tilbot project holds the conversation. `project_id` in `project.toml` links them.
- **Participant:** a person who signs up and talks to the bot. **Researcher:** who runs the study.
- **Project folder (`project/`):** the one folder with everything a study decides, apart from the conversation. Inside the containers it is `/project`.
- **Flowchart:** the conversation as drawn in Tilbot's editor. **Block:** one step in it (a question, a text, a processing step). **Connector:** an arrow leaving a block, with a label that decides where the chat goes next.
- **Processing block / external link:** a block that sends the participant's answer to another server (here: the shell) and follows the connector that server names.
- **Reverse proxy (Caddy):** the one program that faces the internet; it handles HTTPS and passes requests to the shell or Tilbot.
- **HTTPS, certificate:** the encryption of traffic between the browser and the server, and the file that proves the server's name. Locally, Caddy issues its own.
- **Container, image, volume (Docker):** a program packed with everything it needs; the file it is built from; a folder Docker keeps between restarts (the databases live in volumes).
- **Migration:** a file that tells Django how to change the database tables when the models change.
- **Encrypted at rest (Fernet):** the value in the database is unreadable without the key in `.env`.
- **Token:** a signed string that names the participant without revealing the code; forging one needs the server's secret key.
- **CSRF, CSP, HSTS:** browser-side protections against forged forms, injected scripts, and plain-HTTP downgrades.
- **Pinned commit:** the exact version of Tilbot we build, by its git hash, so a build is repeatable.
