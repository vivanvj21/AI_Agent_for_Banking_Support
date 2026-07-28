# Contributing Guide

> How to contribute to the Autonomous Banking Assistant.

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/your-username/AI-Agent-for-Banking-Support.git
cd "AI Agent for Banking Support"

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# 5. Initialize
python start.py init-db

# 6. Verify
python start.py check
```

---

## Code Style

This project uses:
- **Black** for formatting: `black .`
- **Ruff** for linting: `ruff check .`
- **isort** for import sorting: `isort .`

> Run before submitting a PR.

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v -k "test_account"   # filter by name
pytest tests/ --tb=short              # compact output
```

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, deployable |
| `develop` | Integration branch |
| `feature/*` | New features |
| `fix/*` | Bug fixes |

---

## Pull Request Process

1. Branch from `develop`
2. Implement your change
3. Add/update tests
4. Run `black`, `ruff`, `isort`
5. Update relevant docs (`docs/`)
6. Open a PR against `develop`
7. Ensure CI passes

---

## Adding a New Agent

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md#how-to-add-a-new-agent).

## Adding a New MCP Server

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md#how-to-add-a-new-mcp-server).

---

## Reporting Issues

Please include:
- Python version
- OS
- Steps to reproduce
- Expected vs. actual behavior
- Relevant log output (`logs/` directory)
