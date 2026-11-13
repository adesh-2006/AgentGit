# Contributing to AgentGit

Thanks for your interest in contributing! 🎉

## Development Setup

```bash
git clone https://github.com/adesh-2006/AgentGit.git
cd AgentGit
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v
```

## Code Quality

```bash
ruff check agentgit/
ruff format agentgit/
```

## Pull Request Process

1. Fork the repo and create a branch from `main`
2. Write tests for any new functionality
3. Ensure all tests pass and linting is clean
4. Update the README if needed
5. Submit a PR with a clear description

## Code Style

- Type hints on all public functions
- Docstrings on all public classes and functions
- Follow existing code patterns
- Keep functions focused and small

## Reporting Issues

- Use GitHub Issues
- Include a minimal reproduction case
- Include your Python version and OS
