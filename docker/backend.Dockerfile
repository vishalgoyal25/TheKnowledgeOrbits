FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

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

# 1. Install ML first (Heavy, rarely changes)
#    Also pre-download the embedding model into the image layer cache
#    so containers don't re-download it on every fresh start (~90 MB saved).
COPY backend/requirements/ml.txt /app/requirements/ml.txt
RUN pip install --upgrade pip
RUN if [ "$INSTALL_ML" = "true" ] ; then \
    pip install --no-cache-dir -r requirements/ml.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" ; \
    fi

# 2. Install Dev (Testing tools)
COPY backend/requirements/dev.txt /app/requirements/dev.txt
RUN if [ "$INSTALL_DEV" = "true" ] ; then pip install --no-cache-dir -r requirements/dev.txt ; fi

# 3. Install Base + Scraper (Changes most frequently)
COPY backend/requirements/base.txt /app/requirements/base.txt
COPY backend/requirements/scraper.txt /app/requirements/scraper.txt
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir -r requirements/scraper.txt

# Copy project
COPY backend/ .

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD sh -c "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"
