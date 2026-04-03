"""Calibre ebook-convert based converter."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from instakindle.converter.base import ConversionResult, Converter
from instakindle.instapaper import Article

logger = logging.getLogger(__name__)


class CalibreConverter(Converter):
    """Convert HTML to EPUB using Calibre's ebook-convert CLI tool.

    Requires `ebook-convert` to be installed (from `calibre` package).
    """

    COMMAND = "ebook-convert"

    @classmethod
    def is_available(cls) -> bool:
        """Check if ebook-convert is installed and accessible."""
        return shutil.which(cls.COMMAND) is not None

    def convert(self, article: Article, html: str) -> ConversionResult:
        """Convert article HTML to EPUB using Calibre.

        Args:
            article: The article metadata.
            html: The HTML content of the article.

        Returns:
            ConversionResult with the path to the generated EPUB.
        """
        work_dir = self.create_temp_dir()
        html_path = work_dir / "article.html"
        epub_path = work_dir / f"{_sanitize_filename(article.title)}.epub"

        try:
            # Download images and update HTML references
            updated_html, _images = self.download_images(html, work_dir)

            # Wrap in a full HTML document
            full_html = _wrap_html(updated_html, article.title)
            html_path.write_text(full_html, encoding="utf-8")

            # Build ebook-convert command
            cmd = [
                self.COMMAND,
                str(html_path),
                str(epub_path),
                "--title",
                article.title,
                "--no-default-epub-cover",
                "--chapter",
                "/",  # No chapter detection (single article)
            ]

            if article.author:
                cmd.extend(["--authors", article.author])

            logger.info("Running Calibre conversion for '%s'...", article.title)
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            if result.returncode != 0:
                logger.error("Calibre conversion failed: %s", result.stderr)
                return ConversionResult(
                    epub_path=epub_path,
                    title=article.title,
                    success=False,
                    error=result.stderr,
                )

            logger.info("Calibre conversion successful: %s", epub_path)
            return ConversionResult(
                epub_path=epub_path,
                title=article.title,
                success=True,
            )

        except subprocess.TimeoutExpired:
            error_msg = "Calibre conversion timed out after 120 seconds"
            logger.error(error_msg)
            return ConversionResult(
                epub_path=epub_path,
                title=article.title,
                success=False,
                error=error_msg,
            )
        except Exception as e:
            logger.exception("Unexpected error during Calibre conversion")
            return ConversionResult(
                epub_path=epub_path,
                title=article.title,
                success=False,
                error=str(e),
            )


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Replace common problematic characters
    for char in r'<>:"/\|?*':
        name = name.replace(char, "_")
    # Truncate to reasonable length
    return name[:200].strip().rstrip(".")


def _wrap_html(body_html: str, title: str) -> str:
    """Wrap body HTML in a full HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: serif; line-height: 1.6; margin: 1em; }}
        pre, code {{ font-family: monospace; font-size: 0.9em; }}
        pre {{ background: #f4f4f4; padding: 1em; overflow-x: auto; white-space: pre-wrap; }}
        img {{ max-width: 100%; height: auto; }}
        blockquote {{ border-left: 3px solid #ccc; padding-left: 1em; margin-left: 0; color: #555; }}
    </style>
</head>
<body>
<h1>{title}</h1>
{body_html}
</body>
</html>"""
