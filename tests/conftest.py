"""Shared test fixtures for InstaKindle."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from instakindle.config import Config
from instakindle.instapaper import Article


@pytest.fixture()
def sample_article() -> Article:
    """Create a sample article for testing."""
    return Article(
        bookmark_id=12345,
        title="Test Article Title",
        url="https://example.com/article",
        description="A test article description",
        author="Test Author",
    )


@pytest.fixture()
def sample_html() -> str:
    """Return sample HTML content for conversion testing."""
    return """
    <article>
        <h1>Test Article</h1>
        <p>This is a test article with <strong>bold</strong> and <em>italic</em> text.</p>
        <pre><code>def hello():
    print("Hello, World!")</code></pre>
        <blockquote>This is a blockquote.</blockquote>
        <p>Here is an image reference: <img src="https://example.com/image.jpg" alt="test"></p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
    </article>
    """


@pytest.fixture()
def sample_html_no_images() -> str:
    """Return sample HTML without images (no network calls needed)."""
    return """
    <article>
        <h1>Test Article</h1>
        <p>This is a simple article with <strong>bold</strong> text.</p>
        <pre><code>console.log("hello");</code></pre>
        <blockquote>A wise quote.</blockquote>
    </article>
    """


@pytest.fixture()
def sample_config() -> Config:
    """Create a valid sample configuration for testing."""
    return Config(
        instapaper_key="test_consumer_key",
        instapaper_secret="test_consumer_secret",
        instapaper_username="test@example.com",
        instapaper_password="test_password",
        kindle_email="test@kindle.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="smtp_user",
        smtp_password="smtp_pass",
        sender_email="sender@example.com",
        poll_interval=60,
        log_level="info",
        converter="ebooklib",
    )


@pytest.fixture()
def mock_smtp(mocker: MagicMock) -> MagicMock:
    """Mock smtplib.SMTP for sender tests."""
    mock_server = MagicMock()
    mock_smtp_class = mocker.patch("instakindle.sender.smtplib.SMTP")
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)
    return mock_server
