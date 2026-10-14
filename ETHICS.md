# What tilbot-shell stores

What the software records, for ethics and data-protection applications (DPIA). Written for the framework; a study's
own description of its participants and purpose belongs in its `/project/README.md`. It describes the
software only; what a particular study decides (retention, who reads transcripts, deletion requests)
belongs to that study's `/project/README.md`. Check this file against the code before every submission.

## Data per participant

| What | Where | Protected by |
|---|---|---|
| A random 4-character code, age, gender, date of sign-up | Postgres, table `accounts_participant` | access to the server |
| Every questionnaire answer: item id, value, time | Postgres, table `records_answer` | the value is encrypted (Fernet: AES-128 with HMAC-SHA256) |
| Every chat message, from the participant and the bot, with its time | Postgres, table `records_transcriptline` | the text is encrypted, as above |

No names, email addresses, phone numbers or other contact details are asked for or stored.
The code is the only link between a person and their data. Whoever holds a code can sign in with it.

## Data about the connection

| What | Where | Why | Kept for |
|---|---|---|---|
| IP address and time of each sign-up and failed sign-in | Postgres, table `accounts_attempt` | slowing down people who guess codes | not cleaned up yet (known gap); the study sets the period |
| A session cookie | the participant's browser | staying signed in | 12 hours |

Caddy, the web server, keeps no access log in this version.

## Where the data lives

- Everything is stored in Docker volumes on the machine that runs the shell. During development this is a researcher's laptop, which must have full-disk encryption.
- Whether this counts as special-category data under the GDPR (health, political opinions, …) depends on the study; the study's `/project/README.md` says so.
- **Tilbot** stores its project definitions and researcher logins in MongoDB. Its own conversation logging is switched off; conversations go to the shell (above).
- **The vector-similarity-intent service** (phase 3, not running yet) will receive the text of participants' questions to match them with the knowledge base. It writes that text to its own log; this has to be fixed before phase 3 is used with real patients.
- **No data leaves the machine**, except backups made by the team.

## Keys and access

- The encryption key (`FIELD_ENCRYPTION_KEY`) is kept apart from the database and from backups (docs/operations.md).
- Who has access to the server, the key and the backups is recorded per study in `/project/README.md`.
