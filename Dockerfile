# AgentGit Dockerfile — zero local setup
FROM python:3.11-slim

WORKDIR /app

# Install git and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install AgentGit
COPY . /app
RUN pip install --no-cache-dir -e .

EXPOSE 8585

# Default to starting the web dashboard
CMD ["agentgit", "ui", "--port", "8585", "--no-browser"]
