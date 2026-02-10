FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    mkdir -p data logs && \
    chown -R botuser:botuser /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=botuser:botuser . .

# Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "bot.py"]
