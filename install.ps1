# AgentGit One-Line Installer for Windows PowerShell
# Usage: irm https://raw.githubusercontent.com/adesh-2006/AgentGit/main/install.ps1 | iex

Write-Host "🧬 Installing AgentGit..." -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python 3 is required. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}

pip install "git+https://github.com/adesh-2006/AgentGit.git"

Write-Host "`n✅ AgentGit installed successfully!" -ForegroundColor Green
Write-Host "🚀 Run the zero-config demo right now:" -ForegroundColor Yellow
Write-Host "   agentgit demo`n" -ForegroundColor White
