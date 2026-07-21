"""FR-08：remind の未読リマインド送信ロジックの単体テスト。"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import remind

JST = timezone(timedelta(hours=9))


def _yesterday_jst() -> str:
    return (datetime.now(tz=JST) - timedelta(days=1)).strftime("%Y-%m-%d")


def test_has_digest_for_date_true():
    index = {"digests": [{"date": "2026-06-18", "time": "13:00"}, {"date": "2026-06-17", "time": "19:00"}]}
    assert remind.has_digest_for_date(index, "2026-06-18") is True


def test_has_digest_for_date_false():
    index = {"digests": [{"date": "2026-06-17", "time": "19:00"}]}
    assert remind.has_digest_for_date(index, "2026-06-18") is False


def test_has_digest_for_date_empty_index():
    assert remind.has_digest_for_date({}, "2026-06-18") is False


def test_build_site_url_from_github_repository(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "kenta2107sub-star/neura")
    assert remind.build_site_url() == "https://kenta2107sub-star.github.io/neura/"


def test_build_site_url_missing_env(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert remind.build_site_url() == ""


def test_main_sends_reminder_when_yesterday_digest_exists(monkeypatch, tmp_path):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps({"digests": [{"date": _yesterday_jst(), "time": "19:00"}]}), encoding="utf-8")
    monkeypatch.setattr(remind, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("remind.requests.post") as mock_post:
        mock_post.return_value.status_code = 204
        remind.main()

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "昨日のAIニュースダイジェスト" in payload["content"]


def test_main_skips_when_no_yesterday_digest(monkeypatch, tmp_path):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps({"digests": [{"date": "2000-01-01", "time": "19:00"}]}), encoding="utf-8")
    monkeypatch.setattr(remind, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("remind.requests.post") as mock_post:
        remind.main()

    mock_post.assert_not_called()


def test_main_skips_when_index_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(remind, "INDEX_PATH", str(tmp_path / "not_exist.json"))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("remind.requests.post") as mock_post:
        remind.main()

    mock_post.assert_not_called()


def test_main_exits_when_webhook_url_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        remind.main()
    assert exc.value.code == 1


def test_main_exits_when_discord_returns_non_204(monkeypatch, tmp_path):
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps({"digests": [{"date": _yesterday_jst(), "time": "19:00"}]}), encoding="utf-8")
    monkeypatch.setattr(remind, "INDEX_PATH", str(index_path))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook")

    with patch("remind.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        with pytest.raises(SystemExit) as exc:
            remind.main()
    assert exc.value.code == 1
