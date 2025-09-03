ARG PYTHON_IMAGE=python:3.12-slim

# -----------------------------
# Builder: ставим зависимости
# -----------------------------
FROM ${PYTHON_IMAGE} AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
ARG INSTALL_DEV=0
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && echo "uv installed"
ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /app
COPY pyproject.toml ./
# Синхронизируем окружение (dev-зависимости опционально)
RUN if [ "$INSTALL_DEV" = "1" ]; then uv sync --no-cache; else uv sync --no-cache --no-dev; fi
COPY . .
RUN if [ "$INSTALL_DEV" = "1" ]; then uv sync --no-cache; else uv sync --no-cache --no-dev; fi

# -----------------------------
# Runtime: только рантайм либы + venv
# -----------------------------
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    libpango-1.0-0 libcairo2 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Копируем виртуальное окружение из билдера
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"
# Некорневой пользователь
RUN useradd -ms /bin/bash app
COPY --chown=app:app . .
USER app
EXPOSE 8000
# Стартуем через интерпретатор из venv
CMD ["python", "-m", "uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
