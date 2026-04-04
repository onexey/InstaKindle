"""Main pipeline: fetch → convert → send → move → repeat."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from instakindle.converter.ebooklib_converter import EbooklibConverter
from instakindle.instapaper import Article, InstapaperClient, InstapaperError
from instakindle.sender import KindleSender, SenderError

if TYPE_CHECKING:
    from instakindle.config import Config

logger = logging.getLogger(__name__)

SENT_FOLDER = "InstaKindle"
MAX_CONSECUTIVE_FAILURES = 10
_MAX_BACKOFF_SECONDS = 3600  # 1 hour
_MAX_BACKOFF_EXPONENT = 4
HEALTHCHECK_FILE = Path("/tmp/instakindle_last_success")


class PipelineIterationError(Exception):
    """All articles in a pipeline iteration failed to process."""


class PipelineShutdownError(Exception):
    """Circuit breaker tripped after too many consecutive failures."""


class Pipeline:
    """Orchestrates the InstaKindle pipeline.

    Fetch → Convert → Send → Move to folder → Repeat
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = InstapaperClient(
            consumer_key=config.instapaper_key,
            consumer_secret=config.instapaper_secret,
            username=config.instapaper_username,
            password=config.instapaper_password,
        )
        self._converter = EbooklibConverter()
        self._sender = KindleSender(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_username=config.smtp_username,
            smtp_password=config.smtp_password,
            sender_email=config.sender_email,
            kindle_email=config.kindle_email,
        )

    def run_forever(self) -> None:
        """Run the pipeline in a continuous loop.

        Uses exponential backoff on repeated failures and shuts down after
        ``MAX_CONSECUTIVE_FAILURES`` consecutive errors to avoid wasting
        resources on known-broken configurations.
        """
        logger.info(
            "Starting InstaKindle pipeline (poll_interval=%ds)",
            self._config.poll_interval,
        )

        # Authenticate once at startup
        self._client.authenticate()

        consecutive_failures = 0

        while True:
            try:
                self.run_once()
                consecutive_failures = 0
                _write_healthcheck(self._config.poll_interval)
            except PipelineIterationError:
                consecutive_failures += 1
                logger.warning(
                    "Pipeline iteration failed — all articles failed (%d/%d)",
                    consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                )
            except InstapaperError:
                consecutive_failures += 1
                logger.exception(
                    "Instapaper API error (%d/%d)",
                    consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                )
            except Exception:
                consecutive_failures += 1
                logger.exception(
                    "Unexpected error (%d/%d)",
                    consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                )

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.critical(
                    "Exceeded %d consecutive failures, shutting down",
                    MAX_CONSECUTIVE_FAILURES,
                )
                raise PipelineShutdownError(consecutive_failures)

            if consecutive_failures > 0:
                backoff = self._config.poll_interval * (
                    2 ** min(consecutive_failures, _MAX_BACKOFF_EXPONENT)
                )
                sleep_seconds = min(backoff, _MAX_BACKOFF_SECONDS)
            else:
                sleep_seconds = self._config.poll_interval
            logger.info("Sleeping for %d seconds...", sleep_seconds)
            time.sleep(sleep_seconds)

    def run_once(self) -> int:
        """Run a single iteration of the pipeline.

        Returns:
            Number of articles successfully processed.

        Raises:
            PipelineIterationError: If articles were found but none could be
                processed successfully (e.g., persistent conversion or
                sending failures).
        """
        articles = self._client.get_bookmarks()

        if not articles:
            logger.info("No unread articles found")
            return 0

        logger.info("Processing %d articles...", len(articles))
        success_count = 0

        for article in articles:
            if self._process_article(article):
                success_count += 1

        logger.info("Processed %d/%d articles successfully", success_count, len(articles))

        if success_count == 0:
            msg = f"All {len(articles)} articles failed to process"
            raise PipelineIterationError(msg)

        return success_count

    def _process_article(self, article: Article) -> bool:
        """Process a single article through the full pipeline.

        Returns:
            True if the article was successfully processed.
        """
        logger.info("Processing: '%s' (%s)", article.title, article.url)

        try:
            # Step 1: Fetch HTML
            article_html = self._client.get_article_html(article.bookmark_id)

            if not article_html:
                logger.warning("Empty HTML for article '%s', skipping", article.title)
                return False

            # Step 2: Convert to EPUB
            result = self._converter.convert(article, article_html)
            if not result.success:
                logger.error("Conversion failed for '%s': %s", article.title, result.error)
                return False

            try:
                # Step 3: Send to Kindle
                self._sender.send_epub(result.epub_path, article.title)

                # Step 4: Move to InstaKindle folder (removes from unread)
                folder_id = self._client.get_or_create_folder(SENT_FOLDER)
                self._client.move_bookmark(article.bookmark_id, folder_id)

                logger.info("Successfully processed: '%s'", article.title)
                return True

            finally:
                # Clean up temporary files
                self._cleanup(result.epub_path.parent)

        except (InstapaperError, SenderError):
            logger.exception("Failed to process article '%s'", article.title)
            return False
        except Exception:
            logger.exception("Unexpected error processing article '%s'", article.title)
            return False

    @staticmethod
    def _cleanup(directory: Path) -> None:
        """Remove temporary conversion directory."""
        try:
            temp_root = str(Path(tempfile.gettempdir()).resolve())
            if directory.exists() and str(directory.resolve()).startswith(temp_root):
                shutil.rmtree(directory)
                logger.debug("Cleaned up temp directory: %s", directory)
        except OSError:
            logger.warning("Failed to clean up temp directory: %s", directory)


def _write_healthcheck(poll_interval: int) -> None:
    """Write current timestamp and poll interval to the healthcheck file.

    The file contains ``<timestamp> <poll_interval>`` so the Docker
    healthcheck can derive a staleness threshold from the effective
    poll interval, even when it differs from the ``POLL_INTERVAL`` env var.

    Uses atomic write (temp file + rename) so that concurrent readers
    (e.g. Docker healthcheck) never see a partially written file.
    """
    try:
        fd, tmp_path = tempfile.mkstemp(dir=HEALTHCHECK_FILE.parent, prefix=".hc_tmp_")
        try:
            with open(fd, "w") as f:
                f.write(f"{time.time()} {poll_interval}")
            Path(tmp_path).rename(HEALTHCHECK_FILE)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    except OSError as exc:
        logger.warning("Failed to write healthcheck file: %s (%s)", HEALTHCHECK_FILE, exc)
