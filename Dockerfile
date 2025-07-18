# Obsidian Post-Processor Docker Container
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Copy application code
COPY obsidian_processor/ obsidian_processor/
COPY processor/ processor/
COPY main.py .

# Create vault mount point (as root)
RUN mkdir -p /vault

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user for security (optional)
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /vault
# Run as root by default for compatibility with various filesystems
# Users can override with --user appuser if they prefer non-root execution

# Set environment variables
ENV PYTHONPATH=/app
ENV VAULT_PATH=/vault
ENV PROCESSOR_SCRIPT_PATH=/app/processor/add_transcript_to_voicememo.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python main.py --config || exit 1

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (will be passed to entrypoint)
CMD []
