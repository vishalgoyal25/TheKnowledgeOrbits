FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Suppress pip's root-user warning (safe inside Docker — container IS the environment)
ENV PIP_ROOT_USER_ACTION=ignore

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Use build arguments to optionally install Dev and ML packages
ARG INSTALL_DEV=false
ARG INSTALL_ML=false

# ── LAYER 1: ML packages (heavy, ~1GB, rarely changes) ────────────────────────
# When INSTALL_ML=true, also pre-downloads the embedding model so it is baked
# into the image layer. Subsequent builds reuse this layer unless ml.txt changes.
COPY backend/requirements/ml.txt /app/requirements/ml.txt
RUN pip install --upgrade pip --quiet
RUN if [ "$INSTALL_ML" = "true" ] ; then \
    pip install --no-cache-dir -r requirements/ml.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" ; \
    fi

# ── LAYER 2: Dev/testing tools (medium, rarely changes) ───────────────────────
COPY backend/requirements/dev.txt /app/requirements/dev.txt
RUN if [ "$INSTALL_DEV" = "true" ] ; then pip install --no-cache-dir -r requirements/dev.txt ; fi

# ── LAYER 3: Base application packages (changes most frequently) ──────────────
# NOTE: scraper.txt is intentionally NOT installed here — all its packages are
# already covered by ml.txt + base.txt. scraper.txt is a standalone file used
# only by GitHub Actions (ca_automation.yml) where the other files aren't present.
COPY backend/requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

# ── LAYER 4: Application code (changes most frequently, must be last) ─────────
COPY backend/ .

# Expose default port (overridden by Render via $PORT)
EXPOSE 8000

# Start Gunicorn with optimized settings for Render
# - Use the dynamic $PORT provided by Render
# - Multiple workers for concurrency
# - Increased timeout to 120s to allow for cold starts
CMD gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
