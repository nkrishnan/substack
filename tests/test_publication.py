"""Tests for substack.publication — collection classes and Publication."""

import json
from datetime import datetime, timezone

import pytest

from substack.models import Comment, Post, User
from substack.publication import (
    CommentCollection,
    PostCollection,
    Publication,
    UserCollection,
)

PUBLICATION_URL = "https://example.substack.com"

_DT_EARLY = datetime(2024, 1, 1, tzinfo=timezone.utc)
_DT_LATE = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _user(handle="alice", name="Alice", uid=1) -> User:
    return User(id=uid, name=name, handle=handle)


def _post(pid=1, title="Post", comment_count=0, published_at=None, post_type="newsletter") -> Post:
    p = Post(
        id=pid,
        title=title,
        slug=title.lower().replace(" ", "-"),
        publication_url=PUBLICATION_URL,
        comment_count=comment_count,
        published_at=published_at,
        post_type=post_type,
    )
    return p


def _comment(
    cid,
    handle="alice",
    likes=0,
    body="Hello",
    created_at=None,
    parent_id=None,
    post=None,
) -> Comment:
    if post is None:
        post = _post(pid=1, title="Post One")
    return Comment(
        id=cid,
        body=body,
        post_id=post.id,
        post_title=post.title,
        post_url=post.url,
        author=_user(handle),
        like_count=likes,
        created_at=created_at,
        parent_id=parent_id,
    )


# ---------------------------------------------------------------------------
# CommentCollection
# ---------------------------------------------------------------------------


class TestCommentCollection:
    def _cc(self, *comments):
        return CommentCollection(comments)

    def test_len_and_iter(self):
        cc = self._cc(_comment(1), _comment(2))
        assert len(cc) == 2
        assert list(cc)[0].id == 1

    def test_getitem(self):
        cc = self._cc(_comment(1), _comment(2))
        assert cc[0].id == 1
        assert cc[1].id == 2

    def test_repr(self):
        assert "2 comments" in repr(self._cc(_comment(1), _comment(2)))

    # filtering
    def test_where(self):
        cc = self._cc(_comment(1, likes=1), _comment(2, likes=5))
        assert len(cc.where(lambda c: c.like_count > 3)) == 1

    def test_by_user(self):
        cc = self._cc(_comment(1, "alice"), _comment(2, "bob"), _comment(3, "alice"))
        assert len(cc.by_user("alice")) == 2
        assert len(cc.by_user("nobody")) == 0

    def test_top_level(self):
        cc = self._cc(
            _comment(1, parent_id=None),
            _comment(2, parent_id=1),
        )
        assert len(cc.top_level()) == 1
        assert cc.top_level()[0].id == 1

    def test_replies(self):
        cc = self._cc(_comment(1), _comment(2, parent_id=1))
        assert len(cc.replies()) == 1

    def test_since(self):
        cc = self._cc(
            _comment(1, created_at=_DT_EARLY),
            _comment(2, created_at=_DT_LATE),
        )
        result = cc.since(datetime(2024, 3, 1, tzinfo=timezone.utc))
        assert len(result) == 1
        assert result[0].id == 2

    def test_before(self):
        cc = self._cc(
            _comment(1, created_at=_DT_EARLY),
            _comment(2, created_at=_DT_LATE),
        )
        result = cc.before(datetime(2024, 3, 1, tzinfo=timezone.utc))
        assert len(result) == 1
        assert result[0].id == 1

    def test_min_likes(self):
        cc = self._cc(_comment(1, likes=0), _comment(2, likes=3), _comment(3, likes=10))
        assert len(cc.min_likes(3)) == 2

    # sorting
    def test_sorted_by_like_count(self):
        cc = self._cc(_comment(1, likes=2), _comment(2, likes=5), _comment(3, likes=1))
        asc = cc.sorted_by("like_count")
        assert [c.like_count for c in asc] == [1, 2, 5]
        desc = cc.sorted_by("like_count", reverse=True)
        assert [c.like_count for c in desc] == [5, 2, 1]

    def test_sorted_by_created_at_none_last(self):
        cc = self._cc(
            _comment(1, created_at=_DT_LATE),
            _comment(2, created_at=None),
            _comment(3, created_at=_DT_EARLY),
        )
        result = cc.sorted_by("created_at")
        # None should sort last
        assert result[0].id == 3   # early
        assert result[1].id == 1   # late
        assert result[2].id == 2   # None

    # analysis
    def test_most_liked(self):
        cc = self._cc(_comment(1, likes=1), _comment(2, likes=9), _comment(3, likes=4))
        top = cc.most_liked(2)
        assert len(top) == 2
        assert top[0].like_count == 9

    def test_top_commenters(self):
        cc = self._cc(
            _comment(1, "alice"), _comment(2, "alice"), _comment(3, "bob")
        )
        results = cc.top_commenters(n=2)
        assert results[0][0].handle == "alice"
        assert results[0][1] == 2
        assert results[1][0].handle == "bob"

    def test_top_commenters_empty(self):
        assert CommentCollection([]).top_commenters() == []

    # export
    def test_to_dicts(self):
        cc = self._cc(_comment(1, "alice", likes=3, created_at=_DT_EARLY))
        rows = cc.to_dicts()
        assert len(rows) == 1
        assert rows[0]["author_handle"] == "alice"
        assert rows[0]["like_count"] == 3
        assert rows[0]["created_at"] == _DT_EARLY.isoformat()

    def test_to_json_returns_string(self):
        cc = self._cc(_comment(1))
        text = cc.to_json()
        assert text is not None
        data = json.loads(text)
        assert isinstance(data, list)

    def test_to_json_writes_file(self, tmp_path):
        cc = self._cc(_comment(1))
        p = tmp_path / "out.json"
        result = cc.to_json(p)
        assert result is None
        assert p.exists()
        data = json.loads(p.read_text())
        assert len(data) == 1

    def test_to_csv_returns_string(self):
        cc = self._cc(_comment(1, "alice"))
        text = cc.to_csv()
        assert text is not None
        assert "alice" in text
        lines = text.strip().splitlines()
        assert len(lines) == 2  # header + 1 row

    def test_to_csv_writes_file(self, tmp_path):
        cc = self._cc(_comment(1))
        p = tmp_path / "out.csv"
        result = cc.to_csv(p)
        assert result is None
        assert "alice" in p.read_text()

    def test_chaining(self):
        """Verify filter → sort → most_liked chain works."""
        cc = CommentCollection([
            _comment(1, "alice", likes=1, created_at=_DT_EARLY),
            _comment(2, "alice", likes=5, created_at=_DT_LATE),
            _comment(3, "bob", likes=10),
        ])
        result = cc.by_user("alice").sorted_by("like_count", reverse=True)
        assert len(result) == 2
        assert result[0].like_count == 5


# ---------------------------------------------------------------------------
# PostCollection
# ---------------------------------------------------------------------------


class TestPostCollection:
    def _pc(self, *posts):
        return PostCollection(posts)

    def test_len_iter_getitem(self):
        pc = self._pc(_post(1), _post(2))
        assert len(pc) == 2
        assert pc[0].id == 1

    def test_where(self):
        pc = self._pc(_post(1, comment_count=5), _post(2, comment_count=0))
        assert len(pc.where(lambda p: p.comment_count > 0)) == 1

    def test_of_type(self):
        pc = self._pc(_post(1, post_type="newsletter"), _post(2, post_type="podcast"))
        assert len(pc.of_type("podcast")) == 1

    def test_containing(self):
        pc = self._pc(
            _post(1, title="Weekly Mailbag"),
            _post(2, title="Opinion piece"),
        )
        result = pc.containing("mailbag")
        assert len(result) == 1
        assert result[0].id == 1

    def test_since(self):
        pc = self._pc(
            _post(1, published_at=_DT_EARLY),
            _post(2, published_at=_DT_LATE),
        )
        result = pc.since(datetime(2024, 3, 1, tzinfo=timezone.utc))
        assert len(result) == 1
        assert result[0].id == 2

    def test_sorted_by_comment_count(self):
        pc = self._pc(_post(1, comment_count=3), _post(2, comment_count=10))
        desc = pc.sorted_by("comment_count", reverse=True)
        assert desc[0].id == 2

    def test_most_discussed(self):
        pc = self._pc(_post(1, comment_count=1), _post(2, comment_count=50))
        top = pc.most_discussed(1)
        assert len(top) == 1
        assert top[0].id == 2

    def test_comments_aggregates_across_posts(self):
        p1 = _post(1, comment_count=2)
        p1._comments = [_comment(1, post=p1), _comment(2, post=p1)]
        p2 = _post(2, comment_count=1)
        p2._comments = [_comment(3, post=p2)]
        pc = PostCollection([p1, p2])
        assert len(pc.comments) == 3

    def test_to_dicts(self):
        pc = self._pc(_post(1, title="Hello", published_at=_DT_EARLY))
        rows = pc.to_dicts()
        assert rows[0]["title"] == "Hello"
        assert rows[0]["published_at"] == _DT_EARLY.isoformat()

    def test_to_csv(self):
        pc = self._pc(_post(1, title="T"))
        text = pc.to_csv()
        assert "T" in text

    def test_to_json(self):
        pc = self._pc(_post(1))
        data = json.loads(pc.to_json())
        assert len(data) == 1


# ---------------------------------------------------------------------------
# UserCollection
# ---------------------------------------------------------------------------


class TestUserCollection:
    def test_deduplicates(self):
        uc = UserCollection([_user("alice"), _user("alice"), _user("bob")])
        assert len(uc) == 2

    def test_by_handle(self):
        uc = UserCollection([_user("alice"), _user("bob")])
        assert uc.by_handle("alice").handle == "alice"
        assert uc.by_handle("nobody") is None

    def test_where(self):
        uc = UserCollection([_user("alice", name="Alice Smith"), _user("bob", name="Bob")])
        result = uc.where(lambda u: "Smith" in u.name)
        assert len(result) == 1

    def test_to_dicts(self):
        uc = UserCollection([_user("alice")])
        rows = uc.to_dicts()
        assert rows[0]["handle"] == "alice"


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


class TestPublication:
    def _pub(self) -> Publication:
        p1 = _post(1, title="Mailbag #1", comment_count=2)
        c1 = _comment(10, "alice", likes=5, created_at=_DT_EARLY, post=p1)
        c2 = _comment(11, "bob", likes=1, created_at=_DT_LATE, post=p1)
        p1._comments = [c1, c2]

        p2 = _post(2, title="Opinion", comment_count=1)
        c3 = _comment(12, "alice", likes=0, post=p2)
        p2._comments = [c3]

        return Publication(PUBLICATION_URL, [p1, p2])

    def test_posts_returns_post_collection(self):
        pub = self._pub()
        assert isinstance(pub.posts, PostCollection)
        assert len(pub.posts) == 2

    def test_comments_returns_all_comments(self):
        pub = self._pub()
        assert len(pub.comments) == 3

    def test_users_deduplicates(self):
        pub = self._pub()
        # alice comments on both posts, should appear once
        uc = pub.users
        handles = {u.handle for u in uc}
        assert "alice" in handles
        assert "bob" in handles
        assert len(handles) == 2

    def test_chainable_mailbag_query(self):
        """Simulate the mailbag analysis: earliest vs most-liked."""
        pub = self._pub()
        mailbag = pub.posts.containing("Mailbag")
        assert len(mailbag) == 1
        by_time = mailbag.comments.sorted_by("created_at")
        assert by_time[0].created_at == _DT_EARLY   # earliest first
        by_votes = mailbag.comments.most_liked(2)
        assert by_votes[0].like_count == 5           # most liked first

    def test_export_csv_roundtrip(self, tmp_path):
        pub = self._pub()
        p = tmp_path / "comments.csv"
        pub.comments.to_csv(p)
        text = p.read_text()
        assert "alice" in text
        lines = text.strip().splitlines()
        assert len(lines) == 4  # header + 3 comments
