"""FR-09：weekly_digest の集計・Discordペイロード生成ロジックの単体テスト。"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import weekly_digest

JST = timezone(timedelta(hours=9))


def _article(title, cat, importance, url):
    return {"title_ja": title, "summary_ja": "s", "category": cat, "importance": importance,
            "url": url, "source": "RSS", "published_at": "2026-06-18T00:00:00Z"}


def test_last_7_days_jst_returns_7_dates_descending():
    dates = weekly_digest.last_7_days_jst()
    assert len(dates) == 7
    assert dates == sorted(dates, reverse=True)


def test_collect_week_articles_reads_matching_files(tmp_path, monkeypatch):
    monkeypatch.setattr(weekly_digest, "DATA_DIR", str(tmp_path))
    (tmp_path / "2026-06-18_13.json").write_text(
        json.dumps({"articles": [_article("A", "ニュース", 5, "https://x.com/a")]}), encoding="utf-8"
    )
    (tmp_path / "2026-06-17_19.json").write_text(
        json.dumps({"articles": [_article("B", "研究", 3, "https://x.com/b")]}), encoding="utf-8"
    )
    index = {
        "digests": [
            {"date": "2026-06-18", "file": "2026-06-18_13"},
            {"date": "2026-06-17", "file": "2026-06-17_19"},
            {"date": "2026-06-01", "file": "2026-06-01_13"},  # 対象外の日付
        ]
    }
    articles = weekly_digest.collect_week_articles(index, {"2026-06-18", "2026-06-17"})
    assert len(articles) == 2
    assert {a["title_ja"] for a in articles} == {"A", "B"}


def test_collect_week_articles_skips_missing_file(tmp_path):
    index = {"digests": [{"date": "2026-06-18", "file": "2026-06-18_13"}]}
    with patch.object(weekly_digest, "DATA_DIR", str(tmp_path)):
        articles = weekly_digest.collect_week_articles(index, {"2026-06-18"})
    assert articles == []


def test_build_discord_payload_category_breakdown_and_top5():
    articles = [_article(f"記事{i}", "ニュース", i, f"https://x.com/{i}") for i in range(1, 8)]
    payload = weekly_digest.build_discord_payload(articles, "2026-06-12", "2026-06-18")
    embed = payload["embeds"][0]
    assert "計7件" in embed["title"]

    cat_field = next(f for f in embed["fields"] if f["name"] == "カテゴリ内訳")
    assert "ニュース 7件" in cat_field["value"]

    top_field = next(f for f in embed["fields"] if f["name"] == "今週の注目記事")
    # importance降順で上位5件のみ（記事7, 6, 5, 4, 3 が入り、記事1・記事2 は入らない）
    assert "記事7" in top_field["value"]
    assert "記事3" in top_field["value"]
    assert "記事2" not in top_field["value"]


def test_build_discord_payload_empty_articles():
    payload = weekly_digest.build_discord_payload([], "2026-06-12", "2026-06-18")
    embed = payload["embeds"][0]
    assert "計0件" in embed["title"]


def test_main_skips_when_no_data_for_week(monkeypatch, tmp_path):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps({"digests": []}), encoding="utf-8")
    monkeypatch.setattr(weekly_digest, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("weekly_digest.requests.post") as mock_post:
        weekly_digest.main()

    mock_post.assert_not_called()


def test_main_skips_when_index_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(weekly_digest, "INDEX_PATH", str(tmp_path / "not_exist.json"))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("weekly_digest.requests.post") as mock_post:
        weekly_digest.main()

    mock_post.assert_not_called()


def test_main_sends_when_data_exists(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    today = weekly_digest.last_7_days_jst()[0]
    (data_dir / f"{today}_13.json").write_text(
        json.dumps({"articles": [_article("A", "ニュース", 5, "https://x.com/a")]}), encoding="utf-8"
    )
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps({"digests": [{"date": today, "file": f"{today}_13"}]}), encoding="utf-8")

    monkeypatch.setattr(weekly_digest, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(weekly_digest, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("weekly_digest.requests.post") as mock_post:
        mock_post.return_value.status_code = 204
        weekly_digest.main()

    mock_post.assert_called_once()


def test_main_exits_when_webhook_url_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        weekly_digest.main()
    assert exc.value.code == 1


def test_main_exits_when_discord_returns_non_204(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    today = weekly_digest.last_7_days_jst()[0]
    (data_dir / f"{today}_13.json").write_text(
        json.dumps({"articles": [_article("A", "ニュース", 5, "https://x.com/a")]}), encoding="utf-8"
    )
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps({"digests": [{"date": today, "file": f"{today}_13"}]}), encoding="utf-8")

    monkeypatch.setattr(weekly_digest, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(weekly_digest, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("weekly_digest.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        with pytest.raises(SystemExit) as exc:
            weekly_digest.main()
    assert exc.value.code == 1
