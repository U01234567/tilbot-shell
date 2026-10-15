# Operations

Setting up, running, deploying a Tilbot project, backups and updates.
Every command runs from the repository root. `start_shell.py` picks the right compose files and pinned commits; any command it doesn't know goes straight to `docker compose`.

## First-time setup

You need Docker (Docker Desktop on Windows or macOS) and Python 3.11 or newer.

1. **Check the pins.** `components.toml` already pins Tilbot and vector-similarity-intent to a commit. `python start_shell.py updates` shows whether upstream has moved on since.
2. **Make your `.env`.** Copy `.env.example` to `.env`, run `python start_shell.py secrets`, and paste the values into `.env`. Store `FIELD_ENCRYPTION_KEY` somewhere safe as well (see [Keys](#keys)).
3. **Pin the Python packages.** This writes `shell/requirements.lock`; commit it.
   ```
   python start_shell.py lock
   ```
4. **Start everything.** The first build takes a while. `/project/` is created from `project-example/` if it doesn't exist.
   ```
   python start_shell.py up
   ```
5. **Create the first database migrations.** Commit `shell/accounts/migrations/` and `shell/records/migrations/`.
   ```
   python start_shell.py exec shell python manage.py makemigrations accounts records
   python start_shell.py exec shell python manage.py migrate
   ```
6. **Open https://localhost.** Caddy makes its own local certificate, so the browser warns once. To trust it permanently:
   ```
   python start_shell.py exec caddy caddy trust
   ```

## Every day

| Task | Command |
|---|---|
| Start | `python start_shell.py up` |
| Stop | `python start_shell.py down` |
| Follow the shell's log | `python start_shell.py logs -f shell` |
| Run the tests | `python start_shell.py exec shell pytest` |
| After a CSS change | `python start_shell.py exec shell python manage.py collectstatic --noinput` |
| After a change in `/project/` | `python start_shell.py restart shell` |
| After a model change | `python start_shell.py exec shell python manage.py makemigrations`, then commit the new migration |

## Putting the Tilbot project online

The flowchart is made in Tilbot's editor, in the browser, and stored on the Tilbot server.

1. **Log in to the dashboard** at http://127.0.0.1:8081/login. The first visit creates `admin` / `admin`; change that password at once.
2. **Create a researcher account.** As `admin`, create a user, then log in as that user. Only users can own projects; the admin account can't.
3. **Create a project** with "+ New project".
4. **Draw the flowchart.** The pencil icon opens the editor. Save with the save icon in the editor's menu; "Project saved!" confirms it. How to build the questionnaire is in [architecture.md](architecture.md#phase-1-in-tilbots-editor).
5. **Switch it to running** in the dashboard.
6. **Connect it to the shell.** The globe icon opens `/?project=<id>`. Copy that id into `[tilbot] project_id` in `/project/project.toml`, then restart the shell.
7. **Test it.** Sign up at https://localhost and check that the chat appears.
8. **Back it up.** The up-arrow icon downloads the project as one `.tilbot` file; keep it in `/project/tilbot/`. Tilbot keeps its projects in a Docker volume, which `down -v` deletes. To move a project to another computer or a server, import that file there.

Good to know:

- **Saving changes the running chat** for every new conversation. Data tables and avatars are stored the moment you add them. While a study runs, work on a copy: a new project with the exported file imported into it.
- **The editor has no "Load project" button in the browser.** Use Import in the dashboard.
- **Leave "Logging enabled" off**, in the dashboard and in the editor's settings: transcripts already go to the shell, encrypted.

## Keys

`FIELD_ENCRYPTION_KEY` encrypts every answer and transcript line. **Without it the data cannot be read, by anyone.**

- **Keep two copies outside this computer,** for example in two password managers held by two people.
- **Never change the key** once real data is stored. Changing it needs a re-encryption step that doesn't exist yet.
- **Restoring a database backup also needs the key** that was in use when the backup was made.

## Backups

**Make one:**
```
python start_shell.py exec db pg_dump -U shell -Fc shell > backup-2026-10-12.dump
```

**Test it.** A backup only counts once a restore has worked:
```
python start_shell.py exec -T db createdb -U shell restore_test
python start_shell.py exec -T db pg_restore -U shell -d restore_test < backup-2026-10-12.dump
python start_shell.py exec db dropdb -U shell restore_test
```

Automating this, and a backup before every update, is still to be built.

## Updates

```
python start_shell.py updates
```

This compares each pinned commit with upstream and changes nothing. To move to a newer commit:

1. Make a backup.
2. Change `commit`, `pinned_on` and `note` in `components.toml`.
3. Run `python start_shell.py up`. If a patch no longer applies, the build stops there; regenerate the patch against the new commit.
4. Run the tests.

Python packages take patch updates only: run `python start_shell.py lock` and rebuild. A minor or major upgrade (Django 5.2 to 6.x, say) is a decision: write it in `docs/decisions.md` first.
