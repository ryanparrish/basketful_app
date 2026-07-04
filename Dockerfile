# Use official Python image (3.13 stable)
FROM python:3.13-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install system dependencies for psycopg2, reportlab, Pillow, etc.
# gettext provides msgfmt for compiling translation catalogs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Compile translation catalogs (.po → .mo). Without this the app silently
# serves English only. django-admin needs no SECRET_KEY/DB for this step.
RUN django-admin compilemessages -l es --ignore=venv --ignore=node_modules \
    --ignore=frontend --ignore=participant-frontend

# Default command for running Django
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
