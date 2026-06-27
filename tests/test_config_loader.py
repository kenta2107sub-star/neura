"""FR-06：config_loader の単体テスト。"""

import json

import config_loader


def test_load_bundled_config_structure():
    """バンドルされた config.json が正しく読み込まれること。"""
    cfg = config_loader.load_config()
    assert len(cfg["sources"]) == 10
    assert "{articles}" in cfg["gemini_prompt"]
    assert len(cfg["keywords"]["en"]) > 0
    assert "notify_schedules" in cfg
    assert len(cfg["notify_schedules"]) > 0


def test_fallback_on_missing_file():
    cfg = config_loader.load_config("/tmp/__neura_nonexistent__.json")
    assert cfg == config_loader.DEFAULT_CONFIG


def test_fallback_on_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not valid json ", encoding="utf-8")
    cfg = config_loader.load_config(str(bad))
    assert cfg == config_loader.DEFAULT_CONFIG


def test_partial_config_merges_defaults(tmp_path):
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"sources": []}), encoding="utf-8")
    cfg = config_loader.load_config(str(partial))
    # 欠けている keywords / gemini_prompt はデフォルトで補完される
    assert "{articles}" in cfg["gemini_prompt"]
    assert len(cfg["keywords"]["en"]) > 0
    assert "notify_schedules" in cfg


def test_bundled_prompt_has_articles_placeholder():
    """config.json の gemini_prompt に {articles} が含まれること（カスタマイズ可能だが必須）。"""
    cfg = config_loader.load_config()
    assert "{articles}" in cfg["gemini_prompt"]


def test_migration_run_hour_jst_to_notify_schedules(tmp_path):
    """旧フィールド run_hour_jst が notify_schedules に変換されること。"""
    old_cfg = {"run_hour_jst": 9, "sources": [], "keywords": {"en": [], "ja": []},
               "gemini_prompt": "{articles}"}
    f = tmp_path / "old.json"
    f.write_text(json.dumps(old_cfg), encoding="utf-8")
    cfg = config_loader.load_config(str(f))
    assert "notify_schedules" in cfg
    assert cfg["notify_schedules"][0]["hour"] == 9
    assert cfg["notify_schedules"][0]["enabled"] is True


def test_migration_global_genres_to_slot(tmp_path):
    """グローバルの genres / max_articles がスロット内に引き継がれること。"""
    cfg_data = {
        "genres": {"ニュース": True, "研究": False, "活用事例": True, "ツール": True},
        "max_articles": 7,
        "notify_schedules": [{"hour": 13, "enabled": True}],
        "sources": [], "keywords": {"en": [], "ja": []}, "gemini_prompt": "{articles}",
    }
    f = tmp_path / "migrated.json"
    f.write_text(json.dumps(cfg_data), encoding="utf-8")
    cfg = config_loader.load_config(str(f))
    slot = cfg["notify_schedules"][0]
    assert slot["genres"]["研究"] is False
    assert slot["max_articles"] == 7
    # グローバルキーは残らない
    assert "genres" not in cfg
    assert "max_articles" not in cfg
