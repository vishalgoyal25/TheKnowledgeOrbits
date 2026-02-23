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
COPY backend/requirements/ml.txt /app/requirements/ml.txt
RUN pip install --upgrade pip
RUN if [ "$INSTALL_ML" = "true" ] ; then pip install --no-cache-dir -r requirements/ml.txt ; fi

# 2. Install Dev (Testing tools)
COPY backend/requirements/dev.txt /app/requirements/dev.txt
RUN if [ "$INSTALL_DEV" = "true" ] ; then pip install --no-cache-dir -r requirements/dev.txt ; fi

# 3. Install Base (Changes most frequently)
COPY backend/requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

# Copy project
COPY backend/ .

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD sh -c "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"
