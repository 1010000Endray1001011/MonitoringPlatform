# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /app

RUN pip install poetry==2.4.1

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .
RUN chown -R app:app /app

USER app

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
