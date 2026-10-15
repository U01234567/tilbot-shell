"""Start and look after tilbot-shell. Needs Python 3.11+ and Docker; standard library only.

    python start_shell.py up         create .env and /project/ if needed, then build and start everything
    python start_shell.py trust      make this computer trust https://localhost and https://bot.localhost
    python start_shell.py updates    compare the pinned commits in components.toml with upstream
    python start_shell.py lock       regenerate shell/requirements.lock (exact versions with hashes)
    python start_shell.py <anything else>
                                     passed to `docker compose` with the right files and pins,
                                     for example: logs -f shell, down, exec shell pytest
"""

import base64
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PINNED = ("tilbot", "vector-similarity-intent")
SECRETS = ("DJANGO_SECRET_KEY", "BRIDGE_SECRET", "TILBOT_SESSION_SECRET", "POSTGRES_PASSWORD", "FIELD_ENCRYPTION_KEY")
# A new value for these locks out what is already stored, so they are never replaced once a database exists.
DATA_SECRETS = {"POSTGRES_PASSWORD", "FIELD_ENCRYPTION_KEY"}
DATABASE_VOLUME = "tilbot-shell_db"  # the "db" volume of compose project "tilbot-shell"
STARTUP_SECONDS = 15  # long enough for a service that fails at start-up to have stopped or restarted

# Where start_shell.py can't trust a certificate without your password, it shows the command instead.
TRUST_COMMANDS = {
    "Darwin": "sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt",
    "Linux": 'certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n caddy-local -i caddy-root.crt   (needs libnss3-tools)',
}


def shell_env() -> str:
    """Return SHELL_ENV from .env: "development" or "production"."""
    if not (ROOT / ".env").exists():
        raise ValueError("there is no .env yet: run python start_shell.py up")
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("SHELL_ENV="):
            return line.removeprefix("SHELL_ENV=").split("#")[0].strip()
    raise ValueError("SHELL_ENV is missing from .env (see .env.example)")


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
    return {
        f"{name.upper().replace('-', '_')}_{key.upper()}": components[name][key]
        for name in PINNED
        for key in ("repo", "commit")
    }


def read_components() -> dict:
    return tomllib.loads((ROOT / "components.toml").read_text(encoding="utf-8"))


def fresh_secret(name: str) -> str:
    if name == "FIELD_ENCRYPTION_KEY":
        # The format of cryptography's Fernet.generate_key(): 32 random bytes, URL-safe base64.
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    return secrets.token_urlsafe(48)


def with_secrets(env_text: str) -> tuple[str, list[str]]:
    """Return the .env text with every empty secret filled in, and the names of those secrets."""
    lines, filled = [], []
    for line in env_text.splitlines():
        name, _, value = line.partition("=")
        if name in SECRETS and not value.split("#")[0].strip():
            line = f"{name}={fresh_secret(name)}"
            filled.append(name)
        lines.append(line)
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


def compose(*args: str, capture: bool = False) -> str:
    require_docker()
    command = ["docker", "compose", *compose_files(shell_env()), *args]
    env = {**os.environ, **pinned_env(read_components())}
    result = subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=capture, text=True)
    return result.stdout


def up() -> None:
    require_docker()
    ensure_env()
    if not (ROOT / "shell" / "requirements.lock").exists():
        raise ValueError("shell/requirements.lock is missing: run python start_shell.py lock first")
    if not (ROOT / "project").exists():
        shutil.copytree(ROOT / "project-example", ROOT / "project")
        print("Created project/ from project-example/. Replace the example content before real use.")
    compose("up", "--build", "--detach")

    print(f"Checking that everything stays up ({STARTUP_SECONDS} seconds)...")
    time.sleep(STARTUP_SECONDS)
    stopped = compose(
        "ps", "--all", "--services", "--status", "exited", "--status", "restarting", "--status", "dead", capture=True
    ).split()
    for service in stopped:
        print(f"Not running: {service}. See why with: python start_shell.py logs {service}")
    if not stopped:
        print("Everything is running. Open https://localhost (if the browser warns: python start_shell.py trust).")


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


COMMANDS = {"up": up, "trust": trust, "updates": updates, "lock": lock}


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    try:
        if args[0] in COMMANDS:
            COMMANDS[args[0]]()
        else:
            compose(*args)
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
    except (FileNotFoundError, KeyError, ValueError) as error:
        sys.exit(f"start_shell.py: {error}")


if __name__ == "__main__":
    main()
