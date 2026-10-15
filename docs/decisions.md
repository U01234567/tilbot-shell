# Decisions

The big choices behind this framework: what we chose, why, and what we turned down.
Smaller choices are explained where they are made, in a comment or in [architecture.md](architecture.md).
A study's own choices (texts, age range, thresholds, retention) live in its `/project/README.md`.

When a big choice changes, rewrite its section here and say what changed and when.

## A shell around Tilbot

The study features (accounts, participant data, rules, feedback, a dashboard) live in a separate application, the shell. Tilbot runs next to it, almost unchanged.

Tilbot is a general tool for anonymous research conversations, and its editor is where researchers draw a conversation. We want to keep both, and keep taking Tilbot's updates.

- **Build the features into Tilbot.** Participant data would end up in a tool designed to hold none, and our copy would drift too far from upstream to update.
- **Write our own chatbot.** We would lose the editor and rebuild what already works.

## Patch files, not a fork

When Tilbot lacks something, we add a small patch in `tilbot/patches/`, applied at build time to the pinned commit. Each patch is one concern, small enough to read in a minute and to offer upstream. Once upstream merges it, the patch file is deleted.

- **A fork.** Our changes would disappear into a long history, and every update would be a merge.
- **A workaround in the shell.** Some things can only be done inside Tilbot. A workaround elsewhere would make our own code more complex than a ten-line patch.

## Flowcharts are made in the browser

Researchers draw the flowchart in Tilbot's editor, opened from the dashboard, and it is stored on our own Tilbot server. Upstream, that editor only works inside Tilbot's desktop app. Patch 0005 lets it run in the browser against the server, and is offered upstream. Patch 0004 makes Tilbot's data tables safe to reach over the network first.

- **Tilbot's desktop app**, built by the Tilbot team or by us. That's a second program to install, kept at the same version as the server, for something the server can host. Building it ourselves would also mean an Electron build inside Docker that we can't test on every system.
- **Writing the flowchart as a file by hand.** No visual editor, so not something researchers can work with.

## The shell is the hub

Tilbot only talks to the shell, and only the shell talks to vector-similarity-intent. Tilbot never sees who the participant is: it carries a signed token that only the shell can read.

That gives one place for access checks and logging, and one place where participant data lives.

- **Tilbot calls the intent service directly.** It can, but then the knowledge base and the participant's data would have to be reachable from Tilbot too.
- **Pass the participant's code to Tilbot.** The code is the login. It would end up in Tilbot's URLs and logs.

## Django for the shell

Django brings most of the security this application needs, already built and widely used:
- protection against cross-site request forgery;
- form validation on the server;
- escaping in templates;
- an ORM that rules out SQL injection;
- signed tokens;
- migrations that keep the database in step with the code.

The team also knows Python.

- **FastAPI**, like vector-similarity-intent. It is good for APIs, but forms, sessions, CSRF protection and migrations would have to be put together from separate packages.
- **Node / SvelteKit**, like Tilbot. It is one language for both, but has no framework with the same security built in, and the team knows Python better.

## Postgres for participant data

Answers, transcripts and accounts are stored in Postgres, separate from Tilbot's MongoDB.

- **SQLite.** Simpler (one file), but it locks the whole database on every write, and moving to a server later means migrating data.
- **MongoDB, already running for Tilbot.** Django's ORM and migrations are built for relational databases. Keeping participant data out of Tilbot's database is also the point of the hub.

## Answers and transcripts encrypted per field

Every answer and transcript line is encrypted (Fernet) before it reaches the database. A database dump or backup on its own reveals nothing. The key lives in `.env` and is backed up separately; without it, the data can't be read.

- **Disk encryption only.** It protects a stolen disk, but not a leaked dump or a backup copied somewhere.
- **Encryption inside Postgres (pgcrypto).** The key would travel along with every query and could end up in logs.
- **No encryption.** Not acceptable for health or other sensitive data.

The cost is that the database can't search or sort on encrypted values. The shell does that in Python, which is fine for a study's size.

## Caddy in front

One reverse proxy handles HTTPS, sets the security headers, and decides which of Tilbot's routes are public. Tilbot's dashboard is never one of them.

- **nginx.** More common, but certificates need a separate tool (certbot) and the configuration is longer.
- **Traefik.** It is configured through labels spread over the compose file, which suits many changing services, not our fixed few.
- **Nothing in front.** Gunicorn and Tilbot's servers would face the internet directly, without HTTPS.

Caddy gets certificates by itself, including a local one for `localhost`, and its configuration fits on one screen.

## Docker Compose for everything

Every part runs in a container, started with one command on Windows, macOS, Linux or a server. `compose.dev.yaml` adds only what differs in development.

- **Install everything by hand** (Node, Python, Postgres, MongoDB). It differs per machine and breaks easily, especially on Windows.
- **One installer, like Tilbot's desktop editor.** Six services that talk over a network don't fit in one `.exe`.
- **Kubernetes.** Far more than one study on one server needs.

## Pinned versions, patch updates only

Tilbot and vector-similarity-intent are pinned to an exact commit in `components.toml`. Python packages are locked to exact versions with hashes, and take bug-fix updates only. Before every update: back up, build, test, then switch.

The rule behind this is that no answer may ever be lost silently. An update that changes behaviour without warning is the easiest way to lose data.

- **Follow upstream's latest version.** Every build could be different, and a change upstream could break a running study overnight.
- **Allow minor updates.** Less work, but minor versions do change behaviour. Moving up a minor or major version is a decision, written here first.

## One project folder per study

Everything specific to a study lives in `/project/`, which is never committed. This covers settings in TOML, the Tilbot flowchart, the knowledge base, feedback templates, theme and texts. `project-example/` shows its shape. The code contains nothing study-specific, so the same framework runs any study of this shape. One deployment runs one study.

- **Study settings in the code.** Every study would need its own copy of the code.
- **Study settings in the database, edited through a web page.** That needs an editor to be built, and the settings could no longer be read, copied or backed up as files.
- **Several studies per deployment.** Every table and page would have to know which study it belongs to.

TOML rather than a Python file, YAML or JSON:
- researchers can edit it without being able to break code;
- it allows comments;
- Python reads it without an extra package.

## The questionnaire in Tilbot's editor, the rules in the shell

Researchers write the questions where they see the conversation, in Tilbot's editor. After each answer, a save block sends it to the shell. The shell stores it and replies which way to go: next question, follow-ups, or ask again if saving failed. Thresholds live in the project folder.

- **The shell sends each question itself (a loop).** One source for questions, and a participant could resume halfway, but researchers lose the visual editor.
- **Everything in Tilbot.** Tilbot would decide on follow-ups, and the shell would not know whether an answer was stored.

The cost: a conversation always starts at the beginning, so a participant who leaves halfway starts again. Answers already given stay stored. This is fine for short questionnaires.

## Transcripts only when stored securely

Full transcripts are kept, because studies need them for evaluation. They are stored by the shell, encrypted, next to the answers; a small patch makes Tilbot send them there. Tilbot's own logging stays off. If transcripts can't be stored securely, they are not stored.

- **Tilbot's own logging.** It stores plain text in MongoDB, unencrypted and not linked to the participant.
- **No transcripts.** Safest, but studies lose what they need to evaluate the conversations.

## A 4-character code as the only login, for now

A participant signs up with age and gender, and gets a random 4-character code. That code is their only login. It is deliberately simple for a proof of concept, and less secure than a password:

- There are 1,048,576 possible codes. With 200 participants, one random guess hits someone with a chance of 1 in 5,243. A lockout after repeated failures limits guessing from one address.
- A lost code can't be recovered.

**Revisit this before real participants use the system.**

- **Email and password.** It is safer, but collects identifying data the study may not want to hold, and adds password resets.
- **A longer code, or a code plus a PIN.** The likely next step, once the proof of concept has been tested.

## vector-similarity-intent for phase 3

Questions in phase 3 are matched to the knowledge base by meaning, in two steps: first the topic, then the question. The answer always comes from the knowledge base itself. The model runs on our own server.

- **A large language model.** It is more flexible, but it writes its own answers, which can be wrong, and usually sends the participant's question to an outside service.
- **Keyword matching.** It is simple, but fails as soon as a participant uses other words.

We use it unchanged and fork it only if matching falls short on a real knowledge base.

## Known gaps in version 0.1

- **Not built yet:** phase 2, phase 3 (and so the knowledge base), the monitor dashboard, our own chat route, backups and the update flow in `start_shell.py`.
- **vector-similarity-intent is started with `--profile phase3`** until phase 3 exists, so developers don't download its model for nothing.
- **Transcripts are best-effort.** If the shell is down, Tilbot logs an error and that line is lost. Answers are not lost: they are asked again.
- **IP addresses in `Attempt` are not cleaned up yet.** They need a retention period (see `ETHICS.md`).
- **Only number answers** are supported in phase 1.
- **No healthchecks** in the compose files yet.
- **The patches were made against the code of 12 October 2026.** If they don't apply to a newer pinned commit, regenerate them.
- **The chat token shows the participant's row number.** It is signed, so it can't be forged, but someone who inspects the chat's address sees roughly how many people signed up before them. A random id per participant would close this.
- **Tilbot's dashboard is only reachable in development.** `compose.yaml` doesn't publish port 8081, so on a server researchers have no way in yet (an SSH tunnel is the likely answer).
