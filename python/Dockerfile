FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml ./
COPY jarvis_ai ./jarvis_ai

RUN pip install --prefix=/install .

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

RUN useradd --system --uid 1000 --create-home app

COPY --from=builder /install /install
COPY jarvis_ai ./jarvis_ai

USER app

EXPOSE 8000

CMD ["uvicorn", "jarvis_ai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
