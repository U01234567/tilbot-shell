"""Researcher pages. Every view requires a login; the login page itself is Django's."""

import csv
import io
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Participant
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
