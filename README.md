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
  instakindle
```

## Docker Compose

```yaml
services:
  instakindle:
    image: instakindle
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

Articles are fetched as HTML from Instapaper and converted to EPUB. The resulting EPUB is sent directly to Kindle via email (Amazon converts EPUB to Kindle format on receipt).

The conversion must handle:

- **Images** — Downloaded and embedded inline in the ebook
- **Code blocks** — Preserved with monospace formatting and syntax structure
- **Typography** — Clean, readable formatting suitable for e-ink displays
- **Metadata** — Title, author, and source URL are set in the ebook metadata

### Conversion Engine Options

> **Note:** The final choice will be made after comparing output quality across all three options. For now, the codebase will be structured so the conversion engine is swappable.

| Option | Install | Image Size Impact | Pros | Cons |
|---|---|---|---|---|
| **[Calibre](https://calibre-ebook.com/) `ebook-convert`** | `apt install calibre` | ~500MB+ (pulls Qt, GUI libs) | Battle-tested, handles edge cases well | Very heavy; bloats the Docker image significantly |
| **[Pandoc](https://pandoc.org/)** | `apt install pandoc` or static binary | ~100MB | Proven CLI tool, solid HTML→EPUB, lighter than Calibre | Still a non-trivial system dependency |
| **[ebooklib](https://github.com/aerkalov/ebooklib)** | `pip install ebooklib` | Negligible (pure Python) | Zero system deps, full control over output, lightest option | We build EPUB programmatically; more code to write and maintain |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐     ┌────────┐
│  Instapaper  │────▶│  InstaKindle │────▶│ Converter │────▶│ Kindle │
│     API      │◀────│   (Python)   │     │ (TBD)     │     │ (SMTP) │
│              │ tag │              │     │           │     │        │
│              │+arch│              │     │           │     │        │
└─────────────┘     └──────────────┘     └───────────┘     └────────┘
```

- **Language**: Python
- **Base image**: `python:3.13-slim`
- **Ebook conversion**: TBD — see [Conversion Engine Options](#conversion-engine-options)
- **Email delivery**: Python `smtplib` (SMTP with TLS)

## Building

```bash
docker build -t instakindle .
```

## License

MIT
