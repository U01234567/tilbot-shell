"""Start and look after tilbot-shell. Needs Python 3.11+ and Docker; standard library only.

    python start_shell.py up         create .env and project/ if needed, then build and start everything
    python start_shell.py trust      make this computer trust https://localhost and https://bot.localhost
    python start_shell.py researcher one name and password for both dashboards on http://127.0.0.1:8081
    python start_shell.py backup [folder] [--keep N]
                                     an encrypted backup of the whole study, checked by restoring it;
                                     --keep N then deletes all but the N newest backups in backups/
    python start_shell.py restore <folder>
                                     replace the study's data, Tilbot's projects and project/ with a backup
    python start_shell.py updates    compare the pinned commits in components.toml with upstream
    python start_shell.py update     after new code or a new pin: a backup, then rebuild, then the tests
    python start_shell.py erase      delete every participant's data, at the end of a study
    python start_shell.py lock       regenerate shell/requirements.lock (exact versions with hashes)
    python start_shell.py <anything else>
                                     passed to `docker compose` with the right files and pins,
                                     for example: logs -f shell, down, exec shell pytest
"""

import argparse
import base64
import io
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PINNED = ("tilbot", "vector-similarity-intent")
SECRETS = (
    "DJANGO_SECRET_KEY", "BRIDGE_SECRET", "TILBOT_SESSION_SECRET", "TILBOT_ADMIN_PASSWORD",
    "POSTGRES_PASSWORD", "FIELD_ENCRYPTION_KEY",
)
# A new value for these locks out what is already stored, so they are never replaced once a database exists.
DATA_SECRETS = {"POSTGRES_PASSWORD", "FIELD_ENCRYPTION_KEY"}
DATABASE_VOLUME = "tilbot-shell_db"  # the "db" volume of compose project "tilbot-shell"
CA_VOLUME = "tilbot-shell-caddy-ca"  # external in compose.yaml, so `down -v` keeps it
# A study with a knowledge base answers questions (phase 3): only then does vector-similarity-intent run.
KNOWLEDGE = ROOT / "project" / "knowledge.xlsx"
# Backups: one folder each, every file encrypted with FIELD_ENCRYPTION_KEY (shell's backup_cipher).
BACKUPS = ROOT / "backups"  # the default place, kept out of git; copy backups elsewhere too
BACKUP_FILES = ("shell.dump", "tilbot.archive", "tilbot-files.tar.gz", "project.zip")
RESTORE_CHECK = "restore_check"  # a scratch database: every backup is restored into it once, then dropped
BACKUP_README = """A backup of the study "{study}", made {when}. It restored completely when it was made.

shell.dump.enc           the shell's database: participants, answers, questions, transcripts, researcher accounts
tilbot.archive.enc       Tilbot's database: its accounts, projects and flowcharts
tilbot-files.tar.gz.enc  Tilbot's files: data tables and avatars
project.zip.enc          the project folder

Every file is encrypted with FIELD_ENCRYPTION_KEY from .env. That key is not in this folder: keep it apart.
To restore: python start_shell.py restore <this folder>
"""
STARTUP_SECONDS = 15  # long enough for a service that fails at start-up to have stopped or restarted

# Where start_shell.py can't trust a certificate without your password, it shows the command instead.
TRUST_COMMANDS = {
    "Darwin": "sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt",
    "Linux": 'certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n caddy-local -i caddy-root.crt   (needs libnss3-tools)',
}


def env_values(env_text: str) -> dict[str, str]:
    """Return NAME: value for every NAME=value line, without comments; a bare NAME= gives ""."""
    values = {}
    for line in env_text.splitlines():
        name, is_assignment, value = line.partition("=")
        if is_assignment and not name.startswith("#"):
            values[name] = value.split("#")[0].strip()
    return values


def shell_env() -> str:
    """Return SHELL_ENV from .env: "development" or "production"."""
    if not (ROOT / ".env").exists():
        raise ValueError("there is no .env yet: run python start_shell.py up")
    values = env_values((ROOT / ".env").read_text(encoding="utf-8"))
    if "SHELL_ENV" not in values:
        raise ValueError("SHELL_ENV is missing from .env (see .env.example)")
    return values["SHELL_ENV"]


def compose_files(env: str) -> list[str]:
    files = ["-f", "compose.yaml"]
    if env == "development":
        files += ["-f", "compose.dev.yaml"]
    return files


def pinned_env(components: dict) -> dict[str, str]:
    """Return TILBOT_REPO, TILBOT_COMMIT, VECTOR_SIMILARITY_INTENT_REPO and ..._COMMIT for docker compose."""
    unpinned = [name for name in PINNED if len(components[name]["commit"]) != 40]
    if unpinned:
        raise ValueError(f"components.toml: give {', '.join(unpinned)} a full 40-character commit hash")
    env = {}
    for name in PINNED:
        prefix = name.upper().replace("-", "_")  # vector-similarity-intent -> VECTOR_SIMILARITY_INTENT
        env[f"{prefix}_REPO"] = components[name]["repo"]
        env[f"{prefix}_COMMIT"] = components[name]["commit"]
    return env


def read_components() -> dict:
    return tomllib.loads((ROOT / "components.toml").read_text(encoding="utf-8"))


def fresh_secret(name: str) -> str:
    if name == "FIELD_ENCRYPTION_KEY":
        # The format of cryptography's Fernet.generate_key(): 32 random bytes, URL-safe base64.
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    return secrets.token_urlsafe(48)


def with_secrets(env_text: str) -> tuple[str, list[str]]:
    """Return the .env text with every empty or missing secret filled in, and the names of those secrets."""
    values = env_values(env_text)
    filled = [name for name in SECRETS if not values.get(name)]
    new_lines = {name: f"{name}={fresh_secret(name)}" for name in filled}
    lines = [new_lines.get(line.partition("=")[0], line) for line in env_text.splitlines()]
    lines += [new_lines[name] for name in filled if name not in values]  # a .env from before the secret existed
    return "\n".join(lines) + "\n", filled


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise ValueError("Docker is not installed (see docs/operations.md)")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        raise ValueError("Docker is not running: start Docker Desktop, wait until it says it is running, then try again")


def ensure_env() -> None:
    """Create .env from .env.example if there is none, and fill in every empty secret."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copyfile(ROOT / ".env.example", env_file)
        print("Created .env from .env.example.")
    text, filled = with_secrets(env_file.read_text(encoding="utf-8"))
    if not filled:
        return
    locked_out = DATA_SECRETS.intersection(filled)
    database = subprocess.run(["docker", "volume", "inspect", DATABASE_VOLUME], capture_output=True)
    if locked_out and database.returncode == 0:
        raise ValueError(
            f"{' and '.join(sorted(locked_out))} is empty in .env, but the database was made with the old value. "
            "Put the old value back from your backup. Only if nothing stored matters: python start_shell.py down -v"
        )
    env_file.write_text(text, encoding="utf-8")
    print(f"Filled in new values in .env for {', '.join(filled)}.")
    if "FIELD_ENCRYPTION_KEY" in filled:
        print("Back up FIELD_ENCRYPTION_KEY from .env now, apart from the database: without it, stored answers can't be read.")


def compose_command(*args: str) -> tuple[list[str], dict[str, str]]:
    """The docker compose command line, and its environment with the pinned commits."""
    profiles = ["--profile", "phase3"] if KNOWLEDGE.exists() else []
    command = ["docker", "compose", *compose_files(shell_env()), *profiles, *args]
    return command, {**os.environ, **pinned_env(read_components())}


def compose(*args: str, capture: bool = False) -> str:
    require_docker()
    command, env = compose_command(*args)
    result = subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=capture, text=True)
    return result.stdout


def compose_bytes(*args: str, data: bytes = b"") -> bytes:
    """docker compose with bytes in and out. No terminal touches them, so a dump arrives byte for byte."""
    require_docker()
    command, env = compose_command(*args)
    result = subprocess.run(command, cwd=ROOT, env=env, input=data, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode(errors="replace"))
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.stdout


def up() -> list[str]:
    """Build and start everything; return the services that didn't stay up."""
    require_docker()  # before ensure_env, which asks Docker about the database
    ensure_env()
    if not (ROOT / "shell" / "requirements.lock").exists():
        raise ValueError("shell/requirements.lock is missing: run python start_shell.py lock first")
    if not (ROOT / "project").exists():
        shutil.copytree(ROOT / "project-example", ROOT / "project")
        print("Created project/ from project-example/. Replace the example content before real use.")
    if not (ROOT / "project" / "project.toml").exists():
        raise ValueError("project/ has no project.toml: put it back from your backup, or move project/ away to start again from project-example/")
    if KNOWLEDGE.exists():
        print("project/knowledge.xlsx found: phase 3 is on. Its first start downloads a language model (about 500 MB).")
    subprocess.run(["docker", "volume", "create", CA_VOLUME], capture_output=True, check=True)
    compose("up", "--build", "--detach")
    # Docker can't see a changed Caddyfile, so Caddy is told to read it again; running requests go on.
    compose("exec", "caddy", "caddy", "reload", "--config", "/etc/caddy/Caddyfile")

    print(f"Checking that everything stays up ({STARTUP_SECONDS} seconds)...")
    time.sleep(STARTUP_SECONDS)
    stopped = compose(
        "ps", "--all", "--services", "--status", "exited", "--status", "restarting", "--status", "dead", capture=True
    ).split()
    for service in stopped:
        print(f"Not running: {service}. See why with: python start_shell.py logs {service}")
    if not stopped:
        print("Everything is running. Open https://localhost (if the browser warns: python start_shell.py trust).")
    return stopped


def trust() -> None:
    """Make this computer trust the certificates Caddy makes for localhost and bot.localhost."""
    compose("cp", "caddy:/data/caddy/pki/authorities/local/root.crt", "caddy-root.crt")
    system = platform.system()
    if system == "Windows":
        subprocess.run(["certutil", "-user", "-addstore", "Root", "caddy-root.crt"], cwd=ROOT, check=True)
        print("Trusted. Restart your browser.")
        return
    command = TRUST_COMMANDS.get(system, "import caddy-root.crt as a trusted root certificate in your browser")
    print(f"Saved caddy-root.crt. To trust it, run:\n  {command}\nThen restart your browser.")


def researcher() -> None:
    """One name and password for both dashboards: ours and Tilbot's (shell/monitor/management/commands)."""
    compose("exec", "shell", "python", "manage.py", "researcher")


def database() -> tuple[str, str]:
    """The shell's database user and name, from .env."""
    values = env_values((ROOT / ".env").read_text(encoding="utf-8"))
    return values["POSTGRES_USER"], values["POSTGRES_DB"]


def study_name() -> str:
    return tomllib.loads((ROOT / "project" / "project.toml").read_text(encoding="utf-8"))["name"]


def cipher(direction: str, data: bytes) -> bytes:
    """Encrypt or decrypt with FIELD_ENCRYPTION_KEY, inside the shell's container (records/management/commands)."""
    return compose_bytes("exec", "-T", "shell", "python", "manage.py", "backup_cipher", direction, data=data)


def zip_folder(folder: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(folder))
    return buffer.getvalue()


def take_backup() -> dict[str, bytes]:
    """Every part of the study's state, as bytes in memory: nothing unencrypted is written to disk."""
    user, name = database()
    return {
        "shell.dump": compose_bytes("exec", "-T", "db", "pg_dump", "-U", user, "-Fc", name),
        "tilbot.archive": compose_bytes("exec", "-T", "mongo", "mongodump", "--db", "tilbot", "--archive", "--gzip"),
        "tilbot-files.tar.gz": compose_bytes("exec", "-T", "tilbot-backend", "tar", "-czf", "-", "projects", "proj_pub"),
        "project.zip": zip_folder(ROOT / "project"),
    }


def read_backup(folder: Path) -> dict[str, bytes]:
    return {file: cipher("decrypt", (folder / f"{file}.enc").read_bytes()) for file in BACKUP_FILES}


def check_backup(parts: dict[str, bytes]) -> None:
    """Restore every part somewhere harmless, so a backup that can't be restored is noticed now."""
    user, _ = database()
    db = ("exec", "-T", "db")
    compose_bytes(*db, "dropdb", "-U", user, "--if-exists", RESTORE_CHECK)
    compose_bytes(*db, "createdb", "-U", user, RESTORE_CHECK)
    try:
        compose_bytes(*db, "pg_restore", "-U", user, "--no-owner", "--exit-on-error", "-d", RESTORE_CHECK, data=parts["shell.dump"])
        count = compose_bytes(*db, "psql", "-U", user, "-d", RESTORE_CHECK, "-tAc", "select count(*) from accounts_participant")
    finally:
        compose_bytes(*db, "dropdb", "-U", user, "--if-exists", RESTORE_CHECK)
    compose_bytes("exec", "-T", "mongo", "mongorestore", "--archive", "--gzip", "--dryRun", data=parts["tilbot.archive"])
    tarfile.open(fileobj=io.BytesIO(parts["tilbot-files.tar.gz"]), mode="r:gz").getnames()  # reads it to the end
    if zipfile.ZipFile(io.BytesIO(parts["project.zip"])).testzip() is not None:
        raise ValueError("project.zip in the backup is damaged")
    print(f"Checked: the database restores ({int(count)} participants), and Tilbot's data and project/ can be read.")


def backup(*args: str) -> Path:
    """Make an encrypted backup of the whole study in a new folder, and check it by restoring it."""
    parser = argparse.ArgumentParser(prog="python start_shell.py backup")
    parser.add_argument("folder", nargs="?", default="", help="where to put it; default: backups/<date and time>")
    parser.add_argument("--keep", type=int, default=0, help="afterwards, keep only this many newest backups in backups/")
    options = parser.parse_args(args)
    if options.keep < 0:
        raise ValueError("--keep needs a number of backups, 1 or more")
    target = Path(options.folder) if options.folder else BACKUPS / time.strftime("%Y-%m-%d-%H%M%S")
    if target.exists():
        raise ValueError(f"{target} exists already: give another folder")
    compose("exec", "shell", "python", "manage.py", "clearsessions")  # expired sessions don't go into a backup
    print("Making the backup...")
    parts = take_backup()
    target.mkdir(parents=True)
    for file, data in parts.items():
        (target / f"{file}.enc").write_bytes(cipher("encrypt", data))
    try:
        check_backup(read_backup(target))  # the files as written, decrypted again: the real test
    except (subprocess.CalledProcessError, ValueError, tarfile.TarError, zipfile.BadZipFile):
        failed = target.with_name(f"{target.name}-FAILED")
        target.rename(failed)
        print(f"This backup could not be restored, so it is renamed {failed.name}: don't rely on it.")
        raise
    (target / "README.txt").write_text(BACKUP_README.format(study=study_name(), when=time.strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    print(f"Backup made: {target}. Keep a copy elsewhere too, and FIELD_ENCRYPTION_KEY apart from it.")
    if options.keep:
        keep_newest(options.keep)
    return target


def keep_newest(keep: int) -> None:
    """Delete all but the newest complete backups in backups/ (complete: README.txt, written after the check)."""
    complete = sorted((folder for folder in BACKUPS.iterdir() if (folder / "README.txt").exists()),
                      key=lambda folder: (folder / "README.txt").stat().st_mtime)
    for old in complete[:-keep]:
        shutil.rmtree(old)
        print(f"Deleted the older backup {old.name} (--keep {keep}).")


def restore(folder: str = "") -> None:
    """Replace the study's data, Tilbot's accounts and projects, and project/ with a backup."""
    if not folder:
        raise ValueError("say which backup: python start_shell.py restore backups/<its name>")
    source = Path(folder)
    print(f"This replaces every participant's data, Tilbot's accounts and projects, and project/ with the backup {source.name}.")
    print("project/ as it is now is kept beside it, as project-before-restore-<date>.")
    if input(f"Type {source.name} to go on: ").strip() != source.name:
        raise ValueError("Nothing restored: that wasn't the backup's name.")
    parts = read_backup(source)
    check_backup(parts)  # before anything is replaced
    user, name = database()
    db = ("exec", "-T", "db")
    compose("stop", "shell")
    compose_bytes(*db, "dropdb", "-U", user, "--force", name)  # a fresh database: no table from later code stays behind
    compose_bytes(*db, "createdb", "-U", user, name)
    compose_bytes(*db, "pg_restore", "-U", user, "--no-owner", "--exit-on-error", "-d", name, data=parts["shell.dump"])
    compose_bytes("exec", "-T", "mongo", "mongorestore", "--archive", "--gzip", "--drop", data=parts["tilbot.archive"])
    compose_bytes(
        "exec", "-T", "tilbot-backend", "sh", "-c", "rm -rf projects/* proj_pub/* && tar -xzf -",
        data=parts["tilbot-files.tar.gz"],
    )
    aside = ROOT / f"project-before-restore-{time.strftime('%Y-%m-%d-%H%M%S')}"
    if (ROOT / "project").exists():
        (ROOT / "project").rename(aside)
    zipfile.ZipFile(io.BytesIO(parts["project.zip"])).extractall(ROOT / "project")
    compose("restart", "tilbot-backend")
    up()
    print(f"Restored {source.name}. project/ from before the restore is in {aside.name}.")


def update() -> None:
    """After new code (git pull) or a new pin in components.toml: a backup, then rebuild, then the tests."""
    folder = backup()
    try:
        if up():
            raise ValueError("not everything stayed up after the rebuild")
        if shell_env() == "development":  # the tests come with the development setup only
            compose("exec", "shell", "pytest")
    except (subprocess.CalledProcessError, ValueError):
        print(f"The update failed. To go back: return to the code you had, then python start_shell.py restore {folder}")
        raise
    print(f"Updated and checked. The backup from just before is {folder}.")


def erase() -> None:
    """Delete every participant's data, at the end of a study (shell/monitor/removal.py)."""
    print(f'This deletes every participant of "{study_name()}" with their answers, questions and transcripts.')
    print("Researcher accounts and Tilbot's projects stay. Backups made earlier still hold the data.")
    typed = input("Type the study's name to go on: ").strip()
    compose("exec", "shell", "python", "manage.py", "erase", typed)  # the shell refuses a wrong name


def updates() -> None:
    components = read_components()
    for name in PINNED:
        pinned = components[name]["commit"]
        result = subprocess.run(
            ["git", "ls-remote", components[name]["repo"], "HEAD"],
            capture_output=True, text=True, check=True,
        )
        latest = result.stdout.split()[0]
        status = "up to date" if latest == pinned else f"upstream is at {latest[:7]}"
        print(f"{name}: pinned {pinned[:7]}, {status}")


def lock() -> None:
    """Pin every runtime package to an exact version with hashes, inside a Python container."""
    require_docker()
    subprocess.run(
        [
            "docker", "run", "--rm", "-v", f"{ROOT / 'shell'}:/work", "-w", "/work", "python:3.12-slim",
            "sh", "-c", "pip install --quiet pip-tools && "
            "pip-compile --quiet --generate-hashes --output-file requirements.lock requirements.in",
        ],
        check=True,
    )


COMMANDS = {
    "up": up, "trust": trust, "researcher": researcher, "backup": backup, "restore": restore,
    "updates": updates, "update": update, "erase": erase, "lock": lock,
}


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    try:
        if args[0] in COMMANDS:
            COMMANDS[args[0]](*args[1:])
        else:
            compose(*args)
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
    except KeyError as error:
        sys.exit(f"start_shell.py: components.toml lacks {error}")
    except (FileNotFoundError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        sys.exit(f"start_shell.py: {error}")


if __name__ == "__main__":
    main()
