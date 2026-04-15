"""HTTP client for the (unofficial) Substack API."""

from __future__ import annotations

import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests


_DEFAULT_TIMEOUT = 30
_RATE_LIMIT_DELAY = 0.5  # seconds between requests


class SubstackClient:
    """Thin wrapper around :mod:`requests` for the Substack API.

    Authentication is optional: unauthenticated requests can access public
    posts and comments.  For actions that require a logged-in user (e.g.,
    listing *your* comments across all publications) pass the value of the
    ``substack.sid`` browser cookie via the *session_cookie* parameter.
    """

    BASE_URL = "https://substack.com"

    def __init__(
        self,
        session_cookie: Optional[str] = None,
        timeout: int = _DEFAULT_TIMEOUT,
        rate_limit_delay: float = _RATE_LIMIT_DELAY,
    ) -> None:
        self._session = requests.Session()
        self._timeout = timeout
        self._rate_limit_delay = rate_limit_delay

        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; substack-cli/0.1; "
                    "+https://github.com/nkrishnan/substack)"
                ),
                "Accept": "application/json",
            }
        )
        if session_cookie:
            self._session.cookies.set("substack.sid", session_cookie)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def get(self, url: str, params: Optional[dict] = None) -> Any:
        """Make a GET request and return the parsed JSON response."""
        time.sleep(self._rate_limit_delay)
        response = self._session.get(url, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Publication-scoped endpoints
    # ------------------------------------------------------------------

    @staticmethod
    def publication_api_url(publication_url: str) -> str:
        """Return the base API URL for a publication."""
        parsed = urlparse(publication_url)
        # Support both "https://pub.substack.com" and "pub.substack.com".
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path.split("/")[0]
        return f"{scheme}://{host}/api/v1"

    def get_posts(
        self, publication_url: str, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Fetch posts for *publication_url* (supports pagination)."""
        api = self.publication_api_url(publication_url)
        return self.get(f"{api}/posts", params={"limit": limit, "offset": offset})

    def get_all_posts(self, publication_url: str, limit: int = 50) -> list[dict]:
        """Fetch **all** posts for *publication_url* by paginating automatically."""
        posts: list[dict] = []
        offset = 0
        while True:
            batch = self.get_posts(publication_url, limit=limit, offset=offset)
            if not batch:
                break
            posts.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return posts

    def get_post_comments(self, publication_url: str, post_id: int) -> list[dict]:
        """Fetch all top-level comments (and their children) for a post."""
        api = self.publication_api_url(publication_url)
        data = self.get(
            f"{api}/post/{post_id}/comments",
            params={"all_comments": "true", "sort": "best_first"},
        )
        # The API returns {"comments": [...]} or just a list.
        if isinstance(data, dict):
            return data.get("comments", [])
        return data

    def get_comment_likes(self, publication_url: str, comment_id: int) -> list[dict]:
        """Fetch users who liked *comment_id*."""
        api = self.publication_api_url(publication_url)
        data = self.get(f"{api}/comment/{comment_id}/likes")
        if isinstance(data, list):
            return data
        return data.get("users", [])
