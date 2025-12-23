FROM python:3.13-slim AS base

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Change ownership of app directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Install uv package manager as appuser
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH for appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Health check - FastMCP provides /mcp endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -s http://localhost:${PORT:-8000}/mcp > /dev/null || exit 1

# Default command
CMD ["uv", "run", "-m", "ssmcp.server"]

# =============================================================================
# Development target - includes dev dependencies, uses volume mount for source
# =============================================================================
FROM base AS development

# Mark this as a development environment
ENV BUILD_ENV=development

# Install ALL dependencies (including dev and test)
RUN uv sync --frozen

# Switch to root for system package installation
USER root

# Install Playwright system dependencies (chromium only to reduce image size)
RUN uv run playwright install-deps chromium

# Switch back to appuser for security
USER appuser

# Install only Chromium browser (saves ~600MB vs installing all browsers)
RUN uv run playwright install chromium

# Run crawl4ai post-installation setup
RUN uv run crawl4ai-setup

# Verify installation and add helper alias
RUN uv run crawl4ai-doctor && \
    echo 'alias doctor="crawl4ai-doctor"' >> ~/.bashrc

# =============================================================================
# Production target - minimal dependencies, bakes source code into image
# =============================================================================
FROM base AS production

# Mark this as a production environment
ENV BUILD_ENV=production

# Install only production dependencies (no dev/test)
RUN uv sync --frozen --no-dev

# Switch to root for system package installation
USER root

# Install Playwright system dependencies (chromium only to reduce image size)
RUN uv run playwright install-deps chromium

# Switch back to appuser for security
USER appuser

# Install only Chromium browser (saves ~600MB vs installing all browsers)
RUN uv run playwright install chromium

# Run crawl4ai post-installation setup
RUN uv run crawl4ai-setup

# Clean up caches to reduce image size
RUN rm -rf ~/.cache/uv ~/.cache/pip 2>/dev/null || true

# Copy application source code
COPY --chown=appuser:appuser src/ssmcp ./src/ssmcp
