# What tilbot-shell stores

What the software records, for ethics and data-protection applications (DPIA, a data-protection impact
assessment). This file describes the software only; what a particular study decides (its participants,
purpose, retention, who reads transcripts, deletion requests) belongs to that study's `project/README.md`.
Check this file against the code before every submission.

## Data per participant

| What | Where | Protected by |
|---|---|---|
| A random 4-character code, age, gender, date of sign-up | Postgres, table `accounts_participant` | access to the server |
| Every questionnaire answer: item id, value, time | Postgres, table `records_answer` | the value is encrypted (Fernet: AES-128 with HMAC-SHA256) |
| Every chat message, from the participant and the bot, with its time; only if `project.toml` says `transcripts.enabled = true` | Postgres, table `records_transcriptline` | the text is encrypted, as above |
| Which participant a browser is signed in as, and the code shown on the sign-up page | Postgres, table `django_session` | deleted after 12 hours |

## Researcher accounts

Researchers log in to the shell's dashboard with Django's own accounts (table `auth_user`: a name and a
hashed password). Participants are not in that table. `python start_shell.py researcher` also makes a Tilbot
account with the same name and password (MongoDB, hashed). Both dashboards are only reachable from the
computer that runs the shell.

No names, email addresses, phone numbers or other contact details are asked for or stored.
The code is the only link between a person and their data. Whoever holds a code can sign in with it.

## Data about the connection

| What | Where | Why | Kept for |
|---|---|---|---|
| IP address and time of each sign-up and failed sign-in | Postgres, table `accounts_attempt` | slowing down people who guess codes | 15 minutes: every new attempt deletes the older ones |
| A session cookie | the participant's browser | staying signed in | 12 hours |

For those 15 minutes, an attempt's IP address and a participant's sign-up time can be matched to each
other by whoever reads the database.

Caddy, the web server, keeps no access log. The containers' own output (`docker compose logs`) can
contain a participant's raw answer when the shell refuses it (an answer off the scale), and error
messages from Tilbot; those logs live on the machine and are not kept after the containers are removed.

## What the participant's browser is given

The chat page passes Tilbot a signed token that names the participant's row number in the database,
never the code. Anyone who reads the page's address sees that number. It cannot be forged.

If the study has `feedback.toml`, the participant sees their own results beside the chat: a score per
scale, computed from their latest answers each time the results open, and never stored. Only the signed-in
participant can load their results; Tilbot only sends the signal to open them and never sees the scores.
Whether a result is shown as "worth discussing" comes from the thresholds the study chose; how that is
worded, so that it never reads as a diagnosis, is the study's responsibility (`project/README.md`).

## Where the data lives

Everything is stored in Docker volumes on the machine that runs the shell. During development this is
a researcher's laptop, which must have full-disk encryption.

| Volume | Holds | Participant data? |
|---|---|---|
| `db` | the Postgres database: everything in the tables above | yes, encrypted where the tables say so |
| `mongo` | Tilbot's researcher logins (hashed passwords), project definitions, dashboard settings | no; Tilbot's own conversation logging is off |
| `tilbot-projects`, `tilbot-public` | the flowcharts' data tables and avatars (uploaded by researchers; an SVG avatar is served as is) | no |
| `static`, `caddy-data`, `tilbot-shell-caddy-ca` | the shell's CSS, Caddy's certificates | no |
| `models` | the language model for phase 3 (not used yet) | no |

Whether this counts as special-category data under the GDPR (health, political opinions, …) depends
on the study; the study's `project/README.md` says so.

**The vector-similarity-intent service** (phase 3, not running yet) will receive the text of
participants' questions to match them with the knowledge base. It writes that text to its own log;
this has to be fixed before phase 3 is used with real participants.

## What leaves the machine

- **No participant data**, except backups and exports made by the team. An export (researcher dashboard)
  contains answers, scale scores and transcripts decrypted, with either the participants' codes or numbers instead;
  the page explains the difference. Where exports are kept is the study's decision (`project/README.md`).
- At build time the machine downloads code and images: Tilbot and vector-similarity-intent from
  GitHub, container images from Docker Hub, Python packages from PyPI, Node packages from npm, and
  for phase 3 the language model from Hugging Face. `python start_shell.py updates` asks GitHub for the
  newest commit. On a real domain, Caddy asks Let's Encrypt for certificates. None of these requests
  carry anything about participants.

## Our changes to Tilbot

Tilbot runs with six small patches, listed in `docs/architecture.md`. Two of them matter here: one
makes Tilbot send conversation events to the shell instead of its own database (so nothing is stored
in plain text), and one passes the participant token above along with each call to the shell.

## Keys and access

- The encryption key (`FIELD_ENCRYPTION_KEY`) is kept apart from the database and from backups (docs/operations.md).
- Who has access to the server, the key and the backups is recorded per study in `project/README.md`.
