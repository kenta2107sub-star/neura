"""FR-02：summarize のプロンプト生成・ジャンル絞込みの単体テスト。"""

import config_loader
import summarize


def _collected(title="t", url="https://x.com/a", body="本文テキスト"):
    return {"title": title, "url": url, "source": "RSS", "score": 0,
            "published_at": "2026-06-18T00:00:00Z", "body_text": body}


def test_build_prompt_injects_articles():
    template = "記事:\n{articles}\n以上"
    prompt = summarize.build_prompt([_collected(title="GPT")], template)
    assert "{articles}" not in prompt
    assert "GPT" in prompt
    assert prompt.startswith("記事:")


def test_build_prompt_fallback_when_no_placeholder():
    prompt = summarize.build_prompt([_collected()], "プレースホルダーなし")
    # フォールバックでデフォルトプロンプトを使う（{articles} 置換済み）
    assert "{articles}" not in prompt
    assert "JSON配列" in prompt


def test_build_prompt_handles_null_body():
    prompt = summarize.build_prompt([_collected(body=None)], "{articles}")
    assert "（本文取得不可）" in prompt


def test_select_articles_filters_disabled_genres():
    result = [
        {"category": "ニュース", "importance": 5, "url": "u1"},
        {"category": "ツール", "importance": 4, "url": "u2"},
        {"category": "研究", "importance": 3, "url": "u3"},
    ]
    genres = {"ニュース": True, "研究": True, "活用事例": True, "ツール": False}
    out = summarize.select_articles(result, genres)
    cats = [a["category"] for a in out]
    assert "ツール" not in cats
    assert cats == ["ニュース", "研究"]  # importance降順


def test_select_articles_sorts_and_caps():
    result = [{"category": "ニュース", "importance": i, "url": f"u{i}"} for i in range(15)]
    genres = {"ニュース": True}
    out = summarize.select_articles(result, genres)
    assert len(out) == summarize.MAX_ARTICLES  # 上位10件
    assert out[0]["importance"] == 14  # 降順先頭が最大
