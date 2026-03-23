"""Substack scraping and analytics toolkit."""

from .publication import CommentCollection, PostCollection, Publication, UserCollection

__version__ = "0.1.0"
__all__ = ["Publication", "PostCollection", "CommentCollection", "UserCollection"]
