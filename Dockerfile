# =============================================================================
# Stage 1: Builder — install Python dependencies
# =============================================================================
FROM python:3.13-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for better layer caching
COPY pyproject.toml requirements.lock ./
COPY src/ src/

# Install the package and its dependencies into a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir --no-deps .

# =============================================================================
# Stage 2: Runtime — minimal image
# =============================================================================
FROM python:3.13-slim AS runtime

LABEL maintainer="InstaKindle Contributors"
LABEL description="Fetch Instapaper articles, convert to ebooks, deliver to Kindle"

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Healthcheck — verify the module can be imported
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD python -c "import instakindle" || exit 1

ENTRYPOINT ["python", "-m", "instakindle"]
