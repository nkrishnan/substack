"""Rich, queryable data structures for Substack content.

The entry point is :class:`Publication`.  Once loaded it exposes
:class:`PostCollection` and :class:`CommentCollection` objects whose methods
can be chained to filter, sort, and export data in any combination::

    from substack import Publication

    pub = Publication.load("https://example.substack.com")

    # Which mailbag questions were chosen — earliest or most-liked?
    mailbag = pub.posts.containing("Mailbag")
    for post in mailbag:
        cc = post.comments.top_level()
        print(post.title)
        print("  by time :", [(c.created_at, c.like_count) for c in cc.sorted_by("created_at")[:3]])
        print("  by votes:", [(c.like_count, c.created_at) for c in cc.most_liked(3)])

    # Who comments most across the whole publication?
    for user, count in pub.comments.top_commenters(n=10):
        print(user.handle, count)

    # Export everything to CSV for use in pandas / Excel
    pub.comments.to_csv("comments.csv")
    pub.posts.to_csv("posts.csv")
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional, Sequence, Union

from .models import Comment, Like, Post, User


# ---------------------------------------------------------------------------
# CommentCollection
# ---------------------------------------------------------------------------


class CommentCollection:
    """An ordered, queryable collection of :class:`~substack.models.Comment` objects.

    All filter and sort methods return a **new** ``CommentCollection`` so
    calls can be chained freely.
    """

    def __init__(self, comments: Sequence[Comment]) -> None:
        self._comments: list[Comment] = list(comments)

    # --- standard Python protocol -------------------------------------------

    def __iter__(self) -> Iterator[Comment]:
        return iter(self._comments)

    def __len__(self) -> int:
        return len(self._comments)

    def __getitem__(self, idx: int) -> Comment:
        return self._comments[idx]

    def __repr__(self) -> str:
        return f"CommentCollection({len(self)} comments)"

    # --- filtering ----------------------------------------------------------

    def where(self, predicate: Callable[[Comment], bool]) -> "CommentCollection":
        """Filter with any predicate.

        Example::

            cc.where(lambda c: c.like_count > 5)
            cc.where(lambda c: "mailbag" in c.body.lower())
        """
        return CommentCollection(c for c in self._comments if predicate(c))

    def by_user(self, handle: str) -> "CommentCollection":
        """Keep only comments authored by *handle*."""
        return self.where(lambda c: c.author.handle == handle)

    def top_level(self) -> "CommentCollection":
        """Keep only direct post comments (not replies)."""
        return self.where(lambda c: c.parent_id is None)

    def replies(self) -> "CommentCollection":
        """Keep only reply comments (children of other comments)."""
        return self.where(lambda c: c.parent_id is not None)

    def since(self, dt: datetime) -> "CommentCollection":
        """Keep comments posted at or after *dt*."""
        return self.where(lambda c: c.created_at is not None and c.created_at >= dt)

    def before(self, dt: datetime) -> "CommentCollection":
        """Keep comments posted before *dt*."""
        return self.where(lambda c: c.created_at is not None and c.created_at < dt)

    def min_likes(self, n: int) -> "CommentCollection":
        """Keep comments with at least *n* likes."""
        return self.where(lambda c: c.like_count >= n)

    # --- sorting ------------------------------------------------------------

    def sorted_by(self, key: str, *, reverse: bool = False) -> "CommentCollection":
        """Sort by an attribute name (e.g. ``'created_at'``, ``'like_count'``).

        ``None`` values sort last regardless of *reverse*.
        """
        def _sort_key(c: Comment):
            v = getattr(c, key)
            # Ensure None sorts last
            if v is None:
                return (1, None) if not reverse else (0, None)
            return (0, v) if not reverse else (1, v)

        return CommentCollection(sorted(self._comments, key=_sort_key, reverse=reverse))

    # --- analysis -----------------------------------------------------------

    def most_liked(self, n: int = 10) -> "CommentCollection":
        """Return the *n* comments with the highest like counts."""
        return CommentCollection(
            sorted(self._comments, key=lambda c: c.like_count, reverse=True)[:n]
        )

    def top_commenters(self, n: int = 10) -> list[tuple[User, int]]:
        """Return ``[(user, comment_count)]`` sorted by count descending."""
        counts: Counter[str] = Counter()
        users: dict[str, User] = {}
        for c in self._comments:
            h = c.author.handle or str(c.author.id)
            counts[h] += 1
            users.setdefault(h, c.author)
        return [(users[h], cnt) for h, cnt in counts.most_common(n)]

    # --- export -------------------------------------------------------------

    def to_dicts(self) -> list[dict]:
        """Return a list of plain dicts (all fields, ready for JSON / pandas)."""
        return [
            {
                "id": c.id,
                "post_id": c.post_id,
                "post_title": c.post_title,
                "post_url": c.post_url,
                "author_handle": c.author.handle,
                "author_name": c.author.name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "like_count": c.like_count,
                "parent_id": c.parent_id,
                "body": c.body,
            }
            for c in self._comments
        ]

    def to_json(self, path: Optional[Union[str, Path]] = None) -> Optional[str]:
        """Serialise to JSON.

        If *path* is given the result is written to that file and ``None`` is
        returned.  Otherwise the JSON string is returned.
        """
        text = json.dumps(self.to_dicts(), indent=2, ensure_ascii=False)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
            return None
        return text

    def to_csv(self, path: Optional[Union[str, Path]] = None) -> Optional[str]:
        """Serialise to CSV.

        If *path* is given the result is written to that file and ``None`` is
        returned.  Otherwise the CSV string is returned.
        """
        rows = self.to_dicts()
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        text = buf.getvalue()
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
            return None
        return text


# ---------------------------------------------------------------------------
# PostCollection
# ---------------------------------------------------------------------------


class PostCollection:
    """An ordered, queryable collection of :class:`~substack.models.Post` objects."""

    def __init__(self, posts: Sequence[Post]) -> None:
        self._posts: list[Post] = list(posts)

    # --- standard Python protocol -------------------------------------------

    def __iter__(self) -> Iterator[Post]:
        return iter(self._posts)

    def __len__(self) -> int:
        return len(self._posts)

    def __getitem__(self, idx: int) -> Post:
        return self._posts[idx]

    def __repr__(self) -> str:
        return f"PostCollection({len(self)} posts)"

    # --- filtering ----------------------------------------------------------

    def where(self, predicate: Callable[[Post], bool]) -> "PostCollection":
        """Filter with any predicate.

        Example::

            pub.posts.where(lambda p: p.comment_count > 50)
        """
        return PostCollection(p for p in self._posts if predicate(p))

    def of_type(self, post_type: str) -> "PostCollection":
        """Keep posts whose ``post_type`` equals *post_type* (e.g. ``'newsletter'``)."""
        return self.where(lambda p: p.post_type == post_type)

    def containing(self, text: str) -> "PostCollection":
        """Keep posts whose title or subtitle contain *text* (case-insensitive)."""
        lower = text.lower()
        return self.where(
            lambda p: lower in p.title.lower() or lower in (p.subtitle or "").lower()
        )

    def since(self, dt: datetime) -> "PostCollection":
        """Keep posts published at or after *dt*."""
        return self.where(lambda p: p.published_at is not None and p.published_at >= dt)

    def before(self, dt: datetime) -> "PostCollection":
        """Keep posts published before *dt*."""
        return self.where(lambda p: p.published_at is not None and p.published_at < dt)

    # --- sorting ------------------------------------------------------------

    def sorted_by(self, key: str, *, reverse: bool = False) -> "PostCollection":
        """Sort by an attribute name (e.g. ``'published_at'``, ``'comment_count'``)."""
        def _sort_key(p: Post):
            v = getattr(p, key)
            if v is None:
                return (1, None) if not reverse else (0, None)
            return (0, v) if not reverse else (1, v)

        return PostCollection(sorted(self._posts, key=_sort_key, reverse=reverse))

    # --- analysis -----------------------------------------------------------

    def most_discussed(self, n: int = 10) -> "PostCollection":
        """Return the *n* posts with the most comments."""
        return PostCollection(
            sorted(self._posts, key=lambda p: p.comment_count, reverse=True)[:n]
        )

    # --- cross-collection access -------------------------------------------

    @property
    def comments(self) -> CommentCollection:
        """All comments across every post in this collection (flat list)."""
        return CommentCollection(
            c for post in self._posts for c in post._comments
        )

    # --- export -------------------------------------------------------------

    def to_dicts(self) -> list[dict]:
        """Return a list of plain dicts (all fields, ready for JSON / pandas)."""
        return [
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "url": p.url,
                "post_type": p.post_type,
                "subtitle": p.subtitle,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "comment_count": p.comment_count,
                "reaction_count": p.reaction_count,
            }
            for p in self._posts
        ]

    def to_json(self, path: Optional[Union[str, Path]] = None) -> Optional[str]:
        """Serialise to JSON (write to *path* or return string)."""
        text = json.dumps(self.to_dicts(), indent=2, ensure_ascii=False)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
            return None
        return text

    def to_csv(self, path: Optional[Union[str, Path]] = None) -> Optional[str]:
        """Serialise to CSV (write to *path* or return string)."""
        rows = self.to_dicts()
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        text = buf.getvalue()
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
            return None
        return text


# ---------------------------------------------------------------------------
# UserCollection
# ---------------------------------------------------------------------------


class UserCollection:
    """A collection of unique :class:`~substack.models.User` objects."""

    def __init__(self, users: Sequence[User]) -> None:
        # Deduplicate by handle, preserving order.
        seen: dict[str, User] = {}
        for u in users:
            key = u.handle or str(u.id)
            seen.setdefault(key, u)
        self._users: list[User] = list(seen.values())

    def __iter__(self) -> Iterator[User]:
        return iter(self._users)

    def __len__(self) -> int:
        return len(self._users)

    def __repr__(self) -> str:
        return f"UserCollection({len(self)} users)"

    def by_handle(self, handle: str) -> Optional[User]:
        """Return the :class:`~substack.models.User` with the given handle, or ``None``."""
        for u in self._users:
            if u.handle == handle:
                return u
        return None

    def where(self, predicate: Callable[[User], bool]) -> "UserCollection":
        """Filter with any predicate."""
        return UserCollection(u for u in self._users if predicate(u))

    def to_dicts(self) -> list[dict]:
        return [
            {"id": u.id, "handle": u.handle, "name": u.name, "photo_url": u.photo_url}
            for u in self._users
        ]

    def to_json(self, path: Optional[Union[str, Path]] = None) -> Optional[str]:
        text = json.dumps(self.to_dicts(), indent=2, ensure_ascii=False)
        if path is not None:
            Path(path).write_text(text, encoding="utf-8")
            return None
        return text


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


class Publication:
    """The top-level object representing a Substack publication.

    Load it once, then query freely::

        pub = Publication.load("https://example.substack.com")

        pub.posts.containing("Mailbag").comments.sorted_by("created_at")
        pub.comments.top_level().top_commenters(n=20)
        pub.comments.to_csv("comments.csv")
    """

    def __init__(self, url: str, posts: list[Post]) -> None:
        self._url = url.rstrip("/")
        self._posts = posts

    @property
    def url(self) -> str:
        return self._url

    @property
    def posts(self) -> PostCollection:
        """All posts as a queryable :class:`PostCollection`."""
        return PostCollection(self._posts)

    @property
    def comments(self) -> CommentCollection:
        """All comments across every post as a :class:`CommentCollection`."""
        return self.posts.comments

    @property
    def users(self) -> UserCollection:
        """Every unique commenter as a :class:`UserCollection`."""
        return UserCollection(c.author for c in self.comments)

    @classmethod
    def load(
        cls,
        url: str,
        *,
        cookie: Optional[str] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        with_comments: bool = True,
    ) -> "Publication":
        """Fetch a publication and (optionally) all its comments.

        :param url: Publication URL, e.g. ``"https://example.substack.com"``.
        :param cookie: ``substack.sid`` browser cookie for authenticated access.
        :param cache_dir: Directory to cache raw API responses.  Subsequent
            calls with the same *cache_dir* will read from disk instead of
            hitting the network.
        :param with_comments: Set to ``False`` to fetch only post metadata
            (much faster if you only need post-level data).
        """
        from .cache import Cache
        from .client import SubstackClient
        from .scraper import fetch_comments_for_post, fetch_posts

        client = SubstackClient(session_cookie=cookie)
        cache = Cache(cache_dir) if cache_dir else None

        posts = fetch_posts(client, url, cache=cache)
        if with_comments:
            for post in posts:
                if post.comment_count > 0:
                    post._comments = fetch_comments_for_post(
                        client, url, post, cache=cache
                    )

        return cls(url, posts)
