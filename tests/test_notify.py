"""FR-03：notify の Discord ペイロード生成の単体テスト。"""

import notify


def _article(title="OpenAI、GPT-5", cat="ニュース", source="HackerNews"):
    return {"title_ja": title, "summary_ja": "要約テキスト", "category": cat,
            "source": source, "url": "https://x.com/a", "importance": 5}


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
