# Operations

Setting up, running, deploying a Tilbot project, backups and updates.
Every command runs from the repository root. `start_shell.py` picks the right compose files and pinned commits; any command it doesn't know goes straight to `docker compose`.

## Before you start

- **Docker, running.** Docker Desktop on Windows and macOS, Docker Engine on Linux. Every command except `updates` needs it; `start_shell.py` says so when it isn't running.
- **Python 3.11 or newer, and Git.**
- **Free ports.** 80 and 443, and in development 8081 and 5432 on this computer. A web server or a Postgres you installed yourself can hold them; `up` then names the service that didn't start.

## Set up on a new computer

1. **Get the code.**
   ```
   git clone https://github.com/U01234567/tilbot-shell
   cd tilbot-shell
   ```
   For a real study, put its `project/` folder here now; otherwise `up` copies `project-example/`.
2. **Start everything.** The first build takes several minutes and downloads about two gigabytes; the terminal shows every build step.
   ```
   python start_shell.py up
   ```
   The first run creates `.env` with fresh secrets. You should see **"Everything is running."** If a service is named as not running, its log says why: `python start_shell.py logs <service>`.
3. **Back up the encryption key.** Copy `FIELD_ENCRYPTION_KEY` from `.env` to two safe places (see [Keys](#keys)).
4. **Trust the local certificates,** once per computer. Caddy keeps its root certificate in the volume `tilbot-shell-caddy-ca`, which `down -v` leaves alone, so this stays valid.
   ```
   python start_shell.py trust
   ```
   On Windows it asks you to confirm, then says **"Trusted."** On macOS and Linux it prints one command to run yourself. Restart your browser afterwards. Firefox may need the file imported under Settings, Certificates, Authorities.

   Without this, accept the browser's warning on https://localhost **and** https://bot.localhost. Caddy renews its certificates every 12 hours, so the warning comes back, and until https://bot.localhost is accepted the chat stays blank.

   To start with a new root certificate (rarely needed): `python start_shell.py down`, then `docker volume rm tilbot-shell-caddy-ca`, then `up` and `trust`. Remove the old one under "Manage user certificates" (Windows) or Keychain Access (macOS).
5. **Run the tests.**
   ```
   python start_shell.py exec shell pytest
   ```
   You should see every test pass.
6. **Open https://localhost.** You should see the study's name and two buttons, sign up and sign in, in the study's language. After signing up, the chat page says "No Tilbot project is linked yet" until you have done [your study, start to finish](#your-study-start-to-finish).

## If something is wrong

| You see | Do this |
|---|---|
| "Docker is not running" | Start Docker Desktop, wait until it says it is running, try again |
| "Not running: *service*" after `up` | `python start_shell.py logs <service>`; a port in use is a common cause |
| A certificate warning on https://localhost | `python start_shell.py trust`, then close **every** browser window, private ones too, and reopen |
| A browser error inside the chat frame | The same, or open https://bot.localhost once and accept the warning |
| "No Tilbot project is linked yet" | Follow [your study, start to finish](#your-study-start-to-finish) |
| "… is empty in .env, but the database was made with the old value" | Put the value back from your backup (see [Keys](#keys)) |
| `researcher` says Tilbot refused its admin password | Someone changed it in Tilbot's dashboard. Put the same value in `.env` as `TILBOT_ADMIN_PASSWORD` and run `up`, or reset the admin (next row) |
| The system page says "Docker can't be read" | `python start_shell.py ps`: is `docker-proxy` running? On Linux with rootless Docker or Podman the socket isn't at `/var/run/docker.sock`; change the line in `compose.yaml` |
| Tilbot's admin password is lost | Delete only the admin account; projects belong to Tilbot accounts and stay. `python start_shell.py exec mongo mongosh tilbot --eval "db.users.deleteOne({role: 99})"`. The next visit to the login page makes `admin` again, with the password from `.env` |

## Running a study

| Task | Command |
|---|---|
| Start | `python start_shell.py up` |
| Stop | `python start_shell.py down` |
| After a change in `project/` | `python start_shell.py restart shell` |
| See what the shell is doing | `python start_shell.py logs -f shell` |
| Is every service healthy? | `python start_shell.py ps`: the status says `(healthy)`, or `(unhealthy)` with its logs to look at |
| How many took part, export the data | http://127.0.0.1:8081/researcher/ (see [the researcher dashboard](#the-researcher-dashboard-and-the-data-export)) |
| An account for someone, on both dashboards | `python start_shell.py researcher` |
| Back up everything, encrypted and checked | `python start_shell.py backup` (see [Backups](#backups)) |
| Take in new code, safely | `python start_shell.py update` (see [Updates](#updates)) |
| A participant asks to be removed | the researcher dashboard, "Remove a participant" (see [Removing data](#removing-data)) |

## Developing

| Task | Command |
|---|---|
| Run the tests | `python start_shell.py exec shell pytest` |
| After a CSS change | `python start_shell.py exec shell python manage.py collectstatic --noinput` |
| After a model change | `python start_shell.py exec shell python manage.py makemigrations`, then commit the new migration |
| After changing `shell/requirements.in` | `python start_shell.py lock`, then `up`, then commit `shell/requirements.lock` |

## Your study, start to finish

A study has two halves, linked by one id. **The project folder** (`project/`) holds the study's settings: texts, age range, questionnaire thresholds, theme. **The Tilbot project** holds the conversation: the flowchart, drawn in Tilbot's editor in the browser. Both dashboards are on the researcher port, http://127.0.0.1:8081, and one name and password opens both.

1. **Make your account,** once per person.
   ```
   python start_shell.py researcher
   ```
   It asks for a name and a password of at least 12 characters, twice. You should see **"Ready. Log in with <name> on both dashboards"**. The same name and password now open our researcher dashboard and Tilbot's dashboard. Run it again with the same name to set a new password for our dashboard; Tilbot's password is changed under "Your account" in Tilbot's dashboard.
2. **Fill in the project folder.** Edit `project/project.toml` (name, language, texts, ages, genders, time zone, transcripts), `project/questionnaire.toml` (each item's scale, button words and threshold), `project/feedback.toml` (the results: scales, thresholds, texts; delete it for a study without results) and `project/knowledge.xlsx` (the questions participants may ask, with their answers; leave it out for a study without questions), then `python start_shell.py up`. Every line has a comment saying what it does; [architecture.md](architecture.md#phase-3-questions) explains the columns of the Excel file.
3. **Make the Tilbot project.** Open http://127.0.0.1:8081/dashboard, log in with your name and password, and click "+ New project".
4. **Draw the flowchart.** The pencil icon opens the editor. It starts with a status check, each question gets a save block whose `item` matches an id in `questionnaire.toml`, the end opens the results, and then questions can follow; [architecture.md](architecture.md#phase-1-in-tilbots-editor) shows how. Save with the save icon; "Project saved!" confirms it. To start from a working example instead, click the project's icon in the Import column and pick `project-example/tilbot/example.tilbot`.
5. **Link the two.** Switch the project to running in Tilbot's dashboard. The globe icon opens `/?project=<id>`: copy that id into `[tilbot] project_id` in `project/project.toml`, then `python start_shell.py restart shell`.
6. **Test it.** Sign up at https://localhost: you should see the bot's first message inside the page. Answer the questions: at the end the results open beside the chat (over it on a phone). Sign out and in again: the bot welcomes you back and skips the questions. With a knowledge base, type a question from it in your own words: you should get its answer. Right after `up`, the first questions may fail with "something went wrong" while the language model downloads; `python start_shell.py logs vector-similarity-intent` shows when it is ready. Then open the [researcher dashboard](#the-researcher-dashboard-and-the-data-export): you should see one participant more, and their answers.
7. **Run the study.** Make a backup first (`python start_shell.py backup`), and regularly while it runs. Participants sign up and chat; you follow the counts in the researcher dashboard and export at the end.
8. **Keep the conversation as a file too.** A backup holds the flowchart, but to move it to another computer or a server, the up-arrow icon in Tilbot's dashboard downloads the project as one `.tilbot` file; keep it in `project/tilbot/` and import it there.

Good to know:

- **Saving changes the running chat** for every new conversation. Data tables and avatars are stored the moment you add them. While a study runs, work on a copy: a new project with the exported file imported into it.
- **The editor has no "Load project" button in the browser.** Use Import in the dashboard.
- **Only the Tilbot project in `project.toml` reaches participants.** Another running project gets nobody through the shell, and can't save anything for anyone. The bin icon hides a project in Tilbot's dashboard; never hide the one in `project.toml`.
- **Transcripts** are stored by the shell, encrypted, when `project/project.toml` has `transcripts.enabled = true` (the default). Tilbot's own logging is off and its switch hidden; nothing is ever written in plain text.
- **Tilbot's `admin` account** only exists to make Tilbot accounts, and `start_shell.py researcher` uses it for you; its password is `TILBOT_ADMIN_PASSWORD` in `.env`. Don't change that password in Tilbot's dashboard, or the command can no longer make accounts.
- **Someone who should only build the flowchart,** a student assistant for example: log in to Tilbot's dashboard as `admin` and make their Tilbot account there by hand. They then can't see the participants' data.

## The researcher dashboard and the data export

The shell's own dashboard shows how the study is going and hands out the data: http://127.0.0.1:8081/researcher/ (exactly this address; `localhost:8081` is refused). Log in with the account from [step 1 above](#your-study-start-to-finish). You should see the number of participants, answers and transcript lines, the time of the last answer, and a link to Tilbot's dashboard.

**System.** "System: status and logs" draws every component and who calls whom: green when it runs well, orange while it starts, red when it is down, dashed when the study doesn't use it. Below: what Docker says about each, its CPU and memory, the answers, chat lines and questions of the last hour, and each component's last 40 log lines. It is read from Docker each time you open or refresh the page. The first thing to look at when something seems wrong.

**Export.** "Export the data" offers two choices, each explained on the page:
- **Without codes:** participants are numbered 1, 2, 3 … in order of sign-up. The files can be joined to each other, but not traced to a person. Use this for analysis.
- **With codes:** every row carries the participant's 4-character code. Only when the study needs it, for example for a removal request; the file is personal data.

Both give one zip with `participants.csv`, `answers.csv`, `scores.csv` (each scale of the results, from the latest answers, as the participant saw it), `questions.csv` (each question asked and the knowledge base entry it matched; its text only when transcripts are kept) and `transcripts.csv`, decrypted, with times in the study's time zone. **The export is the one place where data leaves the database unencrypted:** store it where the study's data management plan says, never in the repository folder (`.gitignore` skips zips as a safety net).

## Removing data

Deleting study data is never automatic: it is always a researcher's decision, with what the study's data management plan says.

- **One participant asks to be removed:** in the researcher dashboard, "Remove a participant". Enter their code: the page shows what will be deleted (answers, questions, transcript lines), and deletes it all, with their sign-in sessions, once you confirm.
- **The study is over:** after the final export and backup, `python start_shell.py erase` deletes every participant with all their data, the sign-in attempts and all sessions. It asks for the study's name as written in `project.toml`. Researcher accounts and Tilbot's projects stay.
- **Backups made before still hold the data.** Delete or keep them as the data management plan says.

Some data goes by itself: sign-in attempts after 15 minutes, expired sign-in sessions at every start of the shell and every backup, and container logs beyond 3 files of 10 MB per service.

## On a server

Not described yet. `compose.yaml` is written for it (`SHELL_ENV=production`, a real `SHELL_HOST` and `BOT_HOST`, ports 80 and 443 open so Caddy can get certificates), but it has not been done once, and Tilbot's dashboard is not reachable there (known gap). The first deployment will write this section.

## Keys

`FIELD_ENCRYPTION_KEY` encrypts every answer and transcript line. **Without it the data cannot be read, by anyone.**

- **Keep two copies outside this computer,** for example in two password managers held by two people.
- **Never change the key** once real data is stored. Changing it needs a re-encryption step that doesn't exist yet.
- **Every backup is encrypted with this key,** so restoring one needs the key that was in use when it was made.
- **New secrets:** empty their values in `.env` and run `up`, which fills them in again. It refuses to replace `FIELD_ENCRYPTION_KEY` or `POSTGRES_PASSWORD` while a database exists, because the new value would lock out what is stored.
- **Start over with all-new secrets,** for a test setup only, because it deletes every stored answer, account and Tilbot project:
  ```
  python start_shell.py down -v
  ```
  Then delete `.env` and run `python start_shell.py up`. Caddy's root certificate is kept, so there is nothing to trust again.

## Backups

```
python start_shell.py backup
```

This makes one folder in `backups/`, named after the date and time, with the whole study in it:

| File | Holds |
|---|---|
| `shell.dump.enc` | the shell's database: participants, answers, questions, transcripts, researcher accounts |
| `tilbot.archive.enc` | Tilbot's database: its accounts, projects and flowcharts |
| `tilbot-files.tar.gz.enc` | Tilbot's files: data tables and avatars |
| `project.zip.enc` | the project folder |
| `README.txt` | what the folder holds, and how to restore it |

You should see "Checked: the database restores (… participants)" and "Backup made". Before saying so, `backup` restores the database into a scratch database and reads every other part back: a backup only counts once a restore has worked. If that check fails, the folder is renamed `…-FAILED`.

- **Every file is encrypted with `FIELD_ENCRYPTION_KEY`,** so a backup can't be read without the key, and the key is never in the backup. The data goes from the containers through memory into the encrypted file; it is never written to disk unencrypted.
- **Keep a copy elsewhere:** `backups/` is on the same computer as the study, and git skips it. To write straight to another place: `python start_shell.py backup D:\backups\2026-10-19`.
- **Make one** before an update (`update` does it for you), before the study starts, and regularly while it runs. `python start_shell.py backup --keep 14` deletes all but the 14 newest backups in `backups/` afterwards, for a daily schedule. Scheduling it comes with running on a server.

**Restore one:**
```
python start_shell.py restore backups/2026-10-19-143000
```
It asks you to type the backup's name, checks the backup, and only then replaces the shell's database, Tilbot's database and files, and `project/`. Your `project/` from before is kept beside it, as `project-before-restore-<date>`. The key in `.env` must be the one the backup was made with.

## Updates

```
python start_shell.py updates
```

This compares each pinned commit with upstream and changes nothing. To take in new code, from `git pull` or a newer commit in `components.toml` (change `commit`, `pinned_on` and `note` there):

```
python start_shell.py update
```

It makes a backup, rebuilds everything and, in development, runs the tests. If something fails, it stops and says which backup takes you back: return to the code you had (`git log` shows it), then `restore` that backup. If a Tilbot patch no longer applies, the build stops; regenerate the patch against the new commit.

Python packages take patch updates only: run `python start_shell.py lock` and rebuild. A minor or major upgrade (Django 5.2 to 6.x, say) is a decision: write it in `docs/decisions.md` first.
