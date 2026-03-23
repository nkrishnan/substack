"""Data models for Substack entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .publication import CommentCollection


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string (with or without trailing Z) into a datetime."""
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class User:
    """A Substack user."""

    id: int
    name: str
    handle: str
    photo_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            name=data.get("name") or data.get("handle", ""),
            handle=data.get("handle", ""),
            photo_url=data.get("photo_url"),
        )


@dataclass
class Post:
    """A Substack post."""

    id: int
    title: str
    slug: str
    publication_url: str
    comment_count: int = 0
    published_at: Optional[datetime] = None
    post_type: str = ""
    subtitle: str = ""
    reaction_count: int = 0
    # Populated by the scraper / Publication.load(); not part of __init__ signature.
    _comments: list["Comment"] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    @property
    def url(self) -> str:
        return f"{self.publication_url}/p/{self.slug}"

    @property
    def comments(self) -> "CommentCollection":
        from .publication import CommentCollection  # avoid circular import at parse time

        return CommentCollection(self._comments)

    @classmethod
    def from_dict(cls, data: dict, publication_url: str) -> "Post":
        reactions = data.get("reactions") or {}
        reaction_count = reactions.get("❤", 0) if isinstance(reactions, dict) else 0
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            publication_url=publication_url.rstrip("/"),
            comment_count=data.get("comment_count", 0),
            published_at=_parse_dt(data.get("post_date") or data.get("published_at")),
            post_type=data.get("type", ""),
            subtitle=data.get("subtitle") or "",
            reaction_count=reaction_count,
        )


@dataclass
class Comment:
    """A comment on a Substack post."""

    id: int
    body: str
    post_id: int
    post_title: str
    post_url: str
    author: User
    like_count: int = 0
    created_at: Optional[datetime] = None
    parent_id: Optional[int] = None
    children: list["Comment"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, post: Post) -> "Comment":
        author_data = data.get("author") or {}
        # Some Substack endpoints nest author info under a "user" key.
        if not author_data.get("id"):
            author_data = data.get("user") or author_data
        author = (
            User.from_dict(author_data)
            if author_data.get("id")
            else User(id=0, name="Unknown", handle="")
        )
        children = [Comment.from_dict(child, post) for child in data.get("children", [])]
        return cls(
            id=data["id"],
            body=data.get("body", ""),
            post_id=post.id,
            post_title=post.title,
            post_url=post.url,
            author=author,
            like_count=data.get("reactions", {}).get("❤", 0),
            created_at=_parse_dt(data.get("date") or data.get("created_at")),
            parent_id=data.get("parent_id"),
            children=children,
        )


@dataclass
class Like:
    """A like (reaction) left by a user on a comment."""

    comment_id: int
    user: User

    @classmethod
    def from_dict(cls, data: dict, comment_id: int) -> "Like":
        return cls(
            comment_id=comment_id,
            user=User.from_dict(data),
        )
