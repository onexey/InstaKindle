"""Tests for the Calibre converter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from instakindle.converter.calibre import CalibreConverter, _sanitize_filename, _wrap_html
from instakindle.instapaper import Article


class TestCalibreConverter:
    """Tests for the CalibreConverter."""

    @patch("shutil.which")
    def test_is_available_when_installed(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/bin/ebook-convert"
        assert CalibreConverter.is_available()

    @patch("shutil.which")
    def test_is_not_available_when_missing(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert not CalibreConverter.is_available()

    @patch("instakindle.converter.calibre.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_success(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
        sample_article: Article,
        sample_html_no_images: str,
    ) -> None:
        """Should call ebook-convert and return success."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        converter = CalibreConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert result.success
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ebook-convert"
        assert "--title" in cmd

    @patch("instakindle.converter.calibre.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_failure(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
        sample_article: Article,
        sample_html_no_images: str,
    ) -> None:
        """Should report failure when ebook-convert returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error!", stdout="")

        converter = CalibreConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert not result.success
        assert "Error!" in result.error

    @patch("instakindle.converter.calibre.subprocess.run")
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

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ebook-convert", timeout=120)

        converter = CalibreConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert not result.success
        assert "timed out" in result.error

    @patch("instakindle.converter.calibre.subprocess.run")
    @patch("instakindle.converter.base.requests.get")
    def test_convert_includes_author(
        self,
        mock_get: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Should include --authors flag when author is set."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        article = Article(bookmark_id=1, title="Test", url="https://example.com", author="John Doe")
        converter = CalibreConverter()
        converter.convert(article, "<p>content</p>")

        cmd = mock_run.call_args[0][0]
        assert "--authors" in cmd
        assert "John Doe" in cmd


class TestSanitizeFilename:
    """Tests for _sanitize_filename helper."""

    def test_removes_special_chars(self) -> None:
        assert '"' not in _sanitize_filename('file"name')
        assert "/" not in _sanitize_filename("file/name")
        assert "?" not in _sanitize_filename("file?name")

    def test_truncates_long_names(self) -> None:
        long_name = "a" * 300
        assert len(_sanitize_filename(long_name)) <= 200


class TestWrapHtml:
    """Tests for _wrap_html helper."""

    def test_wraps_in_html_doc(self) -> None:
        result = _wrap_html("<p>Hello</p>", "Test Title")
        assert "<!DOCTYPE html>" in result
        assert "<title>Test Title</title>" in result
        assert "<p>Hello</p>" in result
        assert "monospace" in result  # CSS should be present

    def test_escapes_html_in_title(self) -> None:
        result = _wrap_html("<p>Body</p>", '<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "<title>&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</title>" in result
        assert "<h1>&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</h1>" in result

    def test_escapes_ampersand_in_title(self) -> None:
        result = _wrap_html("<p>Body</p>", "Tom & Jerry")
        assert "<title>Tom &amp; Jerry</title>" in result
        assert "<h1>Tom &amp; Jerry</h1>" in result
