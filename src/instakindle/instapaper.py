"""Instapaper API client.

Implements OAuth 1.0a xAuth authentication and bookmark management.
See: https://www.instapaper.com/api
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests_oauthlib import OAuth1
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://www.instapaper.com/api/1.1"


@dataclass
class Article:
    """Represents an Instapaper bookmark/article."""

    bookmark_id: int
    title: str
    url: str
    description: str = ""
    html: str = ""
    author: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Article:
        """Create an Article from Instapaper API response data."""
        return cls(
            bookmark_id=int(data.get("bookmark_id", 0)),
            title=data.get("title", "Untitled"),
            url=data.get("url", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
        )


class InstapaperError(Exception):
    """Raised when an Instapaper API call fails."""


class InstapaperClient:
    """Client for the Instapaper Full API (OAuth 1.0a with xAuth)."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        username: str,
        password: str,
        *,
        session: requests.Session | None = None,
    ) -> None:
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._username = username
        self._password = password
        self._session = session or self._build_session()
        self._oauth_token: str = ""
        self._oauth_token_secret: str = ""
        self._folder_cache: dict[str, str] = {}  # name -> folder_id

    @staticmethod
    def _build_session() -> requests.Session:
        """Create a requests session with automatic retry on transient errors."""
        session = requests.Session()
        # The Instapaper API uses POST for all endpoints (including read-only
        # ones like /bookmarks/list).  The operations are effectively idempotent
        # (archiving/moving/tagging twice has no extra side effects), so
        # transport-level retries on POST are safe here.
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @property
    def is_authenticated(self) -> bool:
        """Whether the client has obtained OAuth tokens."""
        return bool(self._oauth_token and self._oauth_token_secret)

    def authenticate(self) -> None:
        """Authenticate via xAuth to obtain OAuth access tokens.

        Raises:
            InstapaperError: If authentication fails.
        """
        logger.info("Authenticating with Instapaper API...")
        oauth = OAuth1(self._consumer_key, self._consumer_secret)

        try:
            response = self._session.post(
                f"{BASE_URL}/oauth/access_token",
                auth=oauth,
                data={
                    "x_auth_username": self._username,
                    "x_auth_password": self._password,
                    "x_auth_mode": "client_auth",
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise InstapaperError(f"Authentication failed: {e}") from e

        # Parse the response (URL-encoded: oauth_token=xxx&oauth_token_secret=yyy)
        tokens: dict[str, str] = {}
        for pair in response.text.split("&"):
            if "=" in pair:
                key, _, value = pair.partition("=")
                tokens[key] = value
        self._oauth_token = tokens.get("oauth_token", "")
        self._oauth_token_secret = tokens.get("oauth_token_secret", "")

        if not self._oauth_token or not self._oauth_token_secret:
            raise InstapaperError("Authentication response missing tokens")

        logger.info("Successfully authenticated with Instapaper")

    def _get_auth(self) -> OAuth1:
        """Get the OAuth1 auth handler for authenticated requests."""
        if not self.is_authenticated:
            raise InstapaperError("Not authenticated. Call authenticate() first.")
        return OAuth1(
            self._consumer_key,
            self._consumer_secret,
            self._oauth_token,
            self._oauth_token_secret,
        )

    def _api_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated API request.

        Returns:
            Parsed JSON response.

        Raises:
            InstapaperError: If the request fails.
        """
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        try:
            response = self._session.request(
                method,
                url,
                auth=self._get_auth(),
                data=data or {},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("API response (%s): %s", endpoint, result)
            return result
        except requests.RequestException as e:
            raise InstapaperError(f"API request failed ({endpoint}): {e}") from e

    def get_bookmarks(self, limit: int = 25, folder_id: str = "unread") -> list[Article]:
        """Fetch bookmarks from Instapaper.

        Args:
            limit: Maximum number of bookmarks to retrieve.
            folder_id: Folder to fetch from ("unread", "starred", "archive", or a folder ID).

        Returns:
            List of Article objects.
        """
        logger.info("Fetching up to %d bookmarks from '%s' folder...", limit, folder_id)
        response_data = self._api_request(
            "POST",
            "/bookmarks/list",
            data={"limit": str(limit), "folder_id": folder_id},
        )

        if isinstance(response_data, dict):
            if "error" in response_data:
                raise InstapaperError(
                    f"API returned error: {response_data.get('error')} - "
                    f"{response_data.get('message', 'unknown error')}"
                )
            # API may return {"user": ..., "bookmarks": [...], "highlights": ...}
            response_data = response_data.get("bookmarks", [])

        articles = []
        for item in response_data:
            if isinstance(item, dict) and item.get("type") == "bookmark":
                articles.append(Article.from_api(item))

        logger.info("Fetched %d articles", len(articles))
        return articles

    def get_article_html(self, bookmark_id: int) -> str:
        """Fetch the full HTML content of a bookmark.

        Args:
            bookmark_id: The Instapaper bookmark ID.

        Returns:
            HTML content as a string.
        """
        logger.debug("Fetching HTML for bookmark %d...", bookmark_id)
        url = f"{BASE_URL}/bookmarks/get_text"
        try:
            response = self._session.post(
                url,
                auth=self._get_auth(),
                data={"bookmark_id": str(bookmark_id)},
                timeout=60,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise InstapaperError(f"Failed to fetch HTML for bookmark {bookmark_id}: {e}") from e

    def tag_bookmark(self, bookmark_id: int, tag: str) -> None:
        """Add a tag to a bookmark.

        Args:
            bookmark_id: The Instapaper bookmark ID.
            tag: Tag name to apply.
        """
        logger.debug("Tagging bookmark %d with '%s'...", bookmark_id, tag)
        try:
            self._api_request(
                "POST",
                f"/bookmarks/{bookmark_id}/tags/add",
                data={"tag": tag},
            )
        except InstapaperError:
            logger.warning("Failed to tag bookmark %d", bookmark_id, exc_info=True)

    def archive_bookmark(self, bookmark_id: int) -> None:
        """Archive a bookmark.

        Args:
            bookmark_id: The Instapaper bookmark ID.
        """
        logger.debug("Archiving bookmark %d...", bookmark_id)
        self._api_request(
            "POST",
            "/bookmarks/archive",
            data={"bookmark_id": str(bookmark_id)},
        )
        logger.debug("Archived bookmark %d", bookmark_id)

    def get_or_create_folder(self, title: str) -> str:
        """Get folder ID by title, creating it if it doesn't exist.

        Args:
            title: Folder title.

        Returns:
            The folder_id as a string.
        """
        if title in self._folder_cache:
            return self._folder_cache[title]

        # List existing folders
        folders = self._api_request("POST", "/folders/list")
        for item in folders:
            if (
                isinstance(item, dict)
                and item.get("type") == "folder"
                and item.get("title") == title
            ):
                folder_id = str(item["folder_id"])
                self._folder_cache[title] = folder_id
                logger.info("Found existing folder '%s' (id=%s)", title, folder_id)
                return folder_id

        # Create folder
        result = self._api_request("POST", "/folders/add", data={"title": title})
        for item in result:
            if isinstance(item, dict) and item.get("type") == "folder":
                folder_id = str(item["folder_id"])
                self._folder_cache[title] = folder_id
                logger.info("Created folder '%s' (id=%s)", title, folder_id)
                return folder_id

        raise InstapaperError(f"Failed to create folder '{title}'")

    def move_bookmark(self, bookmark_id: int, folder_id: str) -> None:
        """Move a bookmark to a folder.

        Args:
            bookmark_id: The Instapaper bookmark ID.
            folder_id: The target folder ID.
        """
        logger.debug("Moving bookmark %d to folder %s...", bookmark_id, folder_id)
        self._api_request(
            "POST",
            "/bookmarks/move",
            data={"bookmark_id": str(bookmark_id), "folder_id": folder_id},
        )
        logger.debug("Moved bookmark %d to folder %s", bookmark_id, folder_id)
