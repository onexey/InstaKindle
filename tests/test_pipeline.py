"""Tests for the main pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instakindle.config import Config
from instakindle.converter.base import ConversionResult
from instakindle.instapaper import Article, InstapaperError
from instakindle.pipeline import Pipeline, SENT_TAG
from instakindle.sender import SenderError


class TestPipeline:
    """Tests for the Pipeline orchestrator."""

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_no_articles(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
    ) -> None:
        """run_once should return 0 when no articles found."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = []

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_client.get_bookmarks.assert_called_once()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_processes_articles(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should process all articles."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_get_converter.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=True,
        )

        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 1
        mock_client.get_article_html.assert_called_once_with(sample_article.bookmark_id)
        mock_converter.convert.assert_called_once()
        mock_sender.send_epub.assert_called_once()
        mock_client.tag_bookmark.assert_called_once_with(sample_article.bookmark_id, SENT_TAG)
        mock_client.archive_bookmark.assert_called_once_with(sample_article.bookmark_id)

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_conversion_failure(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should skip articles that fail conversion."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_get_converter.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=False,
            error="Conversion error",
        )

        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_sender.send_epub.assert_not_called()
        mock_client.archive_bookmark.assert_not_called()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_empty_html(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """run_once should skip articles with empty HTML."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = ""

        mock_converter = mock_get_converter.return_value
        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_converter.convert.assert_not_called()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_send_failure(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
        sample_article: Article,
    ) -> None:
        """Articles that fail sending should not be tagged/archived."""
        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [sample_article]
        mock_client.get_article_html.return_value = "<p>Content</p>"

        mock_converter = mock_get_converter.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title=sample_article.title,
            success=True,
        )

        mock_sender = mock_sender_cls.return_value
        mock_sender.send_epub.side_effect = SenderError("SMTP failed")

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 0
        mock_client.tag_bookmark.assert_not_called()
        mock_client.archive_bookmark.assert_not_called()

    @patch("instakindle.pipeline.KindleSender")
    @patch("instakindle.pipeline.get_converter")
    @patch("instakindle.pipeline.InstapaperClient")
    def test_run_once_multiple_articles_partial_failure(
        self,
        mock_client_cls: MagicMock,
        mock_get_converter: MagicMock,
        mock_sender_cls: MagicMock,
        sample_config: Config,
    ) -> None:
        """Should continue processing other articles if one fails."""
        article1 = Article(bookmark_id=1, title="Article 1", url="https://a.com")
        article2 = Article(bookmark_id=2, title="Article 2", url="https://b.com")

        mock_client = mock_client_cls.return_value
        mock_client.get_bookmarks.return_value = [article1, article2]
        mock_client.get_article_html.side_effect = [
            InstapaperError("API error"),  # article1 fails
            "<p>Content 2</p>",  # article2 succeeds
        ]

        mock_converter = mock_get_converter.return_value
        mock_converter.convert.return_value = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title="Article 2",
            success=True,
        )

        mock_sender = mock_sender_cls.return_value

        pipeline = Pipeline(sample_config)
        count = pipeline.run_once()

        assert count == 1  # Only article2 succeeded


class TestPipelineCleanup:
    """Tests for pipeline cleanup behavior."""

    def test_cleanup_removes_temp_dir(self, tmp_path: Path) -> None:
        """Should remove temp directories under /tmp."""
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="instakindle_"))
        (temp_dir / "test.epub").write_bytes(b"data")

        Pipeline._cleanup(temp_dir)
        assert not temp_dir.exists()

    def test_cleanup_ignores_non_tmp_dir(self, tmp_path: Path) -> None:
        """Should not remove directories outside /tmp."""
        test_dir = tmp_path / "keep_this"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("keep")

        Pipeline._cleanup(test_dir)
        assert test_dir.exists()
