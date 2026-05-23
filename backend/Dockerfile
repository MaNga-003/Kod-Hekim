FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# system deps for git (gitpython) + build tools for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY . .

# Railway sets $PORT dynamically; fall back to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# shell form so $PORT expands at runtime
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
