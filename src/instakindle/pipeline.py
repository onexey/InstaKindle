"""Main pipeline: fetch → convert → send → tag → archive → repeat."""

from __future__ import annotations

import logging
import shutil
import time
from typing import TYPE_CHECKING

from instakindle.converter.base import Converter, get_converter
from instakindle.instapaper import Article, InstapaperClient, InstapaperError
from instakindle.sender import KindleSender, SenderError

if TYPE_CHECKING:
    from pathlib import Path

    from instakindle.config import Config

logger = logging.getLogger(__name__)

SENT_TAG = "sent-to-kindle"


class Pipeline:
    """Orchestrates the InstaKindle pipeline.

    Fetch → Convert → Send → Tag → Archive → Repeat
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = InstapaperClient(
            consumer_key=config.instapaper_key,
            consumer_secret=config.instapaper_secret,
            username=config.instapaper_username,
            password=config.instapaper_password,
        )
        self._converter: Converter = get_converter(config.converter)
        self._sender = KindleSender(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_username=config.smtp_username,
            smtp_password=config.smtp_password,
            sender_email=config.sender_email,
            kindle_email=config.kindle_email,
        )

    def run_forever(self) -> None:
        """Run the pipeline in a continuous loop."""
        logger.info(
            "Starting InstaKindle pipeline (converter=%s, poll_interval=%ds)",
            self._config.converter,
            self._config.poll_interval,
        )

        # Authenticate once at startup
        self._client.authenticate()

        while True:
            try:
                self.run_once()
            except InstapaperError:
                logger.exception("Instapaper API error during pipeline run")
            except Exception:
                logger.exception("Unexpected error during pipeline run")

            logger.info("Sleeping for %d seconds...", self._config.poll_interval)
            time.sleep(self._config.poll_interval)

    def run_once(self) -> int:
        """Run a single iteration of the pipeline.

        Returns:
            Number of articles successfully processed.
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
        return success_count

    def _process_article(self, article: Article) -> bool:
        """Process a single article through the full pipeline.

        Returns:
            True if the article was successfully processed.
        """
        logger.info("Processing: '%s' (%s)", article.title, article.url)

        try:
            # Step 1: Fetch HTML
            html = self._client.get_article_html(article.bookmark_id)
            if not html:
                logger.warning("Empty HTML for article '%s', skipping", article.title)
                return False

            # Step 2: Convert to EPUB
            result = self._converter.convert(article, html)
            if not result.success:
                logger.error("Conversion failed for '%s': %s", article.title, result.error)
                return False

            try:
                # Step 3: Send to Kindle
                self._sender.send_epub(result.epub_path, article.title)

                # Step 4: Tag the article
                self._client.tag_bookmark(article.bookmark_id, SENT_TAG)

                # Step 5: Archive the article
                self._client.archive_bookmark(article.bookmark_id)

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
            if directory.exists() and str(directory).startswith("/tmp"):
                shutil.rmtree(directory)
                logger.debug("Cleaned up temp directory: %s", directory)
        except OSError:
            logger.warning("Failed to clean up temp directory: %s", directory)
