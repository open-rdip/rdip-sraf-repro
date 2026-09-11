# SRAF engine container — runs the lifter, RAG pipeline, diff engine, dashboard.
#
# Build for linux/amd64 to match the cluster architecture.
# Docker Compose sets the platform automatically on Apple Silicon.

FROM --platform=linux/amd64 python:3.12-slim-bookworm

# System dependencies:
#   git           — for cloning research repos in the build harness
#   curl          — for healthchecks and SPARQL endpoint testing
#   build-essential — required by some Python wheels (rdflib-jsonld, etc.)
#   ca-certificates — TLS for git clone over https
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Engine-only dependencies: requirements.txt pulls sentence-transformers ->
# torch (~2 GB), which the engine never uses and which makes the image too big
# to pull under the cluster's home quota. See requirements-engine.txt.
COPY requirements-engine.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-engine.txt

# Copy the rest of the repo
COPY . .

# Default environment — overridden by docker-compose.yml or Slurm env vars
ENV OXIGRAPH_HOST=oxigraph \
    OXIGRAPH_PORT=7878 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/workspace

# Sleep by default so `docker compose exec` can attach for interactive work.
# Individual commands run via `docker compose exec sraf-engine python ...`
CMD ["sleep", "infinity"]
