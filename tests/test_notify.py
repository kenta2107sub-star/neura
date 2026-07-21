"""FR-03：notify の Discord ペイロード生成の単体テスト。"""

import pytest
from unittest.mock import patch, mock_open
import json
import notify


def _article(title="OpenAI、GPT-5", cat="ニュース", source="HackerNews", url="https://x.com/a",
             importance=5, key_points=None, summary_ja="要約テキスト"):
    return {"title_ja": title, "summary_ja": summary_ja, "category": cat,
            "source": source, "url": url, "importance": importance,
            "key_points": key_points if key_points is not None else []}


def test_build_discord_payload_structure():
    payload = notify.build_discord_payload([_article()], "2026/06/18")
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "2026/06/18" in embed["title"]
    assert "1件" in embed["title"]
    assert len(embed["fields"]) == 1


def test_build_discord_payload_category_emoji():
    payload = notify.build_discord_payload([_article(cat="研究")], "2026/06/18")
    field = payload["embeds"][0]["fields"][0]
    assert "🔬" in field["name"]


def test_build_discord_payload_source_label_and_link():
    payload = notify.build_discord_payload([_article(source="Zenn")], "2026/06/18")
    field = payload["embeds"][0]["fields"][0]
    assert "Zenn 🇯🇵" in field["value"]
    assert "https://x.com/a" in field["value"]


def test_build_discord_payload_content_lists_all_titles():
    articles = [
        _article(title="記事A"),
        _article(title="記事B"),
        _article(title="記事C"),
    ]
    payload = notify.build_discord_payload(articles, "2026/06/18")
    content = payload["content"]
    assert "1. 記事A" in content
    assert "2. 記事B" in content
    assert "3. 記事C" in content


def test_build_discord_payload_includes_key_points():
    art = _article(key_points=["ポイント1", "ポイント2"])
    payload = notify.build_discord_payload([art], "2026/06/18")
    field = payload["embeds"][0]["fields"][0]
    assert "・ポイント1" in field["value"]
    assert "・ポイント2" in field["value"]


def test_fit_embed_within_limit_keeps_key_points():
    art = _article(key_points=["ポイント1"])
    embed = notify.fit_embed_to_char_limit([art], "2026/06/18")
    assert notify.embed_char_count(embed) <= notify.EMBED_CHAR_LIMIT
    assert "・ポイント1" in embed["fields"][0]["value"]


def test_fit_embed_removes_key_points_from_lowest_importance_first():
    long_kp = ["あ" * 40, "い" * 40, "う" * 40]
    long_summary = "要約" * 50
    articles = [
        _article(title=f"記事{i}", url=f"https://x.com/{i}", importance=i,
                 key_points=long_kp, summary_ja=long_summary)
        for i in range(1, 31)
    ]
    embed = notify.fit_embed_to_char_limit(articles, "2026/06/18")

    assert notify.embed_char_count(embed) <= notify.EMBED_CHAR_LIMIT
    field_low = next(f for f in embed["fields"] if f["name"].endswith("記事1"))
    field_high = next(f for f in embed["fields"] if f["name"].endswith("記事30"))
    assert "・" not in field_low["value"]  # 重要度最小の記事から key_points が消える
    assert "・" in field_high["value"]     # 重要度最大の記事はまだ key_points が残る


def test_fit_embed_truncates_summary_when_still_over_limit_after_removing_key_points():
    long_summary = "あ" * 300
    articles = [
        _article(title=f"記事{i}", url=f"https://x.com/{i}", importance=i,
                 key_points=["短いポイント"], summary_ja=long_summary)
        for i in range(1, 31)
    ]
    embed = notify.fit_embed_to_char_limit(articles, "2026/06/18")

    assert notify.embed_char_count(embed) <= notify.EMBED_CHAR_LIMIT
    field_low = next(f for f in embed["fields"] if f["name"].endswith("記事1"))
    assert "…" in field_low["value"]


def test_main_exits_when_articles_empty(monkeypatch, tmp_path):
    """記事0件のJSONを読み込んだ場合、Discord送信せずsys.exit(1)すること。"""
    empty_json = tmp_path / "summarized.json"
    empty_json.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")
    monkeypatch.setattr(notify, "INPUT_PATH", str(empty_json))

    with patch("notify.requests.post") as mock_post:
        with pytest.raises(SystemExit) as exc:
            notify.main()
    assert exc.value.code == 1
    mock_post.assert_not_called()
