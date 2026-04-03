"""Tests for the ebooklib-based converter."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from instakindle.converter.ebooklib_converter import EbooklibConverter, _guess_media_type
from instakindle.instapaper import Article


class TestEbooklibConverter:
    """Tests for the EbooklibConverter."""

    def test_is_available(self) -> None:
        """EbooklibConverter should always be available."""
        assert EbooklibConverter.is_available()

    def test_convert_simple_html(
        self, sample_article: Article, sample_html_no_images: str
    ) -> None:
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
    def test_convert_with_images(
        self, mock_get: MagicMock, sample_article: Article
    ) -> None:
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
        html = '<pre><code>def main():\n    pass</code></pre>'
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
