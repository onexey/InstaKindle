"""Tests for the Instapaper API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from instakindle.instapaper import Article, InstapaperClient, InstapaperError


class TestArticle:
    """Tests for the Article dataclass."""

    def test_from_api_full_data(self) -> None:
        """Article.from_api should parse complete API data."""
        data = {
            "type": "bookmark",
            "bookmark_id": 42,
            "title": "Great Article",
            "url": "https://example.com/great",
            "description": "A great read",
            "author": "Jane Doe",
        }
        article = Article.from_api(data)
        assert article.bookmark_id == 42
        assert article.title == "Great Article"
        assert article.url == "https://example.com/great"
        assert article.author == "Jane Doe"

    def test_from_api_minimal_data(self) -> None:
        """Article.from_api should handle missing fields gracefully."""
        data = {"type": "bookmark", "bookmark_id": 1}
        article = Article.from_api(data)
        assert article.bookmark_id == 1
        assert article.title == "Untitled"
        assert article.url == ""

    def test_from_api_empty_dict(self) -> None:
        """Article.from_api should handle empty dict."""
        article = Article.from_api({})
        assert article.bookmark_id == 0
        assert article.title == "Untitled"


class TestInstapaperClient:
    """Tests for the InstapaperClient."""

    def _make_client(
        self, session: requests.Session | None = None
    ) -> InstapaperClient:
        return InstapaperClient(
            consumer_key="test_key",
            consumer_secret="test_secret",
            username="user@test.com",
            password="password123",
            session=session,
        )

    def test_not_authenticated_initially(self) -> None:
        """Client should not be authenticated before calling authenticate()."""
        client = self._make_client()
        assert not client.is_authenticated

    def test_authenticate_success(self) -> None:
        """Successful authentication should set OAuth tokens."""
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.text = "oauth_token=abc123&oauth_token_secret=def456"
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        assert client.is_authenticated

    def test_authenticate_http_error(self) -> None:
        """Authentication should raise InstapaperError on HTTP errors."""
        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.side_effect = requests.HTTPError("401 Unauthorized")

        client = self._make_client(session=mock_session)
        with pytest.raises(InstapaperError, match="Authentication failed"):
            client.authenticate()

    def test_authenticate_missing_tokens(self) -> None:
        """Authentication should raise error when tokens are missing."""
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock()
        mock_response.text = "unexpected_response"
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        client = self._make_client(session=mock_session)
        with pytest.raises(InstapaperError, match="missing tokens"):
            client.authenticate()

    def test_get_bookmarks(self) -> None:
        """get_bookmarks should parse API response into Articles."""
        mock_session = MagicMock(spec=requests.Session)

        # First call: authenticate
        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()

        # Second call: get bookmarks
        bookmarks_response = MagicMock()
        bookmarks_response.json.return_value = [
            {"type": "meta"},
            {"type": "bookmark", "bookmark_id": 1, "title": "Article 1", "url": "https://a.com"},
            {"type": "bookmark", "bookmark_id": 2, "title": "Article 2", "url": "https://b.com"},
        ]
        bookmarks_response.raise_for_status = MagicMock()

        mock_session.post.return_value = auth_response
        client = self._make_client(session=mock_session)
        client.authenticate()

        mock_session.request.return_value = bookmarks_response
        articles = client.get_bookmarks()

        assert len(articles) == 2
        assert articles[0].title == "Article 1"
        assert articles[1].bookmark_id == 2

    def test_get_article_html(self) -> None:
        """get_article_html should return HTML content."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        html_response = MagicMock()
        html_response.text = "<p>Article content</p>"
        html_response.raise_for_status = MagicMock()
        mock_session.post.return_value = html_response

        html = client.get_article_html(12345)
        assert "<p>Article content</p>" in html

    def test_api_request_not_authenticated(self) -> None:
        """API requests should fail if not authenticated."""
        client = self._make_client()
        with pytest.raises(InstapaperError, match="Not authenticated"):
            client.get_bookmarks()

    def test_tag_bookmark_failure_is_warning(self) -> None:
        """Tagging failure should log warning but not raise."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        mock_session.request.side_effect = requests.HTTPError("403 Forbidden")

        # Should not raise — tagging failure is non-fatal
        client.tag_bookmark(123, "sent-to-kindle")

    def test_archive_bookmark(self) -> None:
        """archive_bookmark should make the correct API call."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        archive_response = MagicMock()
        archive_response.json.return_value = []
        archive_response.raise_for_status = MagicMock()
        mock_session.request.return_value = archive_response

        client.archive_bookmark(123)
        mock_session.request.assert_called_once()
        call_args = mock_session.request.call_args
        assert "bookmarks/archive" in call_args[0][1]
