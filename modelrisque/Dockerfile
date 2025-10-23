FROM python:3.11-slim

# Set maintainer
LABEL maintainer="HealthFlow-MS Team"
LABEL service="modelrisque"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create model directory
RUN mkdir -p /app/model

# Copy application code
COPY app/ ./

# Create non-root user for security
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import xgboost; import shap; print('Health check passed')" || exit 1

# Run the application
CMD ["python", "main.py"]