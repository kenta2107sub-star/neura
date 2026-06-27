"""FR-01：collect の純粋関数（フィルタ・ランキング）の単体テスト。"""

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
