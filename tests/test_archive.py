"""FR-04：archive の index.json 更新ロジックの単体テスト。"""

from unittest.mock import MagicMock, patch

import archive


def _article(cat):
    return {"title_ja": "t", "summary_ja": "s", "category": cat, "importance": 3,
            "url": "https://x.com/a", "source": "RSS", "published_at": "2026-06-18T00:00:00Z",
            "translation_ja": None}


def test_build_index_meta_counts_categories():
    arts = [_article("ニュース"), _article("ニュース"), _article("ツール")]
    meta = archive.build_index_meta("2026-06-18", "13:00", "2026-06-18_13", arts)
    assert meta["date"] == "2026-06-18"
    assert meta["time"] == "13:00"
    assert meta["file"] == "2026-06-18_13"
    assert meta["count"] == 3
    assert meta["categories"] == {"ニュース": 2, "ツール": 1}


def test_update_index_prepends_new_date():
    index = {"digests": [{"date": "2026-06-17", "time": "13:00", "count": 5, "categories": {}}]}
    meta = {"date": "2026-06-18", "time": "13:00", "count": 3, "categories": {"ニュース": 3}}
    out = archive.update_index(index, meta)
    assert out["digests"][0]["date"] == "2026-06-18"  # 先頭（降順維持）
    assert len(out["digests"]) == 2


def test_update_index_dedupes_same_date_and_time():
    index = {"digests": [{"date": "2026-06-18", "time": "13:00", "count": 1, "categories": {}}]}
    meta = {"date": "2026-06-18", "time": "13:00", "count": 7, "categories": {"ニュース": 7}}
    out = archive.update_index(index, meta)
    assert len(out["digests"]) == 1  # 同一 (date, time) は置換
    assert out["digests"][0]["count"] == 7


def test_update_index_keeps_different_time_same_date():
    index = {"digests": [{"date": "2026-06-18", "time": "13:00", "count": 5, "categories": {}}]}
    meta = {"date": "2026-06-18", "time": "20:00", "count": 3, "categories": {}}
    out = archive.update_index(index, meta)
    assert len(out["digests"]) == 2  # 日付同じでも時刻違いは別エントリ


def test_update_index_caps_at_100():
    index = {"digests": [{"date": f"2026-01-{i:02d}", "count": 0, "categories": {}} for i in range(1, 101)]}
    meta = {"date": "2026-06-18", "count": 1, "categories": {}}
    out = archive.update_index(index, meta)
    assert len(out["digests"]) == 100
    assert out["digests"][0]["date"] == "2026-06-18"


def _proc(returncode=0, stderr=""):
    return MagicMock(returncode=returncode, stderr=stderr)


def test_run_git_commands_push_succeeds_without_retry():
    """通常時：push が一発で成功すれば pull --rebase は呼ばれない。"""
    with patch("archive.subprocess.run", return_value=_proc(0)) as mock_run:
        archive.run_git_commands("2026-07-08")
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "push"] in calls
    assert ["git", "pull", "--rebase"] not in calls


def test_run_git_commands_retries_push_after_rebase_on_non_fast_forward():
    """push が non-fast-forward で失敗しても、pull --rebase 後の再pushが成功すれば正常終了する。"""
    # config x2, add, commit succeed → push fails → pull --rebase succeeds → push(retry) succeeds
    results = [_proc(0), _proc(0), _proc(0), _proc(0), _proc(1, "rejected"), _proc(0), _proc(0)]
    with patch("archive.subprocess.run", side_effect=results) as mock_run:
        archive.run_git_commands("2026-07-08")  # sys.exit を呼ばずに正常終了すること
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert calls.count(["git", "push"]) == 2
    assert ["git", "pull", "--rebase"] in calls


def test_run_git_commands_exits_when_rebase_fails():
    import pytest
    results = [_proc(0), _proc(0), _proc(0), _proc(0), _proc(1, "rejected"), _proc(1, "conflict")]
    with patch("archive.subprocess.run", side_effect=results):
        with pytest.raises(SystemExit) as exc:
            archive.run_git_commands("2026-07-08")
    assert exc.value.code == 1


def test_run_git_commands_exits_when_retry_push_also_fails():
    import pytest
    results = [_proc(0), _proc(0), _proc(0), _proc(0), _proc(1, "rejected"), _proc(0), _proc(1, "rejected again")]
    with patch("archive.subprocess.run", side_effect=results):
        with pytest.raises(SystemExit) as exc:
            archive.run_git_commands("2026-07-08")
    assert exc.value.code == 1
