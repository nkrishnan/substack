"""Tests for substack.cache."""

import json
from pathlib import Path

import pytest

from substack.cache import Cache


@pytest.fixture()
def cache(tmp_path) -> Cache:
    return Cache(tmp_path / "cache")


class TestCache:
    def test_miss_returns_none(self, cache):
        assert cache.get("missing-key") is None

    def test_set_and_get(self, cache):
        cache.set("key1", {"a": 1, "b": [1, 2, 3]})
        result = cache.get("key1")
        assert result == {"a": 1, "b": [1, 2, 3]}

    def test_set_list(self, cache):
        cache.set("list-key", [1, 2, 3])
        assert cache.get("list-key") == [1, 2, 3]

    def test_overwrite(self, cache):
        cache.set("k", {"v": 1})
        cache.set("k", {"v": 2})
        assert cache.get("k") == {"v": 2}

    def test_invalidate(self, cache):
        cache.set("k", {"v": 1})
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_missing_is_noop(self, cache):
        cache.invalidate("nonexistent")  # should not raise

    def test_clear(self, cache):
        cache.set("k1", 1)
        cache.set("k2", 2)
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_different_keys_dont_collide(self, cache):
        cache.set("key:a", {"x": 1})
        cache.set("key:b", {"x": 2})
        assert cache.get("key:a") == {"x": 1}
        assert cache.get("key:b") == {"x": 2}

    def test_creates_directory_if_missing(self, tmp_path):
        subdir = tmp_path / "deep" / "nested" / "cache"
        cache = Cache(subdir)
        cache.set("k", 42)
        assert cache.get("k") == 42

    def test_tilde_expansion(self, tmp_path, monkeypatch):
        # Ensure ~ in path is expanded
        monkeypatch.setenv("HOME", str(tmp_path))
        cache = Cache("~/testcache")
        cache.set("k", 99)
        assert cache.get("k") == 99
