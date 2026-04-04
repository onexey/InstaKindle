# Deployment Guide

This guide covers how to build, publish, and deploy InstaKindle as a Docker image.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- A [GitHub](https://github.com/) account (for publishing via GitHub Container Registry)
- Instapaper API credentials (OAuth consumer key & secret) — see [Obtaining Instapaper API Credentials](#obtaining-instapaper-api-credentials)
- SMTP credentials for sending emails — see [Setting Up Email (SMTP)](#setting-up-email-smtp)
- Your Kindle Send-to-Kindle email address — see [Finding Your Kindle Email Address](#finding-your-kindle-email-address)

## Obtaining Instapaper API Credentials

InstaKindle uses the Instapaper Full API with OAuth 1.0a (xAuth) to fetch your bookmarks. You need a **consumer key** and **consumer secret** to authenticate.

> **Note:** The Instapaper Full API requires an Instapaper Premium (subscription) account.

1. Log in to your Instapaper account
2. Go to **https://www.instapaper.com/developers/applications/create**
3. Fill out the short form describing your use case (e.g. "Personal tool to send articles to Kindle")
4. Instapaper will provide you with a **Consumer Key** and **Consumer Secret**
5. Set these values in your `.env` file:

   ```dotenv
   INSTAPAPER_KEY=your_consumer_key
   INSTAPAPER_SECRET=your_consumer_secret
   ```

## Finding Your Kindle Email Address

Amazon assigns each Kindle device (and the Kindle app) a unique Send-to-Kindle email address. InstaKindle sends converted ebooks to this address.

1. Go to [Amazon – Manage Your Content and Devices](https://www.amazon.com/mn/dcw/myx.html)
2. Click the **Devices** tab
3. Select your Kindle device (or the Kindle app you use)
4. Your Send-to-Kindle email is shown — it looks like `something@kindle.com`
5. Set it in your `.env` file:

   ```dotenv
   KINDLE_EMAIL=your_username@kindle.com
   ```

### Approve the Sender Email

Amazon only delivers documents from approved sender addresses. You must add the email address InstaKindle will send from:

1. Go to [Amazon – Manage Your Content and Devices → Preferences](https://www.amazon.com/hz/mycd/myx#/home/settings/)
2. Scroll down to **Personal Document Settings**
3. Under **Approved Personal Document E-mail List**, click **Add a new approved e-mail address**
4. Enter the email address you will use as `SENDER_EMAIL` (e.g. your Gmail address)

## Setting Up Email (SMTP)

InstaKindle needs an SMTP server to send ebooks to your Kindle. **Gmail with an App Password** is the easiest option and works well with Docker/server deployments.

### Gmail Setup

Gmail provides free, standard SMTP access — no extra apps required.

#### Create a Gmail Account (skip if you already have one)

1. Go to **https://accounts.google.com/signup** and create an account
2. You now have a `yourname@gmail.com` address

#### Enable 2-Step Verification

App Passwords require 2-Step Verification to be enabled:

1. Go to [Google Account → Security](https://myaccount.google.com/security)
2. Under **How you sign in to Google**, click **2-Step Verification**
3. Follow the prompts to enable it

#### Create an App Password

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Enter a name (e.g. "InstaKindle") and click **Create**
3. Google will display a 16-character password — copy it immediately (you won't see it again)
4. Set these values in your `.env` file:

   ```dotenv
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=yourname@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   SENDER_EMAIL=yourname@gmail.com
   ```

## Building the Docker Image

### Local Build

```bash
docker build -t instakindle .
```

## Publishing to GitHub Container Registry

This section walks you through publishing InstaKindle to [GitHub Container Registry (ghcr.io)](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) — from authenticating to pushing your first image.

GHCR is GitHub's built-in container registry. Images are stored alongside your code, authentication uses your existing GitHub credentials, and there are no pull rate limits for public images.

### 1. Create a Personal Access Token (PAT)

To push images from the CLI, you need a GitHub Personal Access Token with the `write:packages` scope:

1. Go to **https://github.com/settings/tokens?type=beta** (fine-grained tokens) or **https://github.com/settings/tokens/new** (classic tokens)
2. For a **classic token**, select the `write:packages` and `read:packages` scopes
3. Click **Generate token** and **copy it immediately** — it won't be shown again

### 2. Log in from the CLI

```bash
echo YOUR_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

You should see:

```
Login Succeeded
```

### 3. Build the Image Locally

From the root of the InstaKindle project directory:

```bash
docker build -t ghcr.io/YOUR_GITHUB_USERNAME/instakindle:latest .
```

### 4. Tag with a Version

```bash
docker tag ghcr.io/YOUR_GITHUB_USERNAME/instakindle:latest ghcr.io/YOUR_GITHUB_USERNAME/instakindle:1.0.0
```

**Semantic versioning convention:** It's common to push multiple tags for the same image so users can pin to the level of specificity they want:

| Tag | Meaning |
|---|---|
| `:latest` | Most recent build (mutable — moves with each push) |
| `:1.0.0` | Exact version (immutable) |
| `:1.0` | Latest patch in the 1.0.x line |
| `:1` | Latest minor/patch in the 1.x.x line |

### 5. Push to GHCR

```bash
docker push ghcr.io/YOUR_GITHUB_USERNAME/instakindle:latest
docker push ghcr.io/YOUR_GITHUB_USERNAME/instakindle:1.0.0
```

The repository is auto-created on first push. Verify the published image in your repo's **Packages** tab on GitHub.

> **Note:** By default, newly pushed packages inherit the repository's visibility. You can change visibility in **Package settings** on GitHub.

### 6. Multi-platform Builds (Optional)

By default, `docker build` creates an image only for your machine's architecture. If you want your image to run on multiple platforms (e.g. `amd64` servers **and** `arm64` devices like Raspberry Pi or Apple Silicon Macs), use Docker Buildx:

```bash
docker buildx create --name multiarch --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/YOUR_GITHUB_USERNAME/instakindle:latest \
  -t ghcr.io/YOUR_GITHUB_USERNAME/instakindle:1.0.0 \
  --push .
```

> **Note:** The `--push` flag is required with multi-platform builds because the resulting image is pushed directly to the registry (it cannot be stored in the local Docker daemon).

### 7. Automated Publishing via GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that automatically builds and pushes multi-platform Docker images when you create a release.

**No secrets to configure** — the workflow uses the automatic `GITHUB_TOKEN` provided by GitHub Actions, which has `packages:write` permission.

#### Workflow overview

The workflow triggers on:

- **Release published** — when you create a new release on GitHub
- **Manual dispatch** — you can trigger it manually from the Actions tab

Here is the full workflow YAML (`.github/workflows/docker-publish.yml`):

```yaml
name: Publish Docker Image

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      tag:
        description: "Docker image tag (e.g., latest, 1.0.0)"
        required: true
        default: "latest"

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  publish:
    name: Build & Push to GHCR
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=raw,value=latest,enable=${{ github.event_name == 'release' }}
            type=raw,value=${{ github.event.inputs.tag }},enable=${{ github.event_name == 'workflow_dispatch' }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

#### How it works

1. **Create a release** on GitHub with a semantic version tag (e.g. `v1.0.0`)
2. The workflow automatically:
   - Builds images for `linux/amd64` and `linux/arm64`
   - Tags them with semantic version variants (`1.0.0`, `1.0`, `1`, `latest`)
   - Pushes all tags to GitHub Container Registry
3. Verify the published image in your repo's **Packages** tab on GitHub

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
  ghcr.io/onexey/instakindle
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

## Monitoring

- Check container status: `docker ps`
- View logs: `docker logs -f instakindle`
- The container includes a healthcheck that verifies the Python module loads correctly

## Troubleshooting

- **Authentication errors**: Verify your Instapaper OAuth credentials. Note that the Instapaper API requires a paid subscription.
- **SMTP errors**: Check your SMTP credentials and ensure your sender email is approved in your Amazon account's Send-to-Kindle settings.
- **Kindle not receiving**: Make sure the sender email is in your Amazon approved email list at [amazon.com/manageyourkindle](https://www.amazon.com/manageyourkindle).
