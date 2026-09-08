FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The full project root is mounted as a volume at /app in docker-compose.
# This Dockerfile is used only for the image base — source code is live-mounted.

EXPOSE 8000
