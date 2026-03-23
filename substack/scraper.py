"""Functions for fetching data from Substack and turning it into model objects."""

from __future__ import annotations

from typing import Optional

from .client import SubstackClient
from .models import Comment, Like, Post, User


def fetch_posts(
    client: SubstackClient, publication_url: str
) -> list[Post]:
    """Return all :class:`~substack.models.Post` objects for *publication_url*."""
    raw = client.get_all_posts(publication_url)
    return [Post.from_dict(p, publication_url) for p in raw]


def fetch_comments_for_post(
    client: SubstackClient, publication_url: str, post: Post
) -> list[Comment]:
    """Return a flat list of all :class:`~substack.models.Comment` objects for *post*.

    The Substack API returns a tree (comments with nested ``children``).  This
    function preserves the tree on each :class:`~substack.models.Comment` but
    also returns every node in the flat list so callers can iterate easily.
    """
    raw = client.get_post_comments(publication_url, post.id)
    top_level = [Comment.from_dict(c, post) for c in raw]
    return _flatten_comments(top_level)


def fetch_all_comments(
    client: SubstackClient, publication_url: str
) -> list[Comment]:
    """Return all comments across every post in *publication_url*."""
    posts = fetch_posts(client, publication_url)
    all_comments: list[Comment] = []
    for post in posts:
        if post.comment_count == 0:
            continue
        comments = fetch_comments_for_post(client, publication_url, post)
        all_comments.extend(comments)
    return all_comments


def fetch_comment_likes(
    client: SubstackClient, publication_url: str, comment_id: int
) -> list[Like]:
    """Return users who liked *comment_id*."""
    raw = client.get_comment_likes(publication_url, comment_id)
    return [Like.from_dict(u, comment_id) for u in raw]


def fetch_user_comments(
    client: SubstackClient,
    publication_url: str,
    user_handle: str,
) -> list[Comment]:
    """Return all comments left by *user_handle* in *publication_url*."""
    all_comments = fetch_all_comments(client, publication_url)
    return [
        c for c in all_comments if c.author.handle == user_handle
    ]


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
