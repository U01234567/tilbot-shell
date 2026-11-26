"""python manage.py model: have Ollama fetch narrative.toml's model and delete every other model it holds.

python start_shell.py up runs this for a study with narrative.toml and server = "ollama", so changing the model is
one line and an up: the new one is fetched once, and the old one is removed from Ollama's volume. Nothing to do
for a study without narrative.toml or with a model by API key.
"""

import json
import time
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand

WAIT = 60  # seconds Ollama may take to start


class Command(BaseCommand):
    help = "Fetch narrative.toml's model in Ollama and delete every other model."

    def handle(self, **options):
        narrative = settings.STUDY.narrative
        if narrative is None or narrative.server != "ollama":
            return
        wanted = tagged(narrative.model)
        held = wait_for_models(narrative.url)
        if wanted not in held:
            self.stdout.write(f"Fetching the language model {wanted} (only this once; it can take minutes)...")
            call(narrative.url, "POST", "/api/pull", {"model": wanted, "stream": False}, timeout=None)
        for name in held - {wanted}:
            call(narrative.url, "DELETE", "/api/delete", {"model": name})
            self.stdout.write(f"Deleted the language model {name}: narrative.toml asks for {wanted}.")
        self.stdout.write(f"Language model ready: {wanted}.")


def tagged(model: str) -> str:
    """Ollama's full name for a model: "gemma3" is "gemma3:latest"."""
    return model if ":" in model else f"{model}:latest"


def wait_for_models(url: str) -> set[str]:
    """The names of the models Ollama holds, waiting for Ollama to start."""
    for _ in range(WAIT):
        try:
            return {model["name"] for model in call(url, "GET", "/api/tags")["models"]}
        except OSError:
            time.sleep(1)
    raise OSError(f"Ollama doesn't answer at {url}: is it in project/compose.yaml? See python start_shell.py logs")


def call(url: str, method: str, path: str, body: dict | None = None, timeout: float | None = 10) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{url.rstrip('/')}{path}", data, {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read()
    return json.loads(text) if text else {}
