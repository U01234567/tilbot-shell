# The shell (Django), as it runs in production. compose.dev.yaml swaps the command for runserver.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Exact versions with hashes only. Regenerate with: python start_shell.py lock
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .
# Every start: bring the database up to date, drop expired sign-in sessions, then serve.
CMD ["sh", "-c", "python manage.py migrate && python manage.py clearsessions && python manage.py collectstatic --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3"]
