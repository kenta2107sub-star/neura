"""FR-01：collect の純粋関数（フィルタ・ランキング）の単体テスト。"""

import asyncio

import pytest

import collect

KW = {
    "en": ["ai", "gpt", "llm"],
    "ja": ["AI", "機械学習"],
}


def _art(title, source, score=0, url=None, published_at="2026-06-18T00:00:00Z"):
    return {
        "title": title,
        "url": url or f"https://example.com/{abs(hash(title)) % 100000}",
        "source": source,
        "score": score,
        "published_at": published_at,
        "body_text": None,
    }


def test_matches_ai_keyword_en():
    assert collect.matches_ai_keyword("New GPT model released", "RSS", KW) is True
    assert collect.matches_ai_keyword("A post about gardening", "RSS", KW) is False


def test_matches_ai_keyword_zenn_always_true():
    # Zenn は ai タグフィードのためフィルタしない
    assert collect.matches_ai_keyword("料理のレシピ", "Zenn", KW) is True


def test_matches_ai_keyword_hatena_uses_ja():
    assert collect.matches_ai_keyword("機械学習の入門", "HatenaBookmark", KW) is True
    assert collect.matches_ai_keyword("GPT news", "HatenaBookmark", KW) is False  # en語は対象外


def test_filter_and_rank_dedup_and_validation():
    arts = [
        _art("GPT release", "HackerNews", score=100, url="https://a.com/x"),
        _art("GPT release dup", "Reddit", url="https://a.com/x/"),  # 正規化で重複
        _art("not http", "RSS", url="ftp://bad/url"),  # URL不正で除外
        _art("gardening", "RSS"),  # キーワード非該当で除外
    ]
    out = collect.filter_and_rank(arts, KW)
    urls = [a["url"] for a in out]
    assert "https://a.com/x" in urls
    assert "https://a.com/x/" not in urls  # 重複排除
    assert all(a["url"].startswith("http") for a in out)
    assert not any(a["title"] == "gardening" for a in out)


def test_filter_and_rank_score_vs_date_groups():
    score_arts = [_art(f"ai item {i}", "HackerNews", score=i) for i in range(25)]
    date_arts = [_art(f"ai date {i}", "Reddit", published_at=f"2026-06-{i+1:02d}T00:00:00Z") for i in range(15)]
    out = collect.filter_and_rank(score_arts + date_arts, KW)
    # スコア系最大14件 + 日付系最大6件 = 最大20件
    assert len(out) == 20
    hn = [a for a in out if a["source"] == "HackerNews"]
    rd = [a for a in out if a["source"] == "Reddit"]
    assert len(hn) == 14
    assert len(rd) == 6
    # スコア系は降順
    assert hn[0]["score"] >= hn[-1]["score"]


def test_flatten_skips_exceptions():
    exc = ValueError("network error")
    result = collect.flatten([[{"title": "a", "url": "https://x.com", "source": "RSS",
                                "score": 0, "published_at": "2026-06-18T00:00:00Z",
                                "body_text": None}],
                              exc,
                              []])
    assert len(result) == 1
    assert result[0]["title"] == "a"


def test_configured_sources_require_https_but_article_urls_keep_public_http_support():
    assert collect.validate_public_url("https://example.com/feed.xml", ("https",)) == "https://example.com/feed.xml"
    with pytest.raises(collect.UnsafeUrlError):
        collect.validate_public_url("http://example.com/feed.xml", ("https",))
    assert collect.is_allowed_article_url("http://example.com/article") is True


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://10.0.0.1/",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/",
    "http://[fe80::1]/",
])
def test_article_url_filter_rejects_non_public_ip_literals(url):
    assert collect.is_allowed_article_url(url) is False


class _FakeContent:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, _size):
        for chunk in self.chunks:
            yield chunk


class _FakeResponse:
    def __init__(self, *, status=200, headers=None, chunks=(b"ok",), content_length=None):
        self.status = status
        self.headers = headers or {}
        self.content = _FakeContent(chunks)
        self.content_length = content_length

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(self.status)


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, _url, **_kwargs):
        return self.responses.pop(0)


def test_limited_response_rejects_declared_and_streamed_oversize_bodies():
    declared = _FakeResponse(content_length=11)
    streamed = _FakeResponse(chunks=(b"12345", b"67890", b"x"))

    with pytest.raises(collect.ResponseTooLargeError):
        asyncio.run(collect.read_limited(declared, 10))
    with pytest.raises(collect.ResponseTooLargeError):
        asyncio.run(collect.read_limited(streamed, 10))


def test_fetch_public_bytes_rejects_redirect_to_private_ip():
    session = _FakeSession([_FakeResponse(status=302, headers={"Location": "https://127.0.0.1/"})])

    with pytest.raises(collect.UnsafeUrlError):
        asyncio.run(collect.fetch_public_bytes(
            session,
            "https://example.com/feed.xml",
            allowed_schemes=("https",),
            max_bytes=collect.FEED_MAX_BYTES,
        ))


def test_fetch_public_bytes_allows_public_url_and_enforces_redirect_limit():
    safe = _FakeSession([_FakeResponse(chunks=(b"feed",))])
    assert asyncio.run(collect.fetch_public_bytes(
        safe,
        "https://example.com/feed.xml",
        allowed_schemes=("https",),
        max_bytes=collect.FEED_MAX_BYTES,
    )) == b"feed"

    redirects = _FakeSession([
        _FakeResponse(status=302, headers={"Location": f"https://example.com/{i}"})
        for i in range(collect.MAX_REDIRECTS + 1)
    ])
    with pytest.raises(collect.UnsafeUrlError):
        asyncio.run(collect.fetch_public_bytes(
            redirects,
            "https://example.com/start",
            allowed_schemes=("https",),
            max_bytes=collect.FEED_MAX_BYTES,
        ))


def test_public_resolver_rejects_private_dns_results(monkeypatch):
    class _FakeLoop:
        async def getaddrinfo(self, *_args, **_kwargs):
            return [
                (2, 1, 6, "", ("93.184.216.34", 443)),
                (2, 1, 6, "", ("169.254.169.254", 443)),
            ]

    monkeypatch.setattr(collect.asyncio, "get_running_loop", lambda: _FakeLoop())

    with pytest.raises(collect.UnsafeUrlError):
        asyncio.run(collect.PublicInternetResolver().resolve("example.com", 443))
