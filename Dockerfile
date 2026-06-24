# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline

COPY frontend/ .
RUN npm run build


# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.13-slim AS app
WORKDIR /app

# Build tools needed by some Python C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
  && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first (keeps image ~500 MB smaller than the default GPU wheel)
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all-providers]"

# Pre-download the embedding model at build time so startup is instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application source
COPY src/ src/

# Embed the pre-built frontend
COPY --from=frontend-builder /app/frontend/dist frontend/dist

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "src.qa_platform.api.main:app", \
     "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "1"]
