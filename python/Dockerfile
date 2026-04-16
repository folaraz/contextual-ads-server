FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Set Python path
ENV PYTHONPATH=/app/python

# Install system dependencies including Java JDK 17 for PyFlink and pemja
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    wget \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME based on architecture
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then \
        echo "JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64" >> /etc/environment; \
        export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64; \
    else \
        echo "JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64" >> /etc/environment; \
        export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64; \
    fi

# Set default JAVA_HOME for ARM64 (Apple Silicon)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Check and override JAVA_HOME if on AMD64
RUN if [ ! -d "$JAVA_HOME" ]; then \
        export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64; \
    fi

# Copy requirements first for better caching
COPY python/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy data directory (taxonomy files etc.)
COPY data/ ./data/

# Copy Python application code
COPY python/ ./python/

WORKDIR /app/python

# Default command - can be overridden in docker-compose
CMD ["python", "consumer/context_processor.py"]



