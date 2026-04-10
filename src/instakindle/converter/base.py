"""Base converter interface and shared types for ebook conversion."""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup

from instakindle.retry import retry

if TYPE_CHECKING:
    from instakindle.instapaper import Article

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of an ebook conversion."""

    epub_path: Path
    title: str
    success: bool
    error: str = ""


class Converter(ABC):
    """Abstract base class for ebook converters.

    Subclasses must implement `convert_html_to_epub`.
    """

    @abstractmethod
    def convert(self, article: Article, html: str) -> ConversionResult:
        """Convert article HTML to EPUB.

        Args:
            article: The article metadata.
            html: The HTML content of the article.

        Returns:
            ConversionResult with the path to the generated EPUB file.
        """

    @staticmethod
    def download_images(html: str, output_dir: Path) -> tuple[str, dict[str, Path]]:
        """Download images referenced in HTML and return updated HTML + image map.

        Args:
            html: The original HTML content.
            output_dir: Directory to save downloaded images.

        Returns:
            Tuple of (updated HTML with local image paths, dict of URL -> local path).
        """
        soup = BeautifulSoup(html, "html.parser")
        image_map: dict[str, Path] = {}

        for idx, img in enumerate(soup.find_all("img")):
            src = img.get("src", "")
            if not src or not src.startswith(("http://", "https://")):
                logger.debug("Removing non-embeddable image with src=%r", src)
                img.decompose()
                continue

            try:
                response = _download_image(src)

                # Determine file extension from content type
                content_type = response.headers.get("content-type", "image/jpeg")
                ext = _extension_from_content_type(content_type)
                filename = f"image_{idx}{ext}"
                local_path = output_dir / filename

                local_path.write_bytes(response.content)
                image_map[src] = local_path
                img["src"] = str(local_path)
                logger.debug("Downloaded image: %s -> %s", src, local_path)
            except requests.RequestException:
                logger.warning("Failed to download image: %s", src)
                img.decompose()

        return str(soup), image_map

    @staticmethod
    def create_temp_dir() -> Path:
        """Create a temporary directory for conversion artifacts."""
        return Path(tempfile.mkdtemp(prefix="instakindle_"))


_TRANSIENT_EXCEPTIONS = (requests.ConnectionError, requests.Timeout)


@retry(max_attempts=3, backoff_factor=2.0, exceptions=_TRANSIENT_EXCEPTIONS)
def _download_image(url: str) -> requests.Response:
    """Download a single image with retry on transient failures.

    Only connection errors and timeouts are retried; permanent HTTP errors
    (e.g. 404, 401) are raised immediately.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response


def _extension_from_content_type(content_type: str) -> str:
    """Map content type to file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    # Handle content types with parameters (e.g., "image/jpeg; charset=utf-8")
    base_type = content_type.split(";")[0].strip().lower()
    return mapping.get(base_type, ".jpg")
