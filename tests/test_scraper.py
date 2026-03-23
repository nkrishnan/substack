"""Tests for substack.scraper (using mocked HTTP responses)."""

import json

import pytest
import responses as responses_lib

from substack.client import SubstackClient
from substack.models import Post
from substack.scraper import (
    _flatten_comments,
    fetch_all_comments,
    fetch_comment_likes,
    fetch_comments_for_post,
    fetch_posts,
    fetch_user_comments,
)


PUBLICATION_URL = "https://example.substack.com"
API_BASE = f"{PUBLICATION_URL}/api/v1"

_RAW_POSTS = [
    {"id": 1, "title": "Post One", "slug": "post-one", "comment_count": 2},
    {"id": 2, "title": "Post Two", "slug": "post-two", "comment_count": 0},
]

_RAW_COMMENTS_POST1 = [
    {
        "id": 10,
        "body": "Top comment",
        "author": {"id": 1, "name": "Alice", "handle": "alice"},
        "reactions": {"❤": 3},
        "children": [
            {
                "id": 11,
                "body": "Reply",
                "author": {"id": 2, "name": "Bob", "handle": "bob"},
                "reactions": {"❤": 1},
                "children": [],
            }
        ],
    }
]

_RAW_LIKES = [
    {"id": 5, "name": "Carol", "handle": "carol"},
    {"id": 6, "name": "Dave", "handle": "dave"},
]


@pytest.fixture()
def client():
    return SubstackClient(rate_limit_delay=0)


@responses_lib.activate
def test_fetch_posts(client):
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/posts",
        json=_RAW_POSTS,
        status=200,
    )
    # Second page returns empty to stop pagination
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/posts",
        json=[],
        status=200,
    )
    posts = fetch_posts(client, PUBLICATION_URL)
    assert len(posts) == 2
    assert posts[0].id == 1
    assert posts[0].title == "Post One"
    assert posts[1].comment_count == 0


@responses_lib.activate
def test_fetch_comments_for_post(client):
    post = Post(
        id=1,
        title="Post One",
        slug="post-one",
        publication_url=PUBLICATION_URL,
        comment_count=2,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/post/1/comments",
        json=_RAW_COMMENTS_POST1,
        status=200,
    )
    comments = fetch_comments_for_post(client, PUBLICATION_URL, post)
    # Flat list: parent + child
    assert len(comments) == 2
    assert comments[0].id == 10
    assert comments[0].author.handle == "alice"
    assert comments[0].like_count == 3
    assert comments[1].id == 11
    assert comments[1].author.handle == "bob"


@responses_lib.activate
def test_fetch_all_comments_skips_zero_comment_posts(client):
    responses_lib.add(
        responses_lib.GET, f"{API_BASE}/posts", json=_RAW_POSTS, status=200
    )
    responses_lib.add(
        responses_lib.GET, f"{API_BASE}/posts", json=[], status=200
    )
    # Only post 1 has comments; post 2 should be skipped.
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/post/1/comments",
        json=_RAW_COMMENTS_POST1,
        status=200,
    )
    comments = fetch_all_comments(client, PUBLICATION_URL)
    assert len(comments) == 2  # parent + child from post 1


@responses_lib.activate
def test_fetch_comment_likes(client):
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/comment/10/likes",
        json=_RAW_LIKES,
        status=200,
    )
    likes = fetch_comment_likes(client, PUBLICATION_URL, 10)
    assert len(likes) == 2
    assert likes[0].user.handle == "carol"
    assert likes[0].comment_id == 10


@responses_lib.activate
def test_fetch_user_comments(client):
    responses_lib.add(
        responses_lib.GET, f"{API_BASE}/posts", json=_RAW_POSTS, status=200
    )
    responses_lib.add(
        responses_lib.GET, f"{API_BASE}/posts", json=[], status=200
    )
    responses_lib.add(
        responses_lib.GET,
        f"{API_BASE}/post/1/comments",
        json=_RAW_COMMENTS_POST1,
        status=200,
    )
    comments = fetch_user_comments(client, PUBLICATION_URL, "alice")
    assert len(comments) == 1
    assert comments[0].author.handle == "alice"


def test_flatten_comments_empty():
    assert _flatten_comments([]) == []


def test_flatten_comments_depth():
    """Ensure deep nesting is fully flattened."""
    from substack.models import Comment, User

    _post = Post(
        id=1,
        title="P",
        slug="p",
        publication_url=PUBLICATION_URL,
        comment_count=1,
    )
    user = User(id=1, name="u", handle="u")

    grandchild = Comment(
        id=3, body="gc", post_id=1, post_title="P", post_url="", author=user
    )
    child = Comment(
        id=2, body="c", post_id=1, post_title="P", post_url="", author=user,
        children=[grandchild]
    )
    parent = Comment(
        id=1, body="p", post_id=1, post_title="P", post_url="", author=user,
        children=[child]
    )
    flat = _flatten_comments([parent])
    assert [c.id for c in flat] == [1, 2, 3]
