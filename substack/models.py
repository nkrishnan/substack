"""Data models for Substack entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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

    @property
    def url(self) -> str:
        return f"{self.publication_url}/p/{self.slug}"

    @classmethod
    def from_dict(cls, data: dict, publication_url: str) -> "Post":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            slug=data.get("slug", ""),
            publication_url=publication_url.rstrip("/"),
            comment_count=data.get("comment_count", 0),
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
    parent_id: Optional[int] = None
    children: list["Comment"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, post: Post) -> "Comment":
        author_data = data.get("author") or {}
        # Substack nests author info inside a "user" sub-key in some endpoints.
        if not author_data.get("id"):
            author_data = data.get("user") or author_data
        author = User.from_dict(author_data) if author_data.get("id") else User(
            id=0, name="Unknown", handle=""
        )
        children = [
            Comment.from_dict(child, post) for child in data.get("children", [])
        ]
        return cls(
            id=data["id"],
            body=data.get("body", ""),
            post_id=post.id,
            post_title=post.title,
            post_url=post.url,
            author=author,
            like_count=data.get("reactions", {}).get("❤", 0),
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
