# What tilbot-shell stores

What the software records, for ethics and data-protection applications (DPIA, a data-protection impact
assessment). This file describes the software only; what a particular study decides (its participants,
purpose, retention, who reads transcripts, deletion requests) belongs to that study's `project/README.md`.
Check this file against the code before every submission.

## Data per participant

| What | Where | Protected by |
|---|---|---|
| A random 4-character code, age, gender, date of sign-up; or, with sign-in by link, the ID in the link and no age or gender. Also the current round, and, with `narrative.toml`, the condition and the story's main character | Postgres, table `accounts_participant` | access to the server |
| Every questionnaire answer: item id, value, round, time | Postgres, table `records_answer` | the value is encrypted (Fernet: AES-128 with HMAC-SHA256) |
| Every chat message, from the participant and the bot, with its time; only if `project.toml` says `transcripts.enabled = true` | Postgres, table `records_transcriptline` | the text is encrypted, as above |
| Every question typed in phase 3, with the knowledge base entry it matched and its time; the text only if `transcripts.enabled = true` | Postgres, table `records_question` | the text is encrypted, as above |
| When the results were shown, and how (panel, chat or both) | Postgres, table `records_feedbackshown` | access to the server; it holds no answers |
| With `narrative.toml`: the story each round, written by a language model from the answers, with the main character's name and whether the model wrote it | Postgres, table `records_narrative` | the text is encrypted, as above |
| Which participant a browser is signed in as, and the code shown on the sign-up page | Postgres, table `django_session` | expires after 12 hours, and is deleted at the next start of the shell or backup |

## Researcher accounts

Researchers log in to the shell's dashboard with Django's own accounts (table `auth_user`: a name and a
hashed password). Participants are not in that table. `python start_shell.py researcher` also makes a Tilbot
account with the same name and password (MongoDB, hashed). Both dashboards are only reachable from the
computer that runs the shell.

No names, email addresses, phone numbers or other contact details are asked for or stored.
The code is the only link between a person and their data. Whoever holds a code can sign in with it. With
sign-in by link, the ID in the link plays that part: whoever has someone's link can answer as them, and the other
app (m-Path, for example) knows who the ID belongs to.

## Removing data

A researcher can remove one participant, with all their answers, questions, transcript lines, stories, the notes of
when their results were shown, and their sign-in sessions, from the researcher dashboard ("Remove a participant", by their code), and every
participant at once at the end of a study (`python start_shell.py erase`). Neither happens automatically.
Backups made before keep the removed data until they are deleted themselves.

## Data about the connection

| What | Where | Why | Kept for |
|---|---|---|---|
| IP address and time of each sign-up and failed sign-in | Postgres, table `accounts_attempt` | slowing down people who guess codes | 15 minutes: every new attempt deletes the older ones |
| A session cookie | the participant's browser | staying signed in | 12 hours |

For those 15 minutes, an attempt's IP address and a participant's sign-up time can be matched to each
other by whoever reads the database.

Caddy, the web server, keeps no access log. The containers' own output (`docker compose logs`) holds, in
development, the addresses the shell was asked for (never a form's content), the knowledge base phrasings the intent service
compared, and error messages; an error can quote a participant's raw answer when the shell refuses it (an
answer off the scale). Tilbot itself printed every message a participant typed; patch 0010 stops that
(below). Tilbot 2.1 logs the address of every request it gets; for the chat that address holds the
participant token (`pid=…`, see below), which is encrypted, names no code and no answer, and expires after 12
hours. Those logs live on the machine, are capped at 3 files of 10 MB per service (older lines go first),
and are not kept after the containers are removed.

## The system page

The researcher dashboard has a page "System" (`/researcher/system`) that shows each component, whether it
runs, its CPU and memory use, and its last 40 log lines, so the team sees how the system is doing without a
terminal. Anyone with a researcher account sees it, like the export. It reads this from Docker each time it
opens and stores nothing.

The shell never talks to Docker itself: Docker's own connection can start containers, read their files and
their settings (which hold the passwords and keys), and so control the whole machine. A small proxy,
`docker-proxy` (the open-source `wollomatic/socket-proxy`, at a fixed version), sits in between. It accepts
calls only from the shell, and passes on only three kinds of reading: the list of containers, a container's
resource use, and a container's log. Everything else is refused, including a container's settings and files.
It runs without any of the system's special powers (`cap_drop: ALL`), on a read-only file system, and is
reachable only inside the Docker network. Should the shell be broken into, this limits what Docker reveals to
what the page shows.

## What the participant's browser is given

The chat page passes Tilbot an encrypted token that names the participant's row number in the database,
never the code. Whoever reads the page's address can't read the number from it, and can't forge a token.
It expires after 12 hours.

If the study has `feedback.toml`, the participant sees their own results once, at the end of the
questionnaire, computed from their latest answers and never stored as such; the shell only notes when, and
how. `show` in that file decides how. Beside the chat (`panel`), only the signed-in participant can load their
results, and Tilbot only sends the signal to open them and never sees them. In the chat (`chat` or `both`),
a short story and a small chart, made by the shell from the study's own sentences and the answers, go through
Tilbot's server to the chat, like the answers of phase 3; Tilbot keeps them only in its memory for that
conversation, and the shell stores them in the transcript, encrypted, when the study keeps transcripts. In
both cases no score is shown, only words and a dot on a line.
Whether a result is shown as "worth discussing" comes from the thresholds the study chose; how that is
worded, so that it never reads as a diagnosis, is the study's responsibility (`project/README.md`).

## Where the data lives

Everything is stored in Docker volumes on the machine that runs the shell. During development this is
a researcher's laptop, which must have full-disk encryption.

| Volume | Holds | Participant data? |
|---|---|---|
| `db` | the Postgres database: everything in the tables above | yes, encrypted where the tables say so |
| `mongo` | Tilbot's researcher logins (hashed passwords), project definitions, dashboard settings; the database needs a login (`MONGO_TILBOT_PASSWORD`) | no; Tilbot's own conversation logging is off |
| `tilbot-projects`, `tilbot-public` | the flowcharts' data tables and avatars (uploaded by researchers; an SVG avatar is served as is) | no |
| `static`, `caddy-data`, `tilbot-shell-caddy-ca` | the shell's CSS, Caddy's certificates | no |
| `models` | the language model for phase 3, downloaded once, only for a study with `knowledge.xlsx` | no |

Whether this counts as special-category data under the GDPR (health, political opinions, …) depends
on the study; the study's `project/README.md` says so.

**The vector-similarity-intent service** runs only for a study with `knowledge.xlsx`. A question the
participant types goes from Tilbot to the shell, and from the shell to this service, both inside the Docker
network. It keeps nothing, logs only the knowledge base's own phrasings with their scores (its `main.py` at
the pinned commit), and calls no outside service once its language model is downloaded. The answer is
taken word for word from `knowledge.xlsx`: nothing is generated.

## What leaves the machine

- **Backups** (`python start_shell.py backup`) hold everything in the volumes above and the project folder,
  every file encrypted with `FIELD_ENCRYPTION_KEY`; they can't be read without that key, which is never in a
  backup. They are written to `backups/` on the same machine unless the team names another place; copies
  elsewhere, and how long they are kept, are the study's decision (`project/README.md`).
- **No other participant data**, except exports made by the team, and what a study's own services send (below). An export (researcher dashboard)
  contains answers, scale scores, when and how the results were shown, questions and transcripts decrypted, with either the participants' codes or numbers instead;
  the page explains the difference. Where exports are kept is the study's decision (`project/README.md`).
- At build time the machine downloads code and images: Tilbot and vector-similarity-intent from
  GitHub, container images from Docker Hub, Python packages from PyPI, Node packages from npm, and
  for phase 3 the language model from Hugging Face. `python start_shell.py updates` asks GitHub for the
  newest commit. On a real domain, Caddy asks Let's Encrypt for certificates. None of these requests
  carry anything about participants.

## A story by a language model

With `narrative.toml`, the shell sends this round's answers (in the words of their buttons), the main character's
name and, in a condition that continues the story, the earlier stories, to the language model the file names. With
Ollama in the study's `compose.yaml`, this stays on the machine. With a model by API key, it goes to that provider.
The model's output is shown to the participant as it is, within the study's prompt and the shell's word limit;
whether a generated text is acceptable for the study's participants is the study's to decide, in
`project/README.md`.

## A study's own services

A study can run services of its own beside the shell, in `project/compose.yaml`, such as a language model. The shell doesn't see what passes between Tilbot and such a service, and can't vouch for what it logs or sends on: Tilbot's own modules print the messages they get to their log. Tilbot gives them neither the participant's token nor the bridge secret (patch 0001), but does send what the participant typed and, where the link's chat history is on, the conversation. A model by API key sends this to its provider, off the machine; a local model keeps it on the machine. What a study's services keep, log and send, and whether the participant sees generated text, is the study's to decide and write in `project/README.md`.

## Our changes to Tilbot

Tilbot runs with fifteen small patches, listed in `docs/architecture.md`. Three of them matter here: one
makes Tilbot send conversation events to the shell instead of its own database (so nothing is stored
in plain text), one passes the participant token above along with each call to the shell, and one
(0010) stops Tilbot from printing participants' messages in its log.

Tilbot 2.1 can send the recent chat history along with a call to an external service (a setting per external link, off unless switched on). The shell's own links don't use it. Switched on for a link to an outside service, that service receives the conversation: a study decision, to record in `project/README.md`.

## Keys and access

- The encryption key (`FIELD_ENCRYPTION_KEY`) is kept apart from the database and from backups (docs/operations.md).
- Who has access to the server, the key and the backups is recorded per study in `project/README.md`.
