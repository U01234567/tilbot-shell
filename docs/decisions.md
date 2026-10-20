# Decisions

The big choices behind this framework: what we chose, why, and what we turned down.
Smaller choices are explained where they are made, in a comment or in [architecture.md](architecture.md).
A study's own choices (texts, age range, thresholds, retention) live in its `project/README.md`.

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

Everything specific to a study lives in `project/`, which is never committed. This covers settings in TOML, the Tilbot flowchart, the knowledge base, feedback templates, theme and texts. `project-example/` shows its shape. The code contains nothing study-specific, so the same framework runs any study of this shape. One deployment runs one study.

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

**Revisit this before real participants use the system.** On 19 October 2026 it was kept at 4 characters for the proof of concept, with the ethics committee to confirm; a 6-character code (32⁶, about a billion) was the alternative.

- **Email and password.** It is safer, but collects identifying data the study may not want to hold, and adds password resets.
- **A longer code, or a code plus a PIN.** The likely next step, once the proof of concept has been tested.

## vector-similarity-intent for phase 3

Questions in phase 3 are matched to the knowledge base by meaning, in two steps: first the topic, then the question. The answer always comes from the knowledge base itself. The model runs on our own server.

- **A large language model.** It is more flexible, but it writes its own answers, which can be wrong, and usually sends the participant's question to an outside service.
- **Keyword matching.** It is simple, but fails as soon as a participant uses other words.

We use it unchanged and fork it only if matching falls short on a real knowledge base.

## Transcripts: a study setting, never plain text

Whether chat messages are stored is `transcripts.enabled` in `project.toml`, on by default. The shell decides; Tilbot's own logging stays off and its switch is hidden (patch 0002), so a transcript can only ever exist encrypted in the shell's database.

- **Tilbot's own "Logging enabled" switch.** It writes plain text to MongoDB, and a researcher could flip it by accident.
- **Always on, no setting.** Simplest, but a study that must not keep transcripts would have to change code.

## No default admin password

Tilbot's dashboard account `admin` gets its first password from `.env` (patch 0006), filled in by `up` like the other secrets. Without that setting Tilbot refuses to create the account.

- **Keep Tilbot's `admin`/`admin` and tell people to change it.** Documented advice is forgotten; a known default on a research server is a security hole.
- **Fall back to `admin` when the setting is missing.** Easier to merge upstream, but a silent default is exactly what we wanted gone.

## Data leaves through the researcher dashboard, by choice

Researchers export the data from the shell's own dashboard, on the researcher port, with two buttons: without codes (participants numbered by sign-up) or with codes. The page says what each means. Researcher accounts are Django's own, made with `python start_shell.py researcher`.

- **A command that writes CSV files.** No login needed, but researchers asked for a page rather than a terminal, and a command can't explain the choice at the moment it is made.
- **One export, always with codes.** Simpler, but every analysis file would be traceable to a person.
- **Tilbot's dashboard.** It's Tilbot's code, it can't read the shell's database, and it would need another large patch.

## One account per person, two dashboards

The researcher port has two dashboards: Tilbot's, for the conversation (projects, the flowchart, data tables), and ours at `/researcher/`, for the participants' data (counts and the decrypted export). `python start_shell.py researcher` gives a person one name and password for both: an account in our dashboard, and a Tilbot account made through Tilbot's own "create user" call, with Tilbot's admin password from `.env`. Nobody logs in as Tilbot's admin; it is plumbing.

- **Two separate accounts per person.** Each login guards only what it must, but one researcher running one study then juggles three logins (Tilbot's admin, a Tilbot account, ours) and two meanings of "researcher". Someone who should only build the flowchart can still get a Tilbot account alone, made by hand as admin.
- **One login for both (single sign-on).** Tilbot would have to trust the shell's login, through a patch in Tilbot's account and session code: far larger than our other patches.
- **Researcher accounts inside Tilbot.** Tilbot can't read the shell's database, and its accounts live in a store (MongoDB) we keep free of participant data.

The catch: the two passwords are stored apart, so changing one in a dashboard leaves the other as it was.

## Results beside the chat, drawn by the shell

Phase 2 shows each scale of `project/feedback.toml` (a score from 0 to 100), once every item is answered. Since 19 October 2026 the panel is kept simple and is meant to read without explanation: per scale a card with its name, a word ("worth discussing" or "going well"), and one line from worse to better with a dot where the participant is: light orange up to the threshold, light green after it, with the scale's own words at both ends ("a lot of pain" … "no pain"). Under the line, the questions it is based on, each with the participant's own answer (the question's `text` in `questionnaire.toml`), so every dot maps visibly onto what they just answered; a scale of several items shows all of them. A × closes the panel. The shell draws it (SVG, no chart library) in a panel beside the chat, over it on a phone, and the chat keeps running underneath. The flowchart opens it with Tilbot's own "Message to parent window" event, so Tilbot needs no patch, and the results never pass through Tilbot: the panel fetches them from the shell with the participant's session. Every line reads the same way, better to the right, so a patient learns it once; the panel shows no numbers, so nothing contradicts the export, where scores keep their official direction (higher is better for functioning, worse for complaints).

- **A separate results page.** Simpler, but leaving the chat page ends the conversation: Tilbot starts again from the top when its frame reloads.
- **Results as chat messages.** Turned down at first (Tilbot shows text only, and the texts travel through Tilbot); since version 1.1 a study can choose them (next section).
- **Each line in the scale's official direction.** Matches the literature, but a patient has to work out per scale which side is good; with no numbers on the panel, nothing is lost by turning complaints around.
- **A bar from 0 instead of a dot.** A bar's length reads as "how much", which means trouble for pain and the opposite for functioning; a dot on a line between two named ends reads as "where I am".
- **More on the panel: a sentence and a definition per scale, groups, an explanation of the line, a print button.** Built first, then left out: participants were given too much at once.
- **One line per question instead of per scale.** Maps one to one onto the chat, but the thresholds belong to the scales (as in the literature), so per-question bars would need thresholds nobody published. A study that wants it can make each item its own scale in `feedback.toml`, without code.
- **Colour per zone of the bar** (the part past the threshold orange). On a scale where higher is better, a fine score would still show orange below the line, so the dot takes one colour and the line shows the zones.

## Phase 3: answers from the study's own knowledge base

Participants' questions are matched to `project/knowledge.xlsx`, one question per row with example phrasings, and answered word for word from it. The shell asks vector-similarity-intent which question or phrasing is closest in meaning, in one step over all of them; a wrong match or no match says so instead of guessing. Every question asked is kept with the entry it matched (the text only when the study keeps transcripts), so a study can evaluate the matching. Links in answers are clickable through a small Tilbot patch.

- **The knowledge base as CSV or TOML.** No extra library, but Dutch Excel breaks CSV (semicolons, accents), and 100 long answers are awkward in TOML. Excel is what researchers edit; reading it costs one small, pure-Python library (openpyxl).
- **Two steps, topic first, then the question.** Helps when many questions look alike across topics, but a wrong topic in the first step makes the second fail. The topic stays in the file; two steps can follow once a real knowledge base shows the need.
- **A language model that writes its own answers.** More flexible, but its answers can be wrong, and the question would usually go to an outside service.
- **Links in the panel beside the chat, or as plain text.** The panel keeps everything ours but covers the chat on a phone after each answer; plain text makes participants copy addresses. The patch is about 15 lines and builds no HTML from the message.
- **No separate questions table.** The transcripts hold the questions, but not what they were matched to.

## Backups hold the whole study, encrypted with the field key, and are checked

`python start_shell.py backup` saves the shell's database, Tilbot's database and files, and `project/` in one folder, each file encrypted with `FIELD_ENCRYPTION_KEY`, and restores the database once into a scratch database before calling it a backup. `restore` checks a backup before it replaces anything, and keeps the old `project/` aside. `update` is a backup, a rebuild and the tests, stopping at the first failure.

- **The shell's database only.** Smaller, but a restore would give participants without their flowchart.
- **Unencrypted, kept somewhere safe.** Answers and transcripts are encrypted inside the dump already, but codes, ages, genders, password hashes and flowcharts are not, and one careless copy would expose them.
- **A separate backup password.** One more secret to lose; the field key is needed to read the answers anyway, so it adds no protection.
- **A button in the researcher dashboard.** The shell's container would need access to Docker and to the database tools of every service: a door we keep shut.

## Deleting data is a researcher's decision

One participant is removed from the researcher dashboard (code, then what will be deleted, then a confirmation); a whole study with `python start_shell.py erase`, which asks for the study's name. Only technical leftovers go by themselves: sign-in attempts after 15 minutes, expired sessions at every start of the shell and every backup, and container logs beyond 3 × 10 MB per service.

- **Automatic deletion after a number of days in `project.toml`.** Hands-off, but one wrong number deletes research data before anyone analysed it.
- **Removal by command only.** Researchers asked for screens over commands; one participant's request is an everyday task.

## Leaving halfway asks first

Signing out shows a question in the study's own words (`sign_out_check` and `stay` in `project.toml`), and while the results haven't been shown, closing or leaving the chat page brings up the browser's own "Leave site?" question. Leaving halfway loses the participant's place: Tilbot starts the conversation again.

- **Only the sign-out question.** Some find the browser's warning pushy, but a closed tab loses the same place as a sign-out.
- **Our own leave dialog.** Browsers don't allow one: on leaving, only their own question, in their own words, can appear.

## Results in the chat or beside it, chosen per study

`show` in `feedback.toml` chooses how the results appear at the end of the questionnaire: `panel` (beside the chat), `chat` (a short story, then a small chart, as two chat messages) or `both`. The flowchart asks the shell (`/bridge/feedback`) and has a route for each, so a study, or a developer preparing a demo, switches with one line and `restart shell`. The story is rule-based: per scale the study writes a sentence for "fine", "worth discussing" or no threshold, with blanks the shell fills in from the answers; nothing is generated freely. Tilbot draws the chart's lines with patch 0011. The shell notes for every participant when the results were shown and how (`feedback.csv` in the export), so a study that switches halfway still knows who saw what. A returning participant doesn't see the results again: they come once, at the end of the questionnaire.

- **The setting in `project.toml`.** Everything about the results already lives in `feedback.toml`.
- **The chart as plain text** (a line of characters). No patch, but no colour, and lines that don't line up in a proportional font.
- **The chart as an image from the shell.** Needs a patch too, and the image would have to carry the participant's login across sites.
- **The story and the chart in one message.** Harder to read; two messages cost one block more.
- **The results again on a return visit,** with a button or a question. More to explain and to build; a returning participant comes for a question.
- **Dividing participants over panel and chat automatically.** Not asked for: a setting is enough for showing both. The shell decides per call, so this stays a small step for later.

## A returning participant skips the questions

Every chat starts with a call from Tilbot to the shell (`/bridge/status`): a participant who answered every item already gets a welcome back and goes straight to their questions (phase 3), without seeing the results again. Everyone else starts the questionnaire. No Tilbot patch: the starting block of the flowchart is a Processing block.

- **The shell picks a different Tilbot project for returning participants.** No flowchart change, but two projects to keep in step.
- **Ask everything again.** Simplest, but the participant repeats work, and the latest answers would replace the first.

## The system page reads Docker through a proxy

The researcher dashboard draws every component and who calls whom, green, orange or red by Docker's health check, with CPU, memory and each component's last log lines (`/researcher/system`). The shell reads Docker through `docker-proxy` (`wollomatic/socket-proxy`), which passes on only the list of containers and a container's resource use and log, and only to the shell. The traffic on the arrows comes from the shell's own records (answers, chat lines and questions of the last hour), so no request log was added. Energy use waits for a server, where it can be measured.

- **Docker's socket in the shell, read-only.** "Read-only" applies to the file, not to what Docker does: the socket can still start containers and read every secret. One break-in in the shell would own the machine.
- **A ready-made tool (Portainer, Dozzle, Grafana).** Quicker, but another login, logs shown in full, no picture of who calls whom, and much more code to trust.
- **A command only** (`start_shell.py status`). Simplest, but not the visual overview that was asked for, and not for researchers without a terminal.
- **Hiding participants' text on the page with patterns.** Fragile: a missed pattern shows it anyway. Tilbot stops writing it instead (patch 0010), which also keeps it out of the logs on disk.

## Known gaps in version 1.1

- **Not built yet:** updates as planned (the new version switched on only after its tests pass, the old one kept to go back to, and a notice in the dashboard when an update exists); the test that runs Tilbot's own engine against the shell, in the repository; backups on a schedule; running on a server; energy use; and several versions of a chatbot side by side (participants divided over Tilbot projects).
- **A participant can't do the questionnaire again** once every item is answered.
- **Tilbot's two servers have no health check.** Their API has no call without side effects to check with; the shell, both databases and the matching service do have one.
- **Matching is tested with a stand-in, not the real model.** The language model is too large for the automated tests; check the matching on the real knowledge base before a study starts, and add phrasings where it misses.
- **The answer to a question can't use the participant's own data** ("your pain score is …") yet.
- **Transcripts are best-effort.** If the shell is down, Tilbot logs an error and that line is lost. Answers are not lost: they are asked again.
- **The `transcripts.enabled` setting is read by the shell only.** Tilbot still sends every event; the shell discards them. That costs nothing but is worth knowing.
- **Questionnaire answers are numbers or fixed words** (`labels` in `questionnaire.toml`); free text is only for questions (phase 3).
- **The results' scores are mean-based (0–100).** Questionnaires scored by a plain sum would need a second method in `phase2_feedback/scoring.py`.
- **The patches were made against the code of 12 October 2026.** If they don't apply to a newer pinned commit, regenerate them.
- **Tilbot's dashboard is only reachable in development.** `compose.yaml` doesn't publish port 8081, so on a server researchers have no way in yet (an SSH tunnel is the likely answer).
