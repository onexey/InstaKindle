# Development Guide

This guide covers how to set up a local development environment for InstaKindle.

## Prerequisites

- Python 3.11 or later
- Git

## Setup

1. **Clone the repository:**

```bash
git clone https://github.com/onexey/InstaKindle.git
cd InstaKindle
```

2. **Create a virtual environment:**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install the package with dev dependencies:**

```bash
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_config.py

# Run with verbose output
pytest -v

# Run only unit tests (skip integration)
pytest -m "not integration"
```

## Linting & Formatting

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix lint errors
ruff check --fix src/ tests/

# Check formatting
ruff format --check src/ tests/

# Auto-format
ruff format src/ tests/
```

## Type Checking

```bash
mypy src/
```

## Project Structure

```
InstaKindle/
├── src/
│   └── instakindle/
│       ├── __init__.py            # Package version
│       ├── __main__.py            # python -m instakindle entry point
│       ├── cli.py                 # CLI argument parsing & entry point
│       ├── config.py              # Configuration from env vars / CLI args
│       ├── instapaper.py          # Instapaper API client (OAuth 1.0a)
│       ├── pipeline.py            # Main pipeline orchestrator
│       ├── sender.py              # SMTP email sender
│       └── converter/
│           ├── __init__.py        # Converter exports
│           ├── base.py            # Abstract converter + factory + image downloader
│           ├── calibre.py         # Calibre ebook-convert wrapper
│           ├── pandoc.py          # Pandoc wrapper
│           └── ebooklib_converter.py  # Pure Python ebooklib converter
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── test_config.py
│   ├── test_instapaper.py
│   ├── test_cli.py
│   ├── test_pipeline.py
│   ├── test_sender.py
│   └── test_converter/
│       ├── test_base.py
│       ├── test_calibre.py
│       ├── test_pandoc.py
│       └── test_ebooklib.py
├── docs/
│   ├── deployment.md
│   └── development.md
├── .github/workflows/
│   ├── ci.yml                     # CI: lint, test, docker build
│   └── docker-publish.yml         # Publish to Docker Hub on release
├── Dockerfile                     # Multi-stage Docker build
├── docker-compose.yml
├── pyproject.toml                 # Project config (build, deps, tools)
├── .env.example                   # Example environment variables
├── .gitignore
└── .dockerignore
```

## Architecture

The pipeline follows a straightforward flow:

```
CLI (cli.py)
  └─> Config (config.py) — load env vars + CLI args
        └─> Pipeline (pipeline.py) — orchestrate the loop
              ├─> InstapaperClient (instapaper.py) — fetch articles
              ├─> Converter (converter/) — HTML → EPUB
              ├─> KindleSender (sender.py) — SMTP delivery
              └─> InstapaperClient — tag + archive
```

### Key Design Decisions

- **Strategy Pattern for converters**: All converters implement the abstract `Converter` base class. The factory function `get_converter()` returns the appropriate implementation based on config.
- **Frozen dataclass for config**: Configuration is immutable once loaded, preventing accidental mutation.
- **Graceful degradation**: Tagging failures are logged as warnings (not all Instapaper plans support tags). Individual article failures don't stop the pipeline.
- **Temp directory cleanup**: Conversion artifacts are cleaned up after each article is processed.

## Adding a New Converter

1. Create a new file in `src/instakindle/converter/`
2. Implement the `Converter` abstract base class
3. Add the new converter to `get_converter()` in `base.py`
4. Add the new converter to `converter/__init__.py`
5. Add tests in `tests/test_converter/`
6. Update the `Config.validate()` valid converters set

## Running Locally (without Docker)

```bash
# Set environment variables
export INSTAPAPER_KEY=your_key
export INSTAPAPER_SECRET=your_secret
# ... set all required vars ...

# Run the application
python -m instakindle

# Or with CLI arguments
instakindle --instapaper-key your_key --instapaper-secret your_secret ...
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests and linting: `pytest && ruff check src/ tests/`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request
