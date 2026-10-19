"""Researcher pages. Every view requires a login; the login page itself is Django's."""

import csv
import http.client
import io
import zipfile
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Participant
from monitor import removal, system
from monitor.export import FILES, numbering
from records.models import Answer, Question, TranscriptLine


@login_required
def overview(request):
    last_answer = Answer.objects.order_by("-at").values_list("at", flat=True).first()
    counts = {
        "participants": Participant.objects.count(),
        "answers": Answer.objects.count(),
        "questions": Question.objects.count(),
        "transcript_lines": TranscriptLine.objects.count(),
    }
    return render(request, "monitor/overview.html", {"counts": counts, "last_answer": last_answer})


@login_required
def system_page(request):
    """Every component in one drawing, green when it runs well, with its resource use and latest log lines."""
    try:
        docker, problem = system.read_docker(), ""
    except (OSError, http.client.HTTPException) as error:  # docker-proxy down, or no Docker at all (tests)
        docker, problem = {}, str(error) or type(error).__name__
    components = [component(key, docker, problem) for key in system.COMPONENTS]
    links = [system.arrow(start, end) for start, end in system.LINKS]
    return render(request, "monitor/system.html", {"components": components, "links": links, "problem": problem, "traffic": traffic()})


def component(key: str, docker: dict[str, dict], problem: str) -> dict:
    """One box: Docker's view of it, or why there is none."""
    name, role, (x, y) = system.COMPONENTS[key]
    if key == "browser":
        found = {"health": "outside", "status": "not ours to watch"}
    elif key in docker:
        found = docker[key]
    elif problem:
        found = {"health": "unknown", "status": "Docker can't be read"}
    elif key == "vector-similarity-intent" and settings.STUDY.knowledge is None:
        found = {"health": "off", "status": "not used: the study has no knowledge.xlsx"}
    else:
        found = {"health": "down", "status": "no container: python start_shell.py up"}
    return {"key": key, "name": name, "role": role, "x": x, "y": y, "word": system.WORDS[found["health"]], **found}


def traffic() -> dict[str, int]:
    """What passed over the arrows that carry participants' data, in the last hour, from the shell's own records."""
    since = timezone.now() - timedelta(hours=1)
    return {
        "answers": Answer.objects.filter(at__gte=since).count(),
        "lines": TranscriptLine.objects.filter(at__gte=since).count(),
        "questions": Question.objects.filter(at__gte=since).count(),
    }


@login_required
def export(request):
    """A zip of five CSV files, with the participants' codes or with numbers instead (export.py)."""
    if request.method != "POST":
        return render(request, "monitor/export.html")
    with_codes = request.POST.get("codes") == "with"
    numbers = numbering()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name, rows in FILES.items():
            text = io.StringIO()
            csv.writer(text).writerows(rows(with_codes, numbers))
            zipped.writestr(f"{name}.csv", text.getvalue())
    kind = "with-codes" if with_codes else "numbered"
    stamp = timezone.now().strftime("%Y-%m-%d-%H%M")
    response = HttpResponse(archive.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="export-{kind}-{stamp}.zip"'
    return response


@login_required
def remove(request):
    """Remove one participant on request: the code first, then what will be deleted, then a confirmation."""
    if request.method != "POST":
        return render(request, "monitor/remove.html")
    code = request.POST.get("code", "").strip().upper()
    participant = Participant.objects.filter(code=code).first()
    if participant is None:
        return render(request, "monitor/remove.html", {"code": code, "unknown": True})
    if request.POST.get("confirm") != code:
        return render(request, "monitor/remove.html", {"participant": participant, "stored": removal.stored_for(participant)})
    removal.remove(participant)
    return render(request, "monitor/remove.html", {"removed": code})
