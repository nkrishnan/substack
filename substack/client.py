"""HTTP client for the (unofficial) Substack API."""

from __future__ import annotations

import time
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import requests


_DEFAULT_TIMEOUT = 30
_RATE_LIMIT_DELAY = 0.5  # seconds between requests
_MAX_RETRIES = 5
_BACKOFF_BASE = 2.0  # seconds; doubles on each retry
_MAX_BACKOFF = 60.0
_RETRY_STATUSES = {429, 500, 502, 503, 504}


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
        max_retries: int = _MAX_RETRIES,
        backoff_base: float = _BACKOFF_BASE,
    ) -> None:
        self._session = requests.Session()
        self._timeout = timeout
        self._rate_limit_delay = rate_limit_delay
        self._max_retries = max_retries
        self._backoff_base = backoff_base

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
        """Make a GET request and return the parsed JSON response.

        Retries on 429 (rate limited) and transient 5xx errors with
        exponential backoff, honouring a numeric ``Retry-After`` header.
        """
        time.sleep(self._rate_limit_delay)
        for attempt in range(self._max_retries + 1):
            response = self._session.get(url, params=params, timeout=self._timeout)
            if (
                response.status_code not in _RETRY_STATUSES
                or attempt == self._max_retries
            ):
                break
            time.sleep(self._retry_delay(response, attempt))
        response.raise_for_status()
        return response.json()

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = float(retry_after)
        except ValueError:
            delay = self._backoff_base * (2**attempt)
        return min(max(delay, 0.0), _MAX_BACKOFF)

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
        self,
        publication_url: str,
        limit: int = 50,
        offset: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Fetch one page of posts for *publication_url*.

        Returns ``(posts, next_cursor)``.  Substack now paginates ``/posts``
        with an opaque ``cursor`` (returned as ``nextCursor``) and rejects the
        ``offset`` parameter, even ``offset=0``.  Older deployments return a
        bare list and paginate by ``offset``; for those ``next_cursor`` is
        ``None``.  *limit* is capped at 50 by the API.
        """
        api = self.publication_api_url(publication_url)
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        elif offset:
            params["offset"] = offset
        data = self.get(f"{api}/posts", params=params)
        if isinstance(data, dict):
            return data.get("posts", []), data.get("nextCursor")
        return data, None

    def get_post_by_slug(self, publication_url: str, slug: str) -> Optional[dict]:
        """Fetch a single post by *slug*, or ``None`` if the API has no such post."""
        api = self.publication_api_url(publication_url)
        try:
            data = self.get(f"{api}/posts/{slug}")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise
        return data if isinstance(data, dict) and data.get("id") else None

    def iter_post_pages(
        self, publication_url: str, limit: int = 50
    ) -> Iterator[list[dict]]:
        """Yield successive pages of posts, newest first.

        Follows ``nextCursor`` when the API provides one and falls back to
        ``offset`` pagination for the legacy list-shaped response.
        """
        offset = 0
        cursor: Optional[str] = None
        while True:
            batch, next_cursor = self.get_posts(
                publication_url, limit=limit, offset=offset, cursor=cursor
            )
            if not batch:
                return
            yield batch
            if next_cursor:
                cursor = next_cursor
            elif cursor is None and len(batch) == limit:
                # Legacy offset pagination: no cursor was ever returned.
                offset += limit
            else:
                return

    def get_all_posts(self, publication_url: str, limit: int = 50) -> list[dict]:
        """Fetch **all** posts for *publication_url* by paginating automatically."""
        posts: list[dict] = []
        for batch in self.iter_post_pages(publication_url, limit=limit):
            posts.extend(batch)
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
        """Fetch users who reacted to (liked) *comment_id*.

        Uses the ``/comment/{id}/reactors`` endpoint; the older ``/likes``
        endpoint now 404s.  Reactor objects carry ``id`` and ``name`` but no
        ``handle``.  The list can be shorter than the comment's reaction count.
        """
        api = self.publication_api_url(publication_url)
        data = self.get(f"{api}/comment/{comment_id}/reactors")
        if isinstance(data, list):
            return data
        return data.get("users", [])
