FROM python:3.11-slim

# Set maintainer
LABEL maintainer="HealthFlow-MS Team"
LABEL service="featurizer"

# Set working directory
WORKDIR /app

# Install system dependencies including those needed for ML libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install specific spaCy model compatible with spaCy 3.6.x
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.6.0/en_core_web_sm-3.6.0-py3-none-any.whl

# Copy application code
COPY app/ ./

# Create non-root user for security
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
    CMD python -c "import spacy; import transformers; print('Health check passed')" || exit 1

# Run the application
CMD ["python", "main.py"]