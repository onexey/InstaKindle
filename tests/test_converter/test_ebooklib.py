"""Tests for the ebooklib-based converter."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from instakindle.converter.ebooklib_converter import (
    EbooklibConverter,
    _guess_media_type,
    _sanitize_filename,
)
from instakindle.instapaper import Article


class TestEbooklibConverter:
    """Tests for the EbooklibConverter."""

    def test_is_available(self) -> None:
        """EbooklibConverter should always be available."""
        assert EbooklibConverter.is_available()

    def test_convert_simple_html(self, sample_article: Article, sample_html_no_images: str) -> None:
        """Should convert simple HTML to a valid EPUB file."""
        converter = EbooklibConverter()
        result = converter.convert(sample_article, sample_html_no_images)

        assert result.success
        assert result.epub_path.exists()
        assert result.epub_path.suffix == ".epub"
        assert result.title == sample_article.title

        # Verify it's a valid ZIP (EPUB is a ZIP archive)
        assert zipfile.is_zipfile(result.epub_path)

    @patch("instakindle.converter.base.requests.get")
    def test_convert_with_images(self, mock_get: MagicMock, sample_article: Article) -> None:
        """Should handle HTML with images."""
        mock_response = MagicMock()
        mock_response.content = b"fake_png_data"
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        html = """
        <p>Text with image</p>
        <img src="https://example.com/photo.png" alt="photo">
        <p>More text</p>
        """
        converter = EbooklibConverter()
        result = converter.convert(sample_article, html)

        assert result.success
        assert result.epub_path.exists()

    def test_convert_empty_html(self, sample_article: Article) -> None:
        """Should handle empty HTML gracefully."""
        converter = EbooklibConverter()
        result = converter.convert(sample_article, "")
        assert result.success  # Empty content is still valid

    def test_convert_preserves_code_blocks(self, sample_article: Article) -> None:
        """Should preserve code blocks in the output."""
        html = "<pre><code>def main():\n    pass</code></pre>"
        converter = EbooklibConverter()
        result = converter.convert(sample_article, html)

        assert result.success
        # Read the EPUB and check code is preserved
        with zipfile.ZipFile(result.epub_path, "r") as zf:
            content_files = [n for n in zf.namelist() if n.endswith(".xhtml")]
            assert len(content_files) > 0
            content = zf.read(content_files[0]).decode("utf-8")
            assert "def main()" in content

    def test_convert_special_characters_in_title(self) -> None:
        """Should handle special characters in article titles."""
        article = Article(
            bookmark_id=1,
            title='Article: "Why <code> matters" & more',
            url="https://example.com",
        )
        converter = EbooklibConverter()
        result = converter.convert(article, "<p>Content</p>")
        assert result.success

    @patch("instakindle.converter.base.requests.get")
    def test_convert_removes_non_embeddable_images_from_epub(
        self, mock_get: MagicMock, sample_article: Article
    ) -> None:
        """Broken or remote-only image references should not remain in the EPUB XHTML."""
        mock_get.side_effect = requests.ConnectionError("Network error")

        html = """
        <p>Relative image</p>
        <img src="/media/cover.png" alt="relative">
        <p>Missing image source</p>
        <img alt="missing">
        <p>Broken remote image</p>
        <img src="https://example.com/broken.png" alt="broken remote">
        """
        converter = EbooklibConverter()
        result = converter.convert(sample_article, html)

        assert result.success

        with zipfile.ZipFile(result.epub_path, "r") as zf:
            content_files = [
                name
                for name in zf.namelist()
                if name.endswith(".xhtml") and not name.endswith("nav.xhtml")
            ]
            assert len(content_files) == 1
            content = zf.read(content_files[0]).decode("utf-8")

        assert "<img" not in content
        assert "/media/cover.png" not in content
        assert "https://example.com/broken.png" not in content


class TestGuessMediaType:
    """Tests for _guess_media_type helper."""

    def test_jpg(self) -> None:
        assert _guess_media_type(Path("image.jpg")) == "image/jpeg"

    def test_png(self) -> None:
        assert _guess_media_type(Path("image.png")) == "image/png"

    def test_gif(self) -> None:
        assert _guess_media_type(Path("image.gif")) == "image/gif"

    def test_unknown(self) -> None:
        assert _guess_media_type(Path("image.bmp")) == "image/jpeg"


class TestSanitizeFilename:
    """Tests for _sanitize_filename helper."""

    def test_ascii_apostrophe_replaced(self) -> None:
        """Apostrophe in title should be replaced to avoid MIME/delivery issues."""
        result = _sanitize_filename("Why I'm Not Worried")
        assert "'" not in result
        assert result == "Why I_m Not Worried"

    def test_curly_apostrophe_replaced(self) -> None:
        """Smart/curly apostrophe (\u2019) should be replaced."""
        result = _sanitize_filename("Why I\u2019m Not Worried")
        assert "\u2019" not in result
        assert result == "Why I_m Not Worried"

    def test_curly_quotes_replaced(self) -> None:
        """Smart/curly double quotes should be replaced."""
        result = _sanitize_filename("Say \u201cHello\u201d")
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert result == "Say _Hello_"

    def test_original_characters_still_replaced(self) -> None:
        """Original set of dangerous filename characters should still be replaced."""
        result = _sanitize_filename('File: "name" <tag> | test?')
        assert result == "File_ _name_ _tag_ _ test_"

    def test_realistic_title_with_apostrophe(self) -> None:
        """Regression test for the exact title from the reported issue."""
        title = "Why I\u2019m Not Worried About Running Out of Work in the Age of AI"
        result = _sanitize_filename(title)
        assert "'" not in result
        assert "\u2019" not in result
        assert "I_m" in result

    def test_em_dash_is_normalized_to_ascii_hyphen(self) -> None:
        """Unicode dash punctuation should not force RFC2231 attachment filenames."""
        title = (
            "Identifying Necessary Transparency Moments In Agentic AI (Part 1) — Smashing Magazine"
        )
        result = _sanitize_filename(title)
        assert result == (
            "Identifying Necessary Transparency Moments In Agentic AI (Part 1) - Smashing Magazine"
        )
        assert all(ord(char) < 128 for char in result)
