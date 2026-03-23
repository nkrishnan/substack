"""Tests for the CLI commands (using Click's test runner + mocked scraper)."""

import json

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from substack.cli import main
from substack.models import Comment, Like, Post, User


PUBLICATION_URL = "https://example.substack.com"


def _user(handle="alice", name="Alice", uid=1):
    return User(id=uid, name=name, handle=handle)


def _comment(cid, handle="alice", likes=0, body="Hello"):
    post = Post(
        id=1, title="My Post", slug="my-post",
        publication_url=PUBLICATION_URL, comment_count=1
    )
    return Comment(
        id=cid, body=body, post_id=1, post_title="My Post",
        post_url=f"{PUBLICATION_URL}/p/my-post",
        author=_user(handle), like_count=likes,
    )


def _like(uid, handle):
    return Like(comment_id=99, user=_user(handle=handle, uid=uid))


@pytest.fixture()
def runner():
    return CliRunner(mix_stderr=False)


class TestTopCommentersCmd:
    def test_text_output(self, runner):
        comments = [_comment(1, "alice"), _comment(2, "alice"), _comment(3, "bob")]
        with patch("substack.cli.fetch_all_comments", return_value=comments):
            result = runner.invoke(
                main, ["top-commenters", PUBLICATION_URL, "--top", "2"]
            )
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output

    def test_json_output(self, runner):
        comments = [_comment(1, "alice"), _comment(2, "bob")]
        with patch("substack.cli.fetch_all_comments", return_value=comments):
            result = runner.invoke(
                main,
                ["--output", "json", "top-commenters", PUBLICATION_URL],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["handle"] in ("alice", "bob")

    def test_no_comments(self, runner):
        with patch("substack.cli.fetch_all_comments", return_value=[]):
            result = runner.invoke(main, ["top-commenters", PUBLICATION_URL])
        assert result.exit_code == 0
        assert "No comments" in result.output


class TestMostLikedCommentsCmd:
    def test_text_output(self, runner):
        comments = [
            _comment(1, "alice", likes=5, body="Great post"),
            _comment(2, "bob", likes=1, body="Nice"),
        ]
        with patch("substack.cli.fetch_all_comments", return_value=comments):
            result = runner.invoke(
                main, ["most-liked-comments", PUBLICATION_URL, "--top", "2"]
            )
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "5" in result.output

    def test_json_output(self, runner):
        comments = [_comment(1, "alice", likes=3)]
        with patch("substack.cli.fetch_all_comments", return_value=comments):
            result = runner.invoke(
                main,
                ["--output", "json", "most-liked-comments", PUBLICATION_URL],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["like_count"] == 3


class TestUserCommentsCmd:
    def test_filters_by_user(self, runner):
        comments = [
            _comment(1, "alice", body="Alice's comment"),
            _comment(2, "bob", body="Bob's comment"),
        ]
        with patch("substack.cli.fetch_all_comments", return_value=comments):
            result = runner.invoke(
                main,
                ["user-comments", PUBLICATION_URL, "--user", "alice"],
            )
        assert result.exit_code == 0
        assert "Alice's comment" in result.output
        assert "Bob's comment" not in result.output

    def test_no_match(self, runner):
        with patch("substack.cli.fetch_all_comments", return_value=[]):
            result = runner.invoke(
                main, ["user-comments", PUBLICATION_URL, "--user", "nobody"]
            )
        assert result.exit_code == 0
        assert "No comments" in result.output


class TestCommentLikersCmd:
    def test_text_output(self, runner):
        likes = [_like(1, "carol"), _like(2, "dave")]
        with patch("substack.cli.fetch_comment_likes", return_value=likes):
            result = runner.invoke(
                main,
                ["comment-likers", PUBLICATION_URL, "--comment-id", "99"],
            )
        assert result.exit_code == 0
        assert "carol" in result.output
        assert "dave" in result.output

    def test_json_output(self, runner):
        likes = [_like(1, "carol")]
        with patch("substack.cli.fetch_comment_likes", return_value=likes):
            result = runner.invoke(
                main,
                [
                    "--output", "json",
                    "comment-likers", PUBLICATION_URL,
                    "--comment-id", "99",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["handle"] == "carol"

    def test_no_likes(self, runner):
        with patch("substack.cli.fetch_comment_likes", return_value=[]):
            result = runner.invoke(
                main,
                ["comment-likers", PUBLICATION_URL, "--comment-id", "99"],
            )
        assert result.exit_code == 0
        assert "No likes" in result.output
