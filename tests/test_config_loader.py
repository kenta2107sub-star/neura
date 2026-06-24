"""FR-06：config_loader の単体テスト。"""

import json

import config_loader


def test_load_default_config_from_bundled_file():
    cfg = config_loader.load_config()
    assert len(cfg["sources"]) == 8
    assert set(cfg["genres"].keys()) == {"ニュース", "研究", "活用事例", "ツール"}
    assert "{articles}" in cfg["gemini_prompt"]
    assert len(cfg["keywords"]["en"]) > 0


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
    partial.write_text(json.dumps({"genres": {"ニュース": False}}), encoding="utf-8")
    cfg = config_loader.load_config(str(partial))
    # 欠けている sources / keywords / gemini_prompt はデフォルトで補完される
    assert "sources" in cfg and len(cfg["sources"]) == 8
    assert "{articles}" in cfg["gemini_prompt"]


def test_bundled_config_matches_default_prompt():
    cfg = config_loader.load_config()
    assert cfg["gemini_prompt"] == config_loader.DEFAULT_CONFIG["gemini_prompt"]
