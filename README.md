# InstaKindle

Automatically fetch your Instapaper articles, convert them to well-formatted ebooks, and deliver them straight to your Kindle — running continuously in a lightweight Docker container.

## What It Does

InstaKindle runs a simple loop:

1. **Fetch** — Connects to the Instapaper API and retrieves all unread articles
2. **Convert** — Transforms each article into a properly formatted EPUB/MOBI ebook, preserving images, code blocks, and formatting
3. **Send** — Delivers the ebook to your Kindle via Amazon's Send-to-Kindle email service
4. **Tag** — Applies a `sent-to-kindle` tag to the article in Instapaper (if supported by the API)
5. **Archive** — Archives the article in Instapaper
6. **Repeat** — Waits for a configurable interval, then starts again

## Features

- **Full-fidelity conversion** — Images, code snippets, and rich formatting are preserved in the ebook output
- **Lightweight Docker image** — Multi-stage build, minimal base image, small footprint
- **Configurable via environment variables** — No config files to mount; pass everything through env vars or CLI arguments
- **Continuous operation** — Runs as a long-lived container, polling on a configurable interval
- **Idempotent** — Already-processed articles are tagged and archived, so they won't be sent twice

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

```bash
docker run -d \
  --name instakindle \
  --restart unless-stopped \
  -e INSTAPAPER_KEY=your_key \
  -e INSTAPAPER_SECRET=your_secret \
  -e INSTAPAPER_USERNAME=you@example.com \
  -e INSTAPAPER_PASSWORD=your_password \
  -e KINDLE_EMAIL=you@kindle.com \
  -e SMTP_HOST=smtp.gmail.com \
  -e SMTP_PORT=587 \
  -e SMTP_USERNAME=you@gmail.com \
  -e SMTP_PASSWORD=your_app_password \
  -e SENDER_EMAIL=you@gmail.com \
  ghcr.io/onexey/instakindle
```

## Docker Compose

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

## How Ebook Conversion Works

Articles are fetched as HTML from Instapaper and converted to EPUB using [ebooklib](https://github.com/aerkalov/ebooklib), a pure-Python library with zero system dependencies. The resulting EPUB is sent directly to Kindle via email (Amazon converts EPUB to Kindle format on receipt).

The conversion handles:

- **Images** — Downloaded and embedded inline in the ebook
- **Code blocks** — Preserved with monospace formatting and syntax structure
- **Typography** — Clean, readable formatting suitable for e-ink displays
- **Metadata** — Title, author, and source URL are set in the ebook metadata

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐     ┌────────┐
│  Instapaper  │────▶│  InstaKindle │────▶│ Converter │────▶│ Kindle │
│     API      │◀────│   (Python)   │     │ (ebooklib)│     │ (SMTP) │
│              │ tag │              │     │           │     │        │
│              │+arch│              │     │           │     │        │
└─────────────┘     └──────────────┘     └───────────┘     └────────┘
```

- **Language**: Python
- **Base image**: `python:3.13-slim`
- **Ebook conversion**: [ebooklib](https://github.com/aerkalov/ebooklib) (pure Python)
- **Email delivery**: Python `smtplib` (SMTP with TLS)

## Building

```bash
docker build -t instakindle .
```

## License

MIT
