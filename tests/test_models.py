"""Tests for substack.models."""

from substack.models import Comment, Like, Post, User


PUBLICATION_URL = "https://example.substack.com"


def _make_post(**kwargs) -> Post:
    data = {"id": 1, "title": "Test Post", "slug": "test-post", "comment_count": 3}
    data.update(kwargs)
    return Post.from_dict(data, PUBLICATION_URL)


def _make_user(**kwargs) -> dict:
    data = {"id": 42, "name": "Alice", "handle": "alice"}
    data.update(kwargs)
    return data


class TestUser:
    def test_from_dict_basic(self):
        user = User.from_dict({"id": 1, "name": "Bob", "handle": "bob"})
        assert user.id == 1
        assert user.name == "Bob"
        assert user.handle == "bob"
        assert user.photo_url is None

    def test_from_dict_with_photo(self):
        user = User.from_dict(
            {"id": 2, "name": "Carol", "handle": "carol", "photo_url": "http://img"}
        )
        assert user.photo_url == "http://img"

    def test_from_dict_missing_name_falls_back_to_handle(self):
        user = User.from_dict({"id": 3, "handle": "dave"})
        assert user.name == "dave"


class TestPost:
    def test_from_dict(self):
        post = _make_post()
        assert post.id == 1
        assert post.title == "Test Post"
        assert post.slug == "test-post"
        assert post.comment_count == 3

    def test_url_property(self):
        post = _make_post()
        assert post.url == f"{PUBLICATION_URL}/p/test-post"

    def test_url_strips_trailing_slash(self):
        post = Post.from_dict(
            {"id": 2, "title": "T", "slug": "t", "comment_count": 0},
            PUBLICATION_URL + "/",
        )
        assert post.url == f"{PUBLICATION_URL}/p/t"


class TestComment:
    def test_from_dict_basic(self):
        post = _make_post()
        data = {
            "id": 100,
            "body": "Great post!",
            "author": _make_user(),
            "reactions": {"❤": 5},
        }
        comment = Comment.from_dict(data, post)
        assert comment.id == 100
        assert comment.body == "Great post!"
        assert comment.author.handle == "alice"
        assert comment.like_count == 5
        assert comment.post_id == post.id
        assert comment.post_title == post.title

    def test_from_dict_no_reactions(self):
        post = _make_post()
        data = {"id": 101, "body": "Hello", "author": _make_user()}
        comment = Comment.from_dict(data, post)
        assert comment.like_count == 0

    def test_from_dict_nested_children(self):
        post = _make_post()
        child_data = {"id": 202, "body": "Reply", "author": _make_user(id=99)}
        data = {
            "id": 201,
            "body": "Parent",
            "author": _make_user(),
            "children": [child_data],
        }
        comment = Comment.from_dict(data, post)
        assert len(comment.children) == 1
        assert comment.children[0].id == 202

    def test_from_dict_user_key_fallback(self):
        """Some API responses use 'user' instead of 'author'."""
        post = _make_post()
        data = {"id": 103, "body": "Hi", "user": _make_user(handle="bob_user")}
        comment = Comment.from_dict(data, post)
        assert comment.author.handle == "bob_user"

    def test_from_dict_unknown_author(self):
        post = _make_post()
        data = {"id": 104, "body": "Anon"}
        comment = Comment.from_dict(data, post)
        assert comment.author.name == "Unknown"


class TestLike:
    def test_from_dict(self):
        like = Like.from_dict({"id": 7, "name": "Eve", "handle": "eve"}, comment_id=55)
        assert like.comment_id == 55
        assert like.user.handle == "eve"
