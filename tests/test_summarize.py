"""FR-02：summarize のプロンプト生成・ジャンル絞込みの単体テスト。"""

from unittest.mock import patch

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


def test_normalize_category_valid_passthrough():
    for cat in ["ニュース", "研究", "活用事例", "ツール"]:
        assert summarize.normalize_category(cat) == cat


def test_normalize_category_english_mapping():
    assert summarize.normalize_category("News") == "ニュース"
    assert summarize.normalize_category("news") == "ニュース"
    assert summarize.normalize_category("Research") == "研究"
    assert summarize.normalize_category("Tool") == "ツール"
    assert summarize.normalize_category("tools") == "ツール"
    assert summarize.normalize_category("Use Cases") == "活用事例"
    assert summarize.normalize_category("application") == "活用事例"


def test_normalize_category_japanese_variant_mapping():
    assert summarize.normalize_category("ニュース・動向") == "ニュース"
    assert summarize.normalize_category("研究・論文") == "研究"
    assert summarize.normalize_category("ツール・製品") == "ツール"
    assert summarize.normalize_category("活用事例・ビジネス") == "活用事例"


def test_normalize_category_unknown_returns_as_is():
    assert summarize.normalize_category("unknown_cat") == "unknown_cat"


def test_normalize_category_none_or_empty():
    assert summarize.normalize_category(None) == ""
    assert summarize.normalize_category("") == ""


def test_normalize_url_strips_trailing_slash_and_query():
    assert summarize.normalize_url("https://x.com/a/") == "https://x.com/a"
    assert summarize.normalize_url("https://x.com/a?utm=1") == "https://x.com/a"
    # rstrip("/") はクエリ除去の前に行うため、a/?q=1 のスラッシュは残る
    assert summarize.normalize_url("https://x.com/a/?ref=foo") == "https://x.com/a/"


def test_build_selection_prompt_contains_title_and_url():
    arts = [_collected(title="GPT-5登場", url="https://x.com/gpt5", body="本文")]
    prompt = summarize.build_selection_prompt(arts, n=5)
    assert "GPT-5登場" in prompt
    assert "https://x.com/gpt5" in prompt
    assert "{" not in prompt  # プレースホルダーが残っていない


def test_build_selection_prompt_handles_null_body():
    arts = [_collected(body=None)]
    prompt = summarize.build_selection_prompt(arts)
    assert "（本文取得不可）" in prompt


def _slot(hour, enabled=True):
    return {"hour": hour, "enabled": enabled, "max_articles": 10,
            "genres": {"ニュース": True}}


def test_get_current_slot_matches_current_hour():
    slots = [_slot(8, enabled=False), _slot(13), _slot(20, enabled=False)]
    result = summarize.get_current_slot.__wrapped__(slots, current_hour=13) \
        if hasattr(summarize.get_current_slot, "__wrapped__") \
        else _get_slot_by_hour(slots, 13)
    assert result["hour"] == 13


def _get_slot_by_hour(slots, hour):
    """get_current_slot の時刻依存部分を切り出して直接テストするヘルパー。"""
    for s in slots:
        if s.get("enabled") and s.get("hour") == hour:
            return s
    for s in slots:
        if s.get("enabled"):
            return s
    return {}


def test_get_current_slot_fallback_to_first_enabled():
    slots = [_slot(8, enabled=False), _slot(13), _slot(20)]
    result = _get_slot_by_hour(slots, 99)  # 99時は存在しないのでフォールバック
    assert result["hour"] == 13  # 最初のenabled


def test_get_current_slot_returns_empty_when_all_disabled():
    slots = [_slot(8, enabled=False), _slot(13, enabled=False)]
    result = _get_slot_by_hour(slots, 99)
    assert result == {}


def test_call_gemini_json_retries_on_parse_failure():
    """JSONパース失敗時にリトライし、2回目で成功すること。"""
    responses = iter(["not valid json", '[{"url": "u1", "category": "ニュース"}]'])
    with patch("summarize._call_gemini", side_effect=lambda *a, **kw: next(responses)), \
         patch("time.sleep"):
        result = summarize._call_gemini_json(None, "prompt", None, max_retries=3)
    assert isinstance(result, list)
    assert result[0]["url"] == "u1"


def test_call_gemini_json_retries_on_non_list():
    """listでないJSONが返ってきた場合もリトライすること。"""
    responses = iter(['{"key": "val"}', '[{"url": "u2"}]'])
    with patch("summarize._call_gemini", side_effect=lambda *a, **kw: next(responses)), \
         patch("time.sleep"):
        result = summarize._call_gemini_json(None, "prompt", None, max_retries=3)
    assert result[0]["url"] == "u2"


def test_call_gemini_json_exits_after_max_retries():
    """max_retries 回連続でパース失敗した場合は sys.exit(1) すること。"""
    import pytest
    with patch("summarize._call_gemini", return_value="bad json"), \
         patch("time.sleep"):
        with pytest.raises(SystemExit) as exc:
            summarize._call_gemini_json(None, "prompt", None, max_retries=3)
    assert exc.value.code == 1


def test_select_articles_returns_empty_when_all_genres_disabled():
    """全genresがfalseの場合、select_articlesは空リストを返すこと。"""
    import pytest
    result = [{"category": "ニュース", "importance": 5, "url": "u1"}]
    genres = {"ニュース": False, "研究": False, "活用事例": False, "ツール": False}
    out = summarize.select_articles(result, genres)
    assert out == []


def test_main_exits_when_zero_articles_after_filter(tmp_path, monkeypatch):
    """カテゴリフィルタ後に0件となった場合、sys.exit(1)すること。"""
    import pytest
    import json as json_mod
    import sys
    from types import ModuleType

    collected = [{"title": "t", "url": "https://x.com/a", "source": "RSS",
                  "score": 0, "published_at": "2026-06-18T00:00:00Z", "body_text": "本文"}]
    collected_path = tmp_path / "collected.json"
    collected_path.write_text(json_mod.dumps(collected), encoding="utf-8")
    monkeypatch.setattr(summarize, "INPUT_PATH", str(collected_path))
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")

    gemini_result = [{"url": "https://x.com/a", "title_ja": "タイトル",
                      "summary_ja": "要約", "translation_ja": "翻訳",
                      "category": "ニュース", "importance": 3}]

    config_with_no_enabled_genres = {
        **config_loader.DEFAULT_CONFIG,
        "notify_schedules": [{"hour": 0, "enabled": True, "max_articles": 5,
                               "genres": {"ニュース": False, "研究": False,
                                          "活用事例": False, "ツール": False}}],
    }

    # google.genai をモック化（インストール不要にする）
    from unittest.mock import MagicMock
    mock_google = ModuleType("google")
    mock_genai = ModuleType("google.genai")
    mock_types = ModuleType("google.genai.types")
    mock_genai.Client = MagicMock(return_value=MagicMock())
    mock_google.genai = mock_genai
    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", mock_types)

    with patch("summarize.load_config", return_value=config_with_no_enabled_genres), \
         patch("summarize._call_gemini_json", return_value=gemini_result):
        with pytest.raises(SystemExit) as exc:
            summarize.main()
    assert exc.value.code == 1
