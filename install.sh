#!/usr/bin/env bash
# AgentGit One-Line Installer for Linux and macOS
# Usage: curl -sSL https://raw.githubusercontent.com/adesh-2006/AgentGit/main/install.sh | bash

set -e

echo "🧬 Installing AgentGit..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install Python 3.9+ first."
    exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install "git+https://github.com/adesh-2006/AgentGit.git"

echo ""
echo "✅ AgentGit installed successfully!"
echo "🚀 Run the zero-config demo right now:"
echo "   agentgit demo"
