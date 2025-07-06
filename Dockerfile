FROM python:3.11-slim

# Copy project
COPY . /no_quitting_bot

# Install Python deps
RUN pip install --no-cache-dir -r /no_quitting_bot/requirements.txt

# Default command: long-polling bot
CMD ["python3", "-m", "no_quitting_bot"] 