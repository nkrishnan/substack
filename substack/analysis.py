"""Analysis functions that operate on lists of model objects."""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

from .models import Comment, Like


class CommentFrequency(NamedTuple):
    """Commenter and how many comments they left."""

    handle: str
    name: str
    count: int


class LikeFrequency(NamedTuple):
    """User and how many likes they gave."""

    handle: str
    name: str
    count: int


def top_commenters(
    comments: list[Comment], n: int = 10
) -> list[CommentFrequency]:
    """Return the *n* most frequent commenters among *comments*.

    :param comments: Flat list of :class:`~substack.models.Comment` objects.
    :param n: Maximum number of results to return.
    :returns: List of :class:`CommentFrequency` sorted by count descending.
    """
    counter: Counter[str] = Counter()
    handle_to_name: dict[str, str] = {}
    for comment in comments:
        handle = comment.author.handle or str(comment.author.id)
        counter[handle] += 1
        handle_to_name.setdefault(handle, comment.author.name)

    return [
        CommentFrequency(handle=handle, name=handle_to_name[handle], count=count)
        for handle, count in counter.most_common(n)
    ]


def most_liked_comments(
    comments: list[Comment], n: int = 10
) -> list[Comment]:
    """Return the *n* comments with the highest like counts.

    :param comments: Flat list of :class:`~substack.models.Comment` objects.
    :param n: Maximum number of results to return.
    :returns: List of :class:`~substack.models.Comment` sorted by like count descending.
    """
    return sorted(comments, key=lambda c: c.like_count, reverse=True)[:n]


def top_likers(likes: list[Like], n: int = 10) -> list[LikeFrequency]:
    """Return the *n* users who gave the most likes.

    :param likes: Flat list of :class:`~substack.models.Like` objects
                  (typically from multiple comments).
    :param n: Maximum number of results to return.
    :returns: List of :class:`LikeFrequency` sorted by count descending.
    """
    counter: Counter[str] = Counter()
    handle_to_name: dict[str, str] = {}
    for like in likes:
        handle = like.user.handle or str(like.user.id)
        counter[handle] += 1
        handle_to_name.setdefault(handle, like.user.name)

    return [
        LikeFrequency(handle=handle, name=handle_to_name[handle], count=count)
        for handle, count in counter.most_common(n)
    ]


def comments_by_user(
    comments: list[Comment], user_handle: str
) -> list[Comment]:
    """Filter *comments* to those authored by *user_handle*.

    :param comments: Flat list of :class:`~substack.models.Comment` objects.
    :param user_handle: Substack handle of the target user.
    :returns: Comments authored by that user.
    """
    return [c for c in comments if c.author.handle == user_handle]
