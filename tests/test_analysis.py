"""Tests for substack.analysis."""

from substack.analysis import (
    CommentFrequency,
    LikeFrequency,
    comments_by_user,
    most_liked_comments,
    top_commenters,
    top_likers,
)
from substack.models import Comment, Like, Post, User


PUBLICATION_URL = "https://example.substack.com"

_POST = Post(
    id=1, title="Post", slug="post", publication_url=PUBLICATION_URL, comment_count=5
)


def _comment(cid: int, handle: str, likes: int = 0, name: str = "") -> Comment:
    user = User(id=cid, name=name or handle, handle=handle)
    return Comment(
        id=cid,
        body=f"Comment {cid}",
        post_id=_POST.id,
        post_title=_POST.title,
        post_url=_POST.url,
        author=user,
        like_count=likes,
    )


def _like(uid: int, handle: str, comment_id: int = 1) -> Like:
    return Like(comment_id=comment_id, user=User(id=uid, name=handle, handle=handle))


class TestTopCommenters:
    def test_basic_ordering(self):
        comments = [
            _comment(1, "alice"),
            _comment(2, "bob"),
            _comment(3, "alice"),
            _comment(4, "alice"),
            _comment(5, "bob"),
        ]
        results = top_commenters(comments, n=2)
        assert results[0].handle == "alice"
        assert results[0].count == 3
        assert results[1].handle == "bob"
        assert results[1].count == 2

    def test_n_limits_results(self):
        comments = [_comment(i, f"user{i}") for i in range(20)]
        results = top_commenters(comments, n=5)
        assert len(results) == 5

    def test_empty(self):
        assert top_commenters([], n=10) == []

    def test_name_preserved(self):
        comments = [_comment(1, "alice", name="Alice Smith")]
        results = top_commenters(comments, n=1)
        assert results[0].name == "Alice Smith"


class TestMostLikedComments:
    def test_ordering(self):
        comments = [
            _comment(1, "alice", likes=2),
            _comment(2, "bob", likes=10),
            _comment(3, "carol", likes=5),
        ]
        results = most_liked_comments(comments, n=3)
        assert results[0].like_count == 10
        assert results[1].like_count == 5
        assert results[2].like_count == 2

    def test_n_limits(self):
        comments = [_comment(i, "u", likes=i) for i in range(10)]
        assert len(most_liked_comments(comments, n=3)) == 3

    def test_empty(self):
        assert most_liked_comments([]) == []


class TestTopLikers:
    def test_ordering(self):
        likes = [
            _like(1, "alice"),
            _like(2, "bob"),
            _like(3, "alice"),
        ]
        results = top_likers(likes, n=2)
        assert results[0].handle == "alice"
        assert results[0].count == 2

    def test_empty(self):
        assert top_likers([]) == []


class TestCommentsByUser:
    def test_filters_correctly(self):
        comments = [
            _comment(1, "alice"),
            _comment(2, "bob"),
            _comment(3, "alice"),
        ]
        results = comments_by_user(comments, "alice")
        assert len(results) == 2
        assert all(c.author.handle == "alice" for c in results)

    def test_no_match(self):
        comments = [_comment(1, "alice")]
        assert comments_by_user(comments, "nobody") == []
