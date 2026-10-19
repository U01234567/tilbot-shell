"""The system page: which components run, how they are doing, who talks to whom, and their latest log lines.

Docker is read through docker-proxy (compose.yaml), which passes on only the three requests below:
the list of containers, and a container's resource use and log. It can't start, stop or change anything.
"""

import http.client
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

PROJECT = "tilbot-shell"  # the name in compose.yaml: Docker labels every container with it
LOG_LINES = 40

# Every box of the drawing: what it is, what it does, and where it sits (its top-left corner; each is 150 × 56).
# Every box but the browser is a service of compose.yaml.
COMPONENTS = {
    "browser": ("Participant", "a phone or computer, through the internet", (0, 128)),
    "caddy": ("Caddy", "web server: HTTPS, and the only way in", (190, 128)),
    "shell": ("Shell", "sign-up, chat page, results, these pages", (380, 28)),
    "tilbot-backend": ("Tilbot backend", "runs the conversations", (380, 128)),
    "tilbot-frontend": ("Tilbot frontend", "Tilbot's chat page and dashboard", (380, 228)),
    "docker-proxy": ("Docker proxy", "lets this page read Docker, nothing else", (590, 0)),
    "db": ("Shell database", "participants, answers (encrypted)", (590, 76)),
    "vector-similarity-intent": ("Intent service", "matches questions to the knowledge base", (590, 152)),
    "mongo": ("Tilbot database", "projects, researcher logins", (590, 228)),
}
# Who calls whom. Two arrows carry the traffic of the last hour (traffic in views.py).
LINKS = (
    ("browser", "caddy"), ("caddy", "shell"), ("caddy", "tilbot-backend"), ("caddy", "tilbot-frontend"),
    ("tilbot-backend", "shell"), ("shell", "docker-proxy"), ("shell", "db"),
    ("shell", "vector-similarity-intent"), ("tilbot-backend", "mongo"),
)
BOX_WIDTH, BOX_HEIGHT = 150, 56
# The word in a box, per health (health() below, and views.component for boxes Docker doesn't know).
WORDS = {
    "up": "running", "starting": "starting", "down": "down", "off": "not used",
    "unknown": "unknown", "outside": "outside the system",
}


def read_docker() -> dict[str, dict]:
    """Service name -> its status, health, CPU, memory and latest log lines, for every container of the project."""
    filters = json.dumps({"label": [f"com.docker.compose.project={PROJECT}"]})
    containers = json.loads(docker_get(f"/containers/json?{urlencode({'all': 1, 'filters': filters})}"))
    with ThreadPoolExecutor() as pool:  # Docker takes about a second to measure a container's CPU
        return dict(pool.map(read_container, containers))


def read_container(container: dict) -> tuple[str, dict]:
    path = f"/containers/{container['Id']}"
    running = container["State"] == "running"
    stats = json.loads(docker_get(f"{path}/stats?stream=false")) if running else None
    log = docker_get(f"{path}/logs?{urlencode({'stdout': 1, 'stderr': 1, 'timestamps': 1, 'tail': LOG_LINES})}")
    return container["Labels"]["com.docker.compose.service"], {
        "status": container["Status"],
        "health": health(container["State"], container["Status"]),
        "log": log_text(log),
        **usage(stats),
    }


def docker_get(path: str) -> bytes:
    connection = http.client.HTTPConnection("docker-proxy", 2375, timeout=10)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    if response.status != 200:
        raise OSError(f"Docker answered {response.status} to {path.split('?')[0]}")
    return body


def health(state: str, status: str) -> str:
    """up, starting or down, from Docker's state and its status text, for example "Up 2 hours (healthy)"."""
    if state != "running" or "(unhealthy)" in status:
        return "down"
    if "(health: starting)" in status:
        return "starting"
    return "up"


def usage(stats: dict | None) -> dict:
    """CPU (percent of one core) and memory (MB) as `docker stats` shows them; None when not running."""
    if stats is None:
        return {"cpu": None, "memory": None}
    now, before, memory = stats["cpu_stats"], stats["precpu_stats"], stats["memory_stats"]
    used = now["cpu_usage"]["total_usage"] - before["cpu_usage"]["total_usage"]
    system = now.get("system_cpu_usage", 0) - before.get("system_cpu_usage", 0)
    return {
        "cpu": 100 * used / system * now.get("online_cpus", 1) if system > 0 else 0.0,
        "memory": (memory.get("usage", 0) - memory.get("stats", {}).get("inactive_file", 0)) / 2**20,
    }


def log_text(raw: bytes) -> str:
    """Docker's log of a container without a terminal: pieces, each after an 8-byte header ending in its size."""
    pieces, at = [], 0
    while at < len(raw):
        size = int.from_bytes(raw[at + 4 : at + 8], "big")
        pieces.append(raw[at + 8 : at + 8 + size])
        at += 8 + size
    return b"".join(pieces).decode("utf-8", "replace")


def arrow(start: str, end: str) -> tuple[int, int, int, int]:
    """The line from one box to another: right side to left side, or straight up within a column."""
    (x1, y1), (x2, y2) = COMPONENTS[start][2], COMPONENTS[end][2]
    if x1 == x2:
        return x1 + BOX_WIDTH // 2, y1, x2 + BOX_WIDTH // 2, y2 + BOX_HEIGHT
    return x1 + BOX_WIDTH, y1 + BOX_HEIGHT // 2, x2, y2 + BOX_HEIGHT // 2
