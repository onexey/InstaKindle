# Deployment Guide

This guide covers how to build, publish, and deploy InstaKindle as a Docker image.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- A [Docker Hub](https://hub.docker.com/) account (for publishing)
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
