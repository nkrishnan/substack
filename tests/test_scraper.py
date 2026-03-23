"""Tests for substack.scraper (using mocked HTTP responses)."""

import json

import pytest
import responses as responses_lib

from substack.client import SubstackClient
from substack.models import Post
from substack.scraper import (
    _flatten_comments,
    fetch_comment_likes,
    fetch_comments_for_post,
    fetch_posts,
)


PUBLICATION_URL = "https://example.substack.com"
API_BASE = f"{PUBLICATION_URL}/api/v1"

_RAW_POSTS = [
    {
        "id": 1,
        "title": "Post One",
        "slug": "post-one",
        "comment_count": 2,
        "post_date": "2024-01-10T08:00:00.000Z",
        "type": "newsletter",
    },
    {"id": 2, "title": "Post Two", "slug": "post-two", "comment_count": 0},
]

_RAW_COMMENTS_POST1 = [
    {
        "id": 10,
        "body": "Top comment",
        "author": {"id": 1, "name": "Alice", "handle": "alice"},
        "reactions": {"❤": 3},
        "date": "2024-01-11T10:00:00.000Z",
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
    assert posts[0].published_at is not None
    assert posts[0].published_at.year == 2024
    assert posts[0].post_type == "newsletter"
    assert posts[1].comment_count == 0


@responses_lib.activate
def test_fetch_posts_uses_cache(client, tmp_path):
    from substack.cache import Cache

    cache = Cache(tmp_path)
    # Prime the cache manually.
    cache.set(f"posts:{PUBLICATION_URL}", _RAW_POSTS)
    # No HTTP call should be made.
    posts = fetch_posts(client, PUBLICATION_URL, cache=cache)
    assert len(posts) == 2
    # responses_lib would raise if any HTTP call were made.


@responses_lib.activate
def test_fetch_posts_populates_cache(client, tmp_path):
    from substack.cache import Cache

    responses_lib.add(responses_lib.GET, f"{API_BASE}/posts", json=_RAW_POSTS)
    responses_lib.add(responses_lib.GET, f"{API_BASE}/posts", json=[])

    cache = Cache(tmp_path)
    fetch_posts(client, PUBLICATION_URL, cache=cache)
    # Second call should use cache, not hit the network again.
    posts2 = fetch_posts(client, PUBLICATION_URL, cache=cache)
    assert len(posts2) == 2


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
    assert comments[0].created_at is not None
    assert comments[1].id == 11
    assert comments[1].author.handle == "bob"


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
def test_fetch_comment_likes_uses_cache(client, tmp_path):
    from substack.cache import Cache

    cache = Cache(tmp_path)
    cache.set(f"likes:{PUBLICATION_URL}:10", _RAW_LIKES)
    likes = fetch_comment_likes(client, PUBLICATION_URL, 10, cache=cache)
    assert len(likes) == 2


def test_flatten_comments_empty():
    assert _flatten_comments([]) == []


def test_flatten_comments_depth():
    """Ensure deep nesting is fully flattened."""
    from substack.models import Comment, User

    post = Post(
        id=1, title="P", slug="p", publication_url=PUBLICATION_URL, comment_count=1
    )
    user = User(id=1, name="u", handle="u")

    grandchild = Comment(id=3, body="gc", post_id=1, post_title="P", post_url="", author=user)
    child = Comment(id=2, body="c", post_id=1, post_title="P", post_url="", author=user, children=[grandchild])
    parent = Comment(id=1, body="p", post_id=1, post_title="P", post_url="", author=user, children=[child])
    flat = _flatten_comments([parent])
    assert [c.id for c in flat] == [1, 2, 3]
