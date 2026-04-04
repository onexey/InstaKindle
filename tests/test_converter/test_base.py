"""Tests for the base converter module."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instakindle.converter.base import (
    ConversionResult,
    Converter,
    ConverterType,
    _extension_from_content_type,
    get_converter,
)


def _make_tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="instakindle_test_"))


class TestConverterType:
    """Tests for the ConverterType enum."""

    def test_values(self) -> None:
        assert ConverterType.CALIBRE.value == "calibre"
        assert ConverterType.PANDOC.value == "pandoc"
        assert ConverterType.EBOOKLIB.value == "ebooklib"


class TestConversionResult:
    """Tests for the ConversionResult dataclass."""

    def test_success_result(self) -> None:
        result = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title="Test",
            success=True,
        )
        assert result.success
        assert result.error == ""

    def test_failure_result(self) -> None:
        result = ConversionResult(
            epub_path=Path("/tmp/test.epub"),
            title="Test",
            success=False,
            error="Conversion failed",
        )
        assert not result.success
        assert result.error == "Conversion failed"


class TestExtensionFromContentType:
    """Tests for _extension_from_content_type helper."""

    def test_jpeg(self) -> None:
        assert _extension_from_content_type("image/jpeg") == ".jpg"

    def test_png(self) -> None:
        assert _extension_from_content_type("image/png") == ".png"

    def test_gif(self) -> None:
        assert _extension_from_content_type("image/gif") == ".gif"

    def test_webp(self) -> None:
        assert _extension_from_content_type("image/webp") == ".webp"

    def test_with_charset(self) -> None:
        assert _extension_from_content_type("image/png; charset=utf-8") == ".png"

    def test_unknown_defaults_to_jpg(self) -> None:
        assert _extension_from_content_type("image/bmp") == ".jpg"


class TestDownloadImages:
    """Tests for the Converter.download_images static method."""

    @patch("instakindle.converter.base.requests.get")
    def test_download_images(self, mock_get: MagicMock) -> None:
        """Should download images and update HTML."""
        work_dir = _make_tmp_dir()
        try:
            mock_response = MagicMock()
            mock_response.content = b"fake_image_data"
            mock_response.headers = {"content-type": "image/png"}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            html = '<p>Text <img src="https://example.com/img.png" alt="test"></p>'
            _updated_html, image_map = Converter.download_images(html, work_dir)

            assert len(image_map) == 1
            assert "https://example.com/img.png" in image_map
            local_path = image_map["https://example.com/img.png"]
            assert local_path.exists()
            assert local_path.read_bytes() == b"fake_image_data"
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_no_images(self) -> None:
        """HTML without images should return unchanged."""
        work_dir = _make_tmp_dir()
        try:
            html = "<p>No images here</p>"
            _updated_html, image_map = Converter.download_images(html, work_dir)
            assert len(image_map) == 0
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_relative_images_skipped(self) -> None:
        """Relative image URLs should be skipped."""
        work_dir = _make_tmp_dir()
        try:
            html = '<p><img src="local/image.png"></p>'
            _updated_html, image_map = Converter.download_images(html, work_dir)
            assert len(image_map) == 0
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @patch("instakindle.converter.base.requests.get")
    def test_download_failure_handled(self, mock_get: MagicMock) -> None:
        """Failed image downloads should be handled gracefully."""
        import requests

        work_dir = _make_tmp_dir()
        try:
            mock_get.side_effect = requests.ConnectionError("Network error")

            html = '<p><img src="https://example.com/broken.png"></p>'
            _updated_html, image_map = Converter.download_images(html, work_dir)
            assert len(image_map) == 0
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


class TestGetConverter:
    """Tests for the get_converter factory function."""

    def test_get_ebooklib(self) -> None:
        from instakindle.converter.ebooklib_converter import EbooklibConverter

        converter = get_converter("ebooklib")
        assert isinstance(converter, EbooklibConverter)

    def test_get_calibre(self) -> None:
        from instakindle.converter.calibre import CalibreConverter

        converter = get_converter("calibre")
        assert isinstance(converter, CalibreConverter)

    def test_get_pandoc(self) -> None:
        from instakindle.converter.pandoc import PandocConverter

        converter = get_converter("pandoc")
        assert isinstance(converter, PandocConverter)

    def test_case_insensitive(self) -> None:
        converter = get_converter("EbookLib")
        assert converter is not None

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown converter"):
            get_converter("nonexistent")
