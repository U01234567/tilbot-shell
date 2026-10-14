"""Start and look after tilbot-shell. Needs Python 3.11+ and Docker; standard library only.

    python start_shell.py up         create /project/ if needed, then build and start everything
    python start_shell.py updates    compare the pinned commits in components.toml with upstream
    python start_shell.py lock       regenerate shell/requirements.lock (exact versions with hashes)
    python start_shell.py secrets    print fresh values for the secrets in .env
    python start_shell.py <anything else>
                                     passed to `docker compose` with the right files and pins,
                                     for example: logs -f shell, down, exec shell pytest
"""

import base64
import os
import secrets
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PINNED = ("tilbot", "vector-similarity-intent")


def shell_env() -> str:
    """Return SHELL_ENV from .env: "development" or "production"."""
    if not (ROOT / ".env").exists():
        raise ValueError("there is no .env yet: copy .env.example to .env and fill it in")
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


def compose(*args: str) -> None:
    command = ["docker", "compose", *compose_files(shell_env()), *args]
    subprocess.run(command, cwd=ROOT, env={**os.environ, **pinned_env(read_components())}, check=True)


def up() -> None:
    if not (ROOT / "project").exists():
        shutil.copytree(ROOT / "project-example", ROOT / "project")
        print("Created project/ from project-example/. Replace the example content before real use.")
    compose("up", "--build", "--detach")


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
    subprocess.run(
        [
            "docker", "run", "--rm", "-v", f"{ROOT / 'shell'}:/work", "-w", "/work", "python:3.12-slim",
            "sh", "-c", "pip install --quiet pip-tools && "
            "pip-compile --quiet --generate-hashes --output-file requirements.lock requirements.in",
        ],
        check=True,
    )


def print_secrets() -> None:
    for name in ("DJANGO_SECRET_KEY", "BRIDGE_SECRET", "TILBOT_SESSION_SECRET", "POSTGRES_PASSWORD"):
        print(f"{name}={secrets.token_urlsafe(48)}")
    # The same format as cryptography's Fernet.generate_key(): 32 random bytes, URL-safe base64.
    print(f"FIELD_ENCRYPTION_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}")
    print("\nBack up FIELD_ENCRYPTION_KEY apart from the database (docs/operations.md).")


COMMANDS = {"up": up, "updates": updates, "lock": lock, "secrets": print_secrets}


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
