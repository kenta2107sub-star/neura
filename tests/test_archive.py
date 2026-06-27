"""FR-04：archive の index.json 更新ロジックの単体テスト。"""

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
