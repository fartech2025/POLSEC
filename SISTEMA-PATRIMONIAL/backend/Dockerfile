# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Dependências de compilação (psycopg binário)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências em camada separada para cache
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Usuário não-root
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Copia dependências instaladas
COPY --from=builder /install /usr/local

# Copia código da aplicação
COPY . .

# Remove arquivos desnecessários na imagem final
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf .venv .env* tests/ *.md importar_*.py aplicar_*.py seed_*.py criar_*.py

# Permissões
RUN chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

# Produção: sem reload, workers configuráveis via env
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log"]
