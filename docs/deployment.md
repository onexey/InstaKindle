# Deployment Guide

This guide covers how to build, publish, and deploy InstaKindle as a Docker image.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- A [Docker Hub](https://hub.docker.com/) account (for publishing)
- Instapaper API credentials (OAuth consumer key & secret)
- SMTP credentials for sending emails
- Your Kindle Send-to-Kindle email address

## Building the Docker Image

### Local Build

```bash
docker build -t instakindle .
```

### Multi-platform Build (for Docker Hub)

```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t youruser/instakindle:latest --push .
```

## Publishing to Docker Hub

### Manual Push

1. **Log in to Docker Hub:**

   ```bash
   docker login
   ```

2. **Tag the image:**

   ```bash
   docker tag instakindle youruser/instakindle:latest
   docker tag instakindle youruser/instakindle:1.0.0
   ```

3. **Push:**

   ```bash
   docker push youruser/instakindle:latest
   docker push youruser/instakindle:1.0.0
   ```

### Automated Publishing (CI/CD)

The repository includes a GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that automatically builds and pushes the Docker image when a release is created.

**Setup steps:**

1. Go to your repository's **Settings → Secrets and variables → Actions**
2. Add the following secrets:
   - `DOCKERHUB_USERNAME` — Your Docker Hub username
   - `DOCKERHUB_TOKEN` — A Docker Hub [access token](https://docs.docker.com/docker-hub/access-tokens/)

3. Create a new release on GitHub. The workflow will:
   - Build images for `linux/amd64` and `linux/arm64`
   - Push with semantic version tags (e.g., `1.0.0`, `1.0`, `1`, `latest`)

## Running the Container

### Using `docker run`

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
  -e POLL_INTERVAL=900 \
  -e LOG_LEVEL=info \
  -e CONVERTER=ebooklib \
  instakindle
```

### Using Docker Compose

1. Copy `.env.example` to `.env` and fill in your credentials:

   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

2. Start:

   ```bash
   docker compose up -d
   ```

3. View logs:

   ```bash
   docker compose logs -f instakindle
   ```

4. Stop:

   ```bash
   docker compose down
   ```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `INSTAPAPER_KEY` | Yes | — | Instapaper OAuth consumer key |
| `INSTAPAPER_SECRET` | Yes | — | Instapaper OAuth consumer secret |
| `INSTAPAPER_USERNAME` | Yes | — | Instapaper account email/username |
| `INSTAPAPER_PASSWORD` | Yes | — | Instapaper account password |
| `KINDLE_EMAIL` | Yes | — | Your Kindle Send-to-Kindle email |
| `SMTP_HOST` | Yes | — | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USERNAME` | Yes | — | SMTP login username |
| `SMTP_PASSWORD` | Yes | — | SMTP login password |
| `SENDER_EMAIL` | Yes | — | Email address to send from |
| `POLL_INTERVAL` | No | `900` | Seconds between fetch cycles |
| `LOG_LEVEL` | No | `info` | Logging level: debug, info, warn, error |
| `CONVERTER` | No | `ebooklib` | Converter engine: ebooklib, calibre, pandoc |

## Choosing a Converter

| Converter | Docker Image Size | Dependencies | Best For |
|---|---|---|---|
| `ebooklib` | ~150 MB | None (pure Python) | Lightest option, good for most articles |
| `pandoc` | ~250 MB | `pandoc` binary | More robust HTML handling |
| `calibre` | ~650 MB+ | `calibre` + Qt/GUI libs | Best edge-case handling, heaviest |

The default converter is `ebooklib`. To use a different converter, set the `CONVERTER` environment variable.

## Monitoring

- Check container status: `docker ps`
- View logs: `docker logs -f instakindle`
- The container includes a healthcheck that verifies the Python module loads correctly

## Troubleshooting

- **Authentication errors**: Verify your Instapaper OAuth credentials. Note that the Instapaper API requires a paid subscription.
- **SMTP errors**: Check your SMTP credentials and ensure your sender email is approved in your Amazon account's Send-to-Kindle settings.
- **Kindle not receiving**: Make sure the sender email is in your Amazon approved email list at [amazon.com/manageyourkindle](https://www.amazon.com/manageyourkindle).
