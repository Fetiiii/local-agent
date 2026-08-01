# Sandbox image for Local Agent's shell_executor and data_analyst tools.
# Runs untrusted, model-generated code isolated from the host.
# Build once:  docker build -t localagent-sandbox:latest -f docker/sandbox.Dockerfile .
FROM python:3.12-slim

# Basic tooling the shell_executor commonly needs (git, curl, build tools).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# Data-analysis stack + a Jupyter kernel (used by the persistent data_analyst
# REPL in phase B). Installed system-wide so the sandbox user can import them.
RUN pip install --no-cache-dir \
        numpy pandas matplotlib plotly seaborn openpyxl \
        ipykernel jupyter_client

# Persistent data_analyst kernel driver (runs inside the container).
COPY backend/tools/sandbox/da_driver.py /opt/da_driver.py

# Non-root user matching the host uid so mounted files stay owner-aligned.
RUN useradd -m -u 1000 sandbox
# Put the user's pip script dir on PATH so `pip install <cli>` then running that
# CLI works in the same session (docker exec inherits this ENV).
ENV PATH="/home/sandbox/.local/bin:${PATH}"
USER sandbox
WORKDIR /workspace

# Long-lived: the container idles; commands are injected via `docker exec`.
CMD ["sleep", "infinity"]
