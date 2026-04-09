"""EbookLib-based converter (pure Python, no system dependencies)."""

from __future__ import annotations

import logging
import unicodedata
import uuid
from typing import TYPE_CHECKING, cast

from bs4 import BeautifulSoup
from ebooklib import epub

from instakindle.converter.base import ConversionResult, Converter

if TYPE_CHECKING:
    from pathlib import Path

    from instakindle.instapaper import Article

logger = logging.getLogger(__name__)

# CSS for clean e-ink reading
_EBOOK_CSS = """\
body {
    font-family: serif;
    line-height: 1.6;
    margin: 1em;
}
h1, h2, h3, h4, h5, h6 {
    font-family: sans-serif;
    line-height: 1.3;
}
pre, code {
    font-family: monospace;
    font-size: 0.9em;
}
pre {
    background: #f4f4f4;
    padding: 1em;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    border: 1px solid #ddd;
}
img {
    max-width: 100%;
    height: auto;
}
blockquote {
    border-left: 3px solid #ccc;
    padding-left: 1em;
    margin-left: 0;
    color: #555;
    font-style: italic;
}
a {
    color: #1a5276;
    text-decoration: underline;
}
table {
    border-collapse: collapse;
    width: 100%;
}
th, td {
    border: 1px solid #ddd;
    padding: 0.5em;
    text-align: left;
}
"""


class EbooklibConverter(Converter):
    """Convert HTML to EPUB using the ebooklib Python library.

    This is the lightest option — no system dependencies required.
    """

    @staticmethod
    def is_available() -> bool:
        """EbookLib is always available (it's a Python dependency)."""
        return True

    def convert(self, article: Article, html: str) -> ConversionResult:
        """Convert article HTML to EPUB using ebooklib.

        Args:
            article: The article metadata.
            html: The HTML content of the article.

        Returns:
            ConversionResult with the path to the generated EPUB.
        """
        work_dir = self.create_temp_dir()
        epub_path = work_dir / f"{_sanitize_filename(article.title)}.epub"

        try:
            # Download images
            updated_html, image_map = self.download_images(html, work_dir)

            # Create the EPUB book
            book = epub.EpubBook()

            # Set metadata
            book_id = str(uuid.uuid4())
            book.set_identifier(book_id)
            book.set_title(article.title)
            book.set_language("en")

            if article.author:
                book.add_author(article.author)

            if article.url:
                book.add_metadata("DC", "source", article.url)

            # Add CSS stylesheet
            style = epub.EpubItem(
                uid="style",
                file_name="style/default.css",
                media_type="text/css",
                content=_EBOOK_CSS.encode("utf-8"),
            )
            book.add_item(style)

            # Add images to the EPUB
            epub_images: list[epub.EpubImage] = []
            soup = BeautifulSoup(updated_html, "html.parser")

            for _original_url, local_path in image_map.items():
                image_filename = f"images/{local_path.name}"
                media_type = _guess_media_type(local_path)

                epub_image = epub.EpubImage()
                epub_image.file_name = image_filename
                epub_image.media_type = media_type
                epub_image.content = local_path.read_bytes()
                book.add_item(epub_image)
                epub_images.append(epub_image)

                # Update image src in HTML to point to EPUB-relative path
                for img_tag in soup.find_all("img", src=str(local_path)):
                    img_tag["src"] = image_filename

            # Create the chapter
            chapter_html = str(soup)
            chapter_content = f"<h1>{article.title}</h1>\n{chapter_html}"

            chapter = epub.EpubHtml(
                title=article.title,
                file_name="content.xhtml",
                lang="en",
            )
            chapter.content = chapter_content.encode("utf-8")
            chapter.add_item(style)
            book.add_item(chapter)

            # Set table of contents and spine
            book.toc = [chapter]
            book.spine = ["nav", chapter]

            # Add navigation files (required by EPUB spec)
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Write the EPUB file
            epub.write_epub(str(epub_path), book, {})

            logger.info("EbookLib conversion successful: %s", epub_path)
            return ConversionResult(
                epub_path=epub_path,
                title=article.title,
                success=True,
            )

        except Exception as e:
            logger.exception("Unexpected error during EbookLib conversion")
            return ConversionResult(
                epub_path=epub_path,
                title=article.title,
                success=False,
                error=str(e),
            )


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Characters unsafe for filenames or MIME Content-Disposition headers.
    # ASCII apostrophes are also replaced because they have caused Kindle
    # delivery failures in generated email attachment headers.
    _unsafe = set("<>:\"/\\|?*'")
    translated = name.translate(
        str.maketrans(
            cast(
                "dict[int, str | int | None]",
                {
                    0x2010: "-",
                    0x2011: "-",
                    0x2012: "-",
                    0x2013: "-",
                    0x2014: "-",
                    0x2015: "-",
                    0x2212: "-",
                },
            )
        )
    )
    normalized = unicodedata.normalize("NFKD", translated)
    sanitized = "".join(
        "_" if ord(char) < 32 or ord(char) > 127 or char in _unsafe else char
        for char in normalized
        if not unicodedata.combining(char)
    )
    return sanitized[:200].strip().rstrip(".")


def _guess_media_type(path: Path) -> str:
    """Guess MIME type from file extension."""
    ext_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    return ext_map.get(path.suffix.lower(), "image/jpeg")
