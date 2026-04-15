"""Functions for fetching data from Substack and turning it into model objects."""

from __future__ import annotations

from typing import Optional

from .cache import Cache
from .client import SubstackClient
from .models import Comment, Like, Post, User


def fetch_posts(
    client: SubstackClient,
    publication_url: str,
    *,
    cache: Optional[Cache] = None,
) -> list[Post]:
    """Return all :class:`~substack.models.Post` objects for *publication_url*."""
    cache_key = f"posts:{publication_url}"
    if cache is not None:
        raw = cache.get(cache_key)
        if raw is None:
            raw = client.get_all_posts(publication_url)
            cache.set(cache_key, raw)
    else:
        raw = client.get_all_posts(publication_url)
    return [Post.from_dict(p, publication_url) for p in raw]


def fetch_comments_for_post(
    client: SubstackClient,
    publication_url: str,
    post: Post,
    *,
    cache: Optional[Cache] = None,
) -> list[Comment]:
    """Return a flat list of all :class:`~substack.models.Comment` objects for *post*.

    The Substack API returns a tree (comments with nested ``children``).  This
    function preserves the tree on each :class:`~substack.models.Comment` but
    also returns every node in the flat list so callers can iterate easily.
    """
    cache_key = f"comments:{publication_url}:{post.id}"
    if cache is not None:
        raw = cache.get(cache_key)
        if raw is None:
            raw = client.get_post_comments(publication_url, post.id)
            cache.set(cache_key, raw)
    else:
        raw = client.get_post_comments(publication_url, post.id)
    top_level = [Comment.from_dict(c, post) for c in raw]
    return _flatten_comments(top_level)


def fetch_comment_likes(
    client: SubstackClient,
    publication_url: str,
    comment_id: int,
    *,
    cache: Optional[Cache] = None,
) -> list[Like]:
    """Return users who liked *comment_id*."""
    cache_key = f"likes:{publication_url}:{comment_id}"
    if cache is not None:
        raw = cache.get(cache_key)
        if raw is None:
            raw = client.get_comment_likes(publication_url, comment_id)
            cache.set(cache_key, raw)
    else:
        raw = client.get_comment_likes(publication_url, comment_id)
    return [Like.from_dict(u, comment_id) for u in raw]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _flatten_comments(comments: list[Comment]) -> list[Comment]:
    """Walk a comment tree and return every node in depth-first order."""
    result: list[Comment] = []
    for comment in comments:
        result.append(comment)
        if comment.children:
            result.extend(_flatten_comments(comment.children))
    return result
