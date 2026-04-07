[![CI](https://github.com/onexey/InstaKindle/actions/workflows/ci.yml/badge.svg)](https://github.com/onexey/InstaKindle/actions/workflows/ci.yml)
[![Publish Docker Image](https://github.com/onexey/InstaKindle/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/onexey/InstaKindle/actions/workflows/docker-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<a href="https://www.buymeacoffee.com/onexey" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="30"></a>

# InstaKindle

Automatically fetch your Instapaper articles, convert them to well-formatted ebooks, and deliver them straight to your Kindle — running continuously in a lightweight Docker container.

## What It Does

InstaKindle runs a simple loop:

1. **Fetch** — Connects to the Instapaper API and retrieves all unread articles
2. **Convert** — Transforms each article into a properly formatted EPUB/MOBI ebook, preserving images, code blocks, and formatting
3. **Send** — Delivers the ebook to your Kindle via Amazon's Send-to-Kindle email service
4. **Move** — Moves the article to an "InstaKindle" folder in Instapaper (removing it from your unread list)
5. **Repeat** — Waits for a configurable interval, then starts again

## Features

- **Full-fidelity conversion** — Images, code snippets, and rich formatting are preserved in the ebook output
- **Lightweight Docker image** — Multi-stage build, minimal base image, small footprint
- **Configurable via environment variables** — No config files to mount; pass everything through env vars or CLI arguments
- **Continuous operation** — Runs as a long-lived container, polling on a configurable interval
- **Idempotent** — Already-processed articles are moved to an "InstaKindle" folder, so they won't be sent twice

## Configuration

All configuration is provided via environment variables (or equivalent CLI arguments):

| Environment Variable | CLI Flag | Required | Description |
|---|---|---|---|
| `INSTAPAPER_KEY` | `--instapaper-key` | Yes | Instapaper OAuth consumer key |
| `INSTAPAPER_SECRET` | `--instapaper-secret` | Yes | Instapaper OAuth consumer secret |
| `INSTAPAPER_USERNAME` | `--instapaper-username` | Yes | Instapaper account email/username |
| `INSTAPAPER_PASSWORD` | `--instapaper-password` | Yes | Instapaper account password |
| `KINDLE_EMAIL` | `--kindle-email` | Yes | Your Kindle's Send-to-Kindle email address (e.g. `you@kindle.com`) |
| `SMTP_HOST` | `--smtp-host` | Yes | SMTP server hostname |
| `SMTP_PORT` | `--smtp-port` | No | SMTP server port (default: `587`) |
| `SMTP_USERNAME` | `--smtp-username` | Yes | SMTP login username |
| `SMTP_PASSWORD` | `--smtp-password` | Yes | SMTP login password |
| `SENDER_EMAIL` | `--sender-email` | Yes | Email address to send from (must be approved in your Amazon account) |
| `POLL_INTERVAL` | `--poll-interval` | No | Seconds between each fetch cycle (default: `900` / 15 minutes) |
| `LOG_LEVEL` | `--log-level` | No | Logging verbosity: `debug`, `info`, `warn`, `error` (default: `info`) |

## Quick Start

### Docker Compose

The repository includes a ready-to-use `docker-compose.yml`:

```yaml
services:
  instakindle:
    image: ghcr.io/onexey/instakindle
    container_name: instakindle
    restart: unless-stopped
    environment:
      INSTAPAPER_KEY: ${INSTAPAPER_KEY}
      INSTAPAPER_SECRET: ${INSTAPAPER_SECRET}
      INSTAPAPER_USERNAME: ${INSTAPAPER_USERNAME}
      INSTAPAPER_PASSWORD: ${INSTAPAPER_PASSWORD}
      KINDLE_EMAIL: ${KINDLE_EMAIL}
      SMTP_HOST: ${SMTP_HOST}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USERNAME: ${SMTP_USERNAME}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      SENDER_EMAIL: ${SENDER_EMAIL}
      POLL_INTERVAL: ${POLL_INTERVAL:-900}
      LOG_LEVEL: ${LOG_LEVEL:-info}
```

1. Copy `.env.example` to `.env` and fill in your credentials:

   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

2. Start the container:

   ```bash
   docker compose up -d
   ```

3. View logs:

   ```bash
   docker compose logs -f instakindle
   ```

### CLI

```bash
pip install .
instakindle \
  --instapaper-key your_key \
  --instapaper-secret your_secret \
  --instapaper-username you@example.com \
  --instapaper-password your_password \
  --kindle-email you@kindle.com \
  --smtp-host smtp.gmail.com \
  --smtp-port 587 \
  --smtp-username you@gmail.com \
  --smtp-password your_app_password \
  --sender-email you@gmail.com
```

## Documentation

- [Deployment Guide](docs/deployment.md) — Building, publishing, Docker Compose, credential setup, and troubleshooting
- [Development Guide](docs/development.md) — Local setup, testing, linting, architecture, and contributing

## License

MIT
