"""Tests for the CLI commands (using Click's test runner + mocked Publication)."""

import csv
import io
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from substack.cli import main
from substack.models import Comment, Like, Post, User
from substack.publication import CommentCollection, PostCollection, Publication

PUBLICATION_URL = "https://example.substack.com"

_DT = datetime(2024, 3, 15, tzinfo=timezone.utc)


def _user(handle="alice", name="Alice", uid=1):
    return User(id=uid, name=name, handle=handle)


def _post(pid=1, title="My Post", published_at=_DT, post_type="newsletter"):
    return Post(
        id=pid,
        title=title,
        slug=title.lower().replace(" ", "-"),
        publication_url=PUBLICATION_URL,
        comment_count=2,
        published_at=published_at,
        post_type=post_type,
    )


def _comment(cid, handle="alice", likes=0, body="Hello"):
    p = _post()
    return Comment(
        id=cid,
        body=body,
        post_id=p.id,
        post_title=p.title,
        post_url=p.url,
        author=_user(handle),
        like_count=likes,
        created_at=_DT,
    )


def _like(uid, handle):
    return Like(comment_id=99, user=_user(handle=handle, uid=uid))


def _mock_pub(posts=None, comments=None):
    """Return a mock Publication whose .posts.comments returns given comments."""
    pub = MagicMock(spec=Publication)
    post_list = [_post()] if posts is None else posts
    comment_list = [_comment(1, "alice"), _comment(2, "bob")] if comments is None else comments
    pc = PostCollection(post_list)
    for p in post_list:
        p._comments = [c for c in comment_list if c.post_id == p.id]
    pub.posts = pc
    pub.comments = CommentCollection(comment_list)
    return pub


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# posts
# ---------------------------------------------------------------------------


class TestPostsCmd:
    def test_table_output(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["posts", PUBLICATION_URL])
        assert result.exit_code == 0
        assert "My Post" in result.output

    def test_json_output(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["--output", "json", "posts", PUBLICATION_URL])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["title"] == "My Post"

    def test_csv_output(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["--output", "csv", "posts", PUBLICATION_URL])
        assert result.exit_code == 0
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = list(reader)
        assert rows[0]["title"] == "My Post"

    def test_no_posts(self, runner):
        pub = _mock_pub(posts=[], comments=[])
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["posts", PUBLICATION_URL])
        assert result.exit_code == 0
        assert "No posts" in result.output


# ---------------------------------------------------------------------------
# comments
# ---------------------------------------------------------------------------


class TestCommentsCmd:
    def test_table_output(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["comments", PUBLICATION_URL])
        assert result.exit_code == 0
        assert "alice" in result.output

    def test_json_output(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(
                main, ["--output", "json", "comments", PUBLICATION_URL]
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        handles = {row["author_handle"] for row in data}
        assert "alice" in handles

    def test_csv_output_has_header(self, runner):
        pub = _mock_pub()
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(
                main, ["--output", "csv", "comments", PUBLICATION_URL]
            )
        assert result.exit_code == 0
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["author_handle"] == "alice"

    def test_csv_includes_timestamps_and_likes(self, runner):
        comments = [_comment(1, "alice", likes=7)]
        pub = _mock_pub(comments=comments)
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(
                main, ["--output", "csv", "comments", PUBLICATION_URL]
            )
        reader = csv.DictReader(io.StringIO(result.stdout))
        row = next(reader)
        assert row["like_count"] == "7"
        assert row["created_at"] != ""

    def test_no_comments(self, runner):
        pub = _mock_pub(comments=[])
        with patch("substack.cli.Publication.load", return_value=pub):
            result = runner.invoke(main, ["comments", PUBLICATION_URL])
        assert result.exit_code == 0
        assert "No comments" in result.output


# ---------------------------------------------------------------------------
# comment-likes
# ---------------------------------------------------------------------------


class TestCommentLikesCmd:
    def test_table_output(self, runner):
        likes = [_like(1, "carol"), _like(2, "dave")]
        with patch("substack.cli.fetch_comment_likes", return_value=likes):
            result = runner.invoke(
                main, ["comment-likes", PUBLICATION_URL, "--comment-id", "99"]
            )
        assert result.exit_code == 0
        assert "carol" in result.output
        assert "dave" in result.output

    def test_json_output(self, runner):
        likes = [_like(1, "carol")]
        with patch("substack.cli.fetch_comment_likes", return_value=likes):
            result = runner.invoke(
                main,
                ["--output", "json", "comment-likes", PUBLICATION_URL, "--comment-id", "99"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["handle"] == "carol"

    def test_csv_output(self, runner):
        likes = [_like(1, "carol"), _like(2, "dave")]
        with patch("substack.cli.fetch_comment_likes", return_value=likes):
            result = runner.invoke(
                main,
                ["--output", "csv", "comment-likes", PUBLICATION_URL, "--comment-id", "99"],
            )
        assert result.exit_code == 0
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) == 2
        handles = {r["handle"] for r in rows}
        assert "carol" in handles

    def test_no_likes(self, runner):
        with patch("substack.cli.fetch_comment_likes", return_value=[]):
            result = runner.invoke(
                main, ["comment-likes", PUBLICATION_URL, "--comment-id", "99"]
            )
        assert result.exit_code == 0
        assert "No likes" in result.output


# ---------------------------------------------------------------------------
# article-comments
# ---------------------------------------------------------------------------


class TestArticleCommentsCmd:
    ARTICLE_URL = "https://example.substack.com/p/my-post"

    def test_json_output(self, runner):
        post_row = {"id": 42, "title": "My Post", "slug": "my-post", "type": "newsletter"}
        comments = [_comment(1, "alice"), _comment(2, "bob")]

        with patch("substack.cli.fetch_comments_for_post", return_value=comments):
            with patch("substack.client.SubstackClient") as client_cls:
                client = client_cls.return_value
                client.get_posts.side_effect = [[post_row]]

                result = runner.invoke(
                    main,
                    ["--output", "json", "article-comments", self.ARTICLE_URL],
                )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        handles = {row["author_handle"] for row in data}
        assert handles == {"alice", "bob"}

    def test_csv_output(self, runner):
        post_row = {"id": 42, "title": "My Post", "slug": "my-post", "type": "newsletter"}
        comments = [_comment(1, "alice", likes=7)]

        with patch("substack.cli.fetch_comments_for_post", return_value=comments):
            with patch("substack.client.SubstackClient") as client_cls:
                client = client_cls.return_value
                client.get_posts.side_effect = [[post_row]]

                result = runner.invoke(
                    main,
                    ["--output", "csv", "article-comments", self.ARTICLE_URL],
                )

        assert result.exit_code == 0
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["author_handle"] == "alice"
        assert rows[0]["like_count"] == "7"

    def test_slug_not_found(self, runner):
        with patch("substack.client.SubstackClient") as client_cls:
            client = client_cls.return_value
            client.get_posts.side_effect = [[{"id": 1, "slug": "other-post"}], []]

            result = runner.invoke(
                main,
                ["article-comments", self.ARTICLE_URL, "--max-pages", "2", "--page-size", "1"],
            )

        assert result.exit_code != 0
        assert "Could not find article slug" in result.output
