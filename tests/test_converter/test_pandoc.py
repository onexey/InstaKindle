"""Tests for the Pandoc converter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from instakindle.converter.pandoc import PandocConverter, _sanitize_filename, _wrap_html
from instakindle.instapaper import Article


class TestPandocConverter:
    """Tests for the PandocConverter."""

    @patch("shutil.which")
    def test_is_available_when_installed(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/pandoc"
        assert PandocConverter.is_available()

    @patch("shutil.which")
    def test_is_not_available_when_missing(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert not PandocConverter.is_available()

    @patch("instakindle.converter.pandoc.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_success(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
        sample_article: Article,
        sample_html_no_images: str,
    ) -> None:
        """Should call pandoc and return success."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        converter = PandocConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert result.success
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "pandoc"
        assert "-f" in cmd
        assert "html" in cmd

    @patch("instakindle.converter.pandoc.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_failure(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
        sample_article: Article,
        sample_html_no_images: str,
    ) -> None:
        """Should report failure when pandoc returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Pandoc error", stdout="")

        converter = PandocConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert not result.success
        assert "Pandoc error" in result.error

    @patch("instakindle.converter.pandoc.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_timeout(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
        sample_article: Article,
        sample_html_no_images: str,
    ) -> None:
        """Should handle timeout gracefully."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pandoc", timeout=120)

        converter = PandocConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert not result.success
        assert "timed out" in result.error

    @patch("instakindle.converter.pandoc.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_includes_metadata(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Should include metadata flags for author."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        article = Article(
            bookmark_id=1, title="Test", url="https://example.com", author="Jane Smith"
        )
        converter = PandocConverter()
        converter.convert(article, "<p>content</p>")

        cmd = mock_run.call_args[0][0]
        assert "--metadata" in cmd
        # Author metadata should be in the command
        metadata_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "--metadata"]
        assert any("author=" in m for m in metadata_args)


class TestSanitizeFilename:
    """Tests for _sanitize_filename helper."""

    def test_removes_special_chars(self) -> None:
        result = _sanitize_filename('title: "test" article?')
        assert '"' not in result
        assert "?" not in result

    def test_truncates(self) -> None:
        assert len(_sanitize_filename("x" * 500)) <= 200


class TestWrapHtml:
    """Tests for _wrap_html helper."""

    def test_wraps_in_html_doc(self) -> None:
        result = _wrap_html("<p>Body</p>", "My Title")
        assert "<!DOCTYPE html>" in result
        assert "<title>My Title</title>" in result
        assert "<p>Body</p>" in result
