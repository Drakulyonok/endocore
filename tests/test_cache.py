"""Cache layer: in-memory + redis-shaped backend + @cached."""

from __future__ import annotations

import asyncio
import fnmatch
import time

import pytest

from endocore.core.cache import InMemoryCache, RedisCache, cached, configure_cache, get_cache


class FakeRedis:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def set(self, k, v):
        self.d[k] = v

    def setex(self, k, ttl, v):
        self.d[k] = v

    def delete(self, *ks):
        for k in ks:
            self.d.pop(k, None)

    def keys(self, pat):
        return [k for k in self.d if fnmatch.fnmatch(k, pat)]

    def exists(self, k):
        return k in self.d


@pytest.fixture(params=["memory", "redis"])
def cache(request):
    if request.param == "memory":
        return InMemoryCache()
    return RedisCache(FakeRedis(), secret="test-secret")


@pytest.mark.parametrize("value", [1, "s", {"a": 1}, [1, 2, 3], True, None, {"n": {"deep": [1]}}])
def test_set_get(cache, value):
    cache.set("k", value)
    assert cache.get("k") == value


def test_get_default(cache):
    assert cache.get("missing") is None
    assert cache.get("missing", "d") == "d"


def test_delete(cache):
    cache.set("k", 1)
    cache.delete("k")
    assert cache.get("k") is None


def test_has(cache):
    cache.set("k", 1)
    assert cache.has("k") is True
    assert cache.has("nope") is False


@pytest.mark.parametrize("start,amount,expected", [(0, 1, 1), (5, 3, 8), (0, 10, 10)])
def test_incr(cache, start, amount, expected):
    if start:
        cache.set("n", start)
    assert cache.incr("n", amount) == expected


def test_clear_memory():
    c = InMemoryCache()
    c.set("a", 1)
    c.set("b", 2)
    c.clear()
    assert c.get("a") is None and c.get("b") is None


def test_ttl_expiry_memory():
    c = InMemoryCache()
    c.set("k", "v", ttl=1)
    assert c.get("k") == "v"
    c._data["k"] = ("v", time.time() - 1)  # force-expire
    assert c.get("k") is None


def test_configure_and_get_default():
    configure_cache("memory")
    get_cache().set("x", 42)
    assert get_cache().get("x") == 42


@pytest.mark.parametrize("x", [1, 2, 5, 10])
def test_cached_sync(x):
    configure_cache("memory")
    calls = {"n": 0}

    @cached(ttl=60)
    def f(v):
        calls["n"] += 1
        return v * 2

    assert f(x) == x * 2
    assert f(x) == x * 2
    assert calls["n"] == 1


def test_cached_async():
    configure_cache("memory")
    calls = {"n": 0}

    @cached(ttl=60)
    async def f(v):
        calls["n"] += 1
        return v + 1

    assert asyncio.run(f(10)) == 11
    assert asyncio.run(f(10)) == 11
    assert calls["n"] == 1


def test_unknown_backend_raises():
    from endocore.core.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        configure_cache("memcached")


# -- RedisCache pickle-RCE hardening (CWE-502) --------------------------------


def test_redis_cache_without_secret_warns():
    with pytest.warns(UserWarning, match="secret"):
        RedisCache(FakeRedis())


def test_redis_cache_with_secret_does_not_warn(recwarn):
    RedisCache(FakeRedis(), secret="s3cr3t")
    assert not recwarn.list


def test_redis_cache_signed_round_trip():
    cache = RedisCache(FakeRedis(), secret="s3cr3t")
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}


def test_redis_cache_rejects_tampered_blob_as_miss():
    """An attacker who can write the Redis key directly (no signature) must
    get a cache miss back, never a pickle.loads() on their bytes."""
    import pickle

    redis = FakeRedis()
    cache = RedisCache(redis, secret="s3cr3t")
    redis.set("endocore:evil", pickle.dumps("attacker-controlled"))
    assert cache.get("evil", "safe-default") == "safe-default"


def test_redis_cache_rejects_blob_signed_with_a_different_secret():
    redis = FakeRedis()
    RedisCache(redis, secret="secret-a").set("k", "mine")
    attacker_view = RedisCache(redis, secret="secret-b")
    assert attacker_view.get("k", "miss") == "miss"


def test_redis_cache_incr_works_when_signed():
    cache = RedisCache(FakeRedis(), secret="s3cr3t")
    assert cache.incr("n", 3) == 3
    assert cache.incr("n", 2) == 5


def test_redis_cache_signature_does_not_verify_under_a_different_key():
    """A signed blob copied from one cache key to another (the attacker still
    needs Redis write access, but not the secret) must not verify — the
    signature is bound to the key it was written under, not just the bytes."""
    redis = FakeRedis()
    cache = RedisCache(redis, secret="s3cr3t")
    cache.set("account:1:balance", 1_000_000)
    stolen_blob = redis.get("endocore:account:1:balance")
    redis.set("endocore:account:2:balance", stolen_blob)
    assert cache.get("account:2:balance", "miss") == "miss"
