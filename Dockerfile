FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    iverilog \
    verilator \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install uv (system-wide)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/root/.local/bin:/root/.cargo/bin:/usr/local/bin:$PATH"

# Create ubuntu user
RUN useradd -m -s /bin/bash ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Configure git for both root and ubuntu users
RUN git config --global --add safe.directory /home/ubuntu/example-verilog-codebase && \
    git config --global user.email "test@example.com" && \
    git config --global user.name "Test User"

# Set up working directory
WORKDIR /home/ubuntu

# Copy problem files (with git repo)
COPY local-repos/problems /home/ubuntu/example-verilog-codebase

# Remove any local .venv that might have wrong shebang paths
RUN rm -rf /home/ubuntu/example-verilog-codebase/.venv \
    /home/ubuntu/example-verilog-codebase/.pytest_cache \
    /home/ubuntu/example-verilog-codebase/sim_build

RUN chown -R ubuntu:ubuntu /home/ubuntu/example-verilog-codebase

# Set up git branches and generate patches
WORKDIR /home/ubuntu/example-verilog-codebase
ARG TEST_BRANCH=crc32_test
ARG GOLDEN_BRANCH=crc32_golden
ARG BASELINE_BRANCH=crc32_baseline

# Checkout branches (they should already exist from local-repos)
RUN git checkout $BASELINE_BRANCH && \
    git checkout $TEST_BRANCH && \
    git checkout $GOLDEN_BRANCH && \
    git checkout $BASELINE_BRANCH

# Generate patches for grading (test.patch only - golden.patch would leak the answer!)
RUN mkdir -p /home/root && \
    git diff $BASELINE_BRANCH $TEST_BRANCH > /home/root/test.patch
# NOTE: golden.patch is NOT generated to prevent answer leakage

# Overwrite git history to avoid leaking info to agent
RUN rm -rf .git && git init && git add . && git commit -m "Initial commit"

# Fix ownership
RUN chown -R ubuntu:ubuntu /home/ubuntu/example-verilog-codebase

# Copy HUD controller
COPY src /app/src
COPY pyproject.toml /app/
COPY README.md /app/

# Install HUD controller
WORKDIR /app
RUN uv sync

# Set up problem environment
WORKDIR /home/ubuntu/example-verilog-codebase
RUN uv sync

# Switch to ubuntu user for running tests
USER ubuntu
WORKDIR /home/ubuntu/example-verilog-codebase

# Configure git for ubuntu user
RUN git config --global user.email "ubuntu@example.com" && \
    git config --global user.name "Ubuntu User" && \
    git config --global --add safe.directory /home/ubuntu/example-verilog-codebase

# Entry point for MCP server
WORKDIR /app
CMD ["uv", "run", "python", "-m", "hud_controller.app"]
