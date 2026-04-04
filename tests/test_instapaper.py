"""Tests for the Instapaper API client."""

from __future__ import annotations

from unittest.mock import MagicMock

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

    def _make_client(self, session: requests.Session | None = None) -> InstapaperClient:
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

        # Second call: get bookmarks (list format)
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

    def test_get_bookmarks_dict_format(self) -> None:
        """get_bookmarks should handle dict response with 'bookmarks' key."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        bookmarks_response = MagicMock()
        bookmarks_response.json.return_value = {
            "user": {"type": "user", "user_id": 123},
            "bookmarks": [
                {"type": "bookmark", "bookmark_id": 1, "title": "Article 1", "url": "https://a.com"},
                {"type": "bookmark", "bookmark_id": 2, "title": "Article 2", "url": "https://b.com"},
            ],
            "highlights": [],
        }
        bookmarks_response.raise_for_status = MagicMock()
        mock_session.request.return_value = bookmarks_response

        articles = client.get_bookmarks()

        assert len(articles) == 2
        assert articles[0].title == "Article 1"
        assert articles[1].bookmark_id == 2

    def test_get_bookmarks_error_response(self) -> None:
        """get_bookmarks should raise InstapaperError when API returns error dict."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        error_response = MagicMock()
        error_response.json.return_value = {"error": 1241, "message": "Invalid or missing bookmark_id"}
        error_response.raise_for_status = MagicMock()
        mock_session.request.return_value = error_response

        with pytest.raises(InstapaperError, match="API returned error"):
            client.get_bookmarks()

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

    def test_tag_bookmark_correct_endpoint(self) -> None:
        """tag_bookmark should use the /bookmarks/{id}/tags/add endpoint."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        tag_response = MagicMock()
        tag_response.json.return_value = []
        tag_response.raise_for_status = MagicMock()
        mock_session.request.return_value = tag_response

        client.tag_bookmark(123, "sent-to-kindle")
        mock_session.request.assert_called_once()
        call_args = mock_session.request.call_args
        assert "bookmarks/123/tags/add" in call_args[0][1]
        assert call_args[1]["data"] == {"tag": "sent-to-kindle"}

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

    def test_get_or_create_folder_existing(self) -> None:
        """get_or_create_folder should return ID of an existing folder."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        list_response = MagicMock()
        list_response.json.return_value = [
            {"type": "folder", "folder_id": 99, "title": "InstaKindle"},
        ]
        list_response.raise_for_status = MagicMock()
        mock_session.request.return_value = list_response

        folder_id = client.get_or_create_folder("InstaKindle")
        assert folder_id == "99"

    def test_get_or_create_folder_creates_new(self) -> None:
        """get_or_create_folder should create a folder when it doesn't exist."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        list_response = MagicMock()
        list_response.json.return_value = []
        list_response.raise_for_status = MagicMock()

        create_response = MagicMock()
        create_response.json.return_value = [
            {"type": "folder", "folder_id": 101, "title": "InstaKindle"},
        ]
        create_response.raise_for_status = MagicMock()

        mock_session.request.side_effect = [list_response, create_response]

        folder_id = client.get_or_create_folder("InstaKindle")
        assert folder_id == "101"

    def test_get_or_create_folder_cached(self) -> None:
        """get_or_create_folder should use cached ID on second call."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        list_response = MagicMock()
        list_response.json.return_value = [
            {"type": "folder", "folder_id": 99, "title": "InstaKindle"},
        ]
        list_response.raise_for_status = MagicMock()
        mock_session.request.return_value = list_response

        client.get_or_create_folder("InstaKindle")
        client.get_or_create_folder("InstaKindle")
        # Only one API call — second hit the cache
        mock_session.request.assert_called_once()

    def test_move_bookmark(self) -> None:
        """move_bookmark should call the correct endpoint."""
        mock_session = MagicMock(spec=requests.Session)

        auth_response = MagicMock()
        auth_response.text = "oauth_token=tok&oauth_token_secret=sec"
        auth_response.raise_for_status = MagicMock()
        mock_session.post.return_value = auth_response

        client = self._make_client(session=mock_session)
        client.authenticate()

        move_response = MagicMock()
        move_response.json.return_value = []
        move_response.raise_for_status = MagicMock()
        mock_session.request.return_value = move_response

        client.move_bookmark(123, "99")
        mock_session.request.assert_called_once()
        call_args = mock_session.request.call_args
        assert "bookmarks/move" in call_args[0][1]
        assert call_args[1]["data"] == {"bookmark_id": "123", "folder_id": "99"}
