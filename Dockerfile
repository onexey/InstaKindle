# =============================================================================
# Stage 1: Builder — install Python dependencies
# =============================================================================
FROM python:3.14-slim AS builder

WORKDIR /build

# Install system dependencies for building Python packages (lxml requires
# C standard-library headers and the libxml2/libxslt development files).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
        zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency specification files first for better layer caching
COPY pyproject.toml requirements.lock ./

# Install pinned dependencies into a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install build dependencies required by pyproject.toml [build-system]
RUN pip install --no-cache-dir setuptools==68.2.2 wheel==0.45.1

RUN pip install --no-cache-dir -r requirements.lock

# Copy source and install the package itself (no dependency or build isolation)
COPY src/ src/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .

# =============================================================================
# Stage 2: Runtime — minimal image
# =============================================================================
FROM python:3.14-slim AS runtime

LABEL maintainer="InstaKindle Contributors"
LABEL description="Fetch Instapaper articles, convert to ebooks, deliver to Kindle"

WORKDIR /app

# Install runtime shared libraries needed by lxml (compiled from source against
# system libxml2/libxslt in the builder stage, so the shared objects must exist
# at runtime).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Healthcheck — verify the pipeline ran successfully recently.
# The healthcheck file contains "<timestamp> <poll_interval>" written by the
# pipeline, so the threshold adapts to the effective poll interval even when
# set via CLI rather than the POLL_INTERVAL env var.
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD python -c "\
import sys, time, pathlib; \
p = pathlib.Path('/tmp/instakindle_last_success'); \
parts = p.read_text().split() if p.exists() else []; \
sys.exit(1) if not parts else None; \
ts = float(parts[0]); \
interval = int(parts[1]) if len(parts) > 1 else 900; \
threshold = max(interval * 3, 1800); \
sys.exit(0 if time.time() - ts < threshold else 1)" || exit 1

ENTRYPOINT ["python", "-m", "instakindle"]
