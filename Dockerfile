FROM python:3.11-slim

# Install system dependencies (optional)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

RUN pwd
# Default command: long-polling bot
CMD ["python3", "-m", "no_quitting_bot"] 