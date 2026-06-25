"""FR-03：Discord通知。

``/tmp/neura_summarized.json`` を読み込み、Discord Webhook に Embed 形式で投稿する。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests

from schemas import Article

INPUT_PATH = "/tmp/neura_summarized.json"
HTTP_TIMEOUT = 10

CATEGORY_EMOJI = {
    "ニュース": "🗞️",
    "研究": "🔬",
    "活用事例": "💡",
    "ツール": "🛠️",
}
SOURCE_LABEL = {
    "HackerNews": "HackerNews",
    "Reddit": "Reddit",
    "RSS": "RSS",
    "Zenn": "Zenn 🇯🇵",
    "HatenaBookmark": "はてブ 🇯🇵",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_discord_payload(articles: list[Article], date: str) -> dict:
    fields = []
    for i, art in enumerate(articles):
        emoji = CATEGORY_EMOJI.get(art.get("category", ""), "📄")
        source = SOURCE_LABEL.get(art.get("source", ""), art.get("source", ""))
        fields.append(
            {
                "name": f"{emoji} {art['title_ja']}",
                "value": f"{art['summary_ja']}\n[{source}]({art['url']})",
                "inline": False,
            }
        )
        if i < len(articles) - 1:
            fields.append({"name": "​", "value": "\n​", "inline": False})

    return {
        "embeds": [
            {
                "title": f"🧠 Neura Daily — {date}（{len(articles)}件）",
                "color": 0x7C6AFF,  # アクセントパープル
                "fields": fields,
                "footer": {"text": "Neura by GitHub Actions"},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
        ]
    }


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set")
        sys.exit(1)

    articles: list[Article] = load_json(INPUT_PATH)
    date = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")

    payload = build_discord_payload(articles, date)
    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT)

    if response.status_code != 204:
        print(f"[ERROR] Discord webhook failed: {response.status_code}")
        sys.exit(1)

    print(f"[INFO]  notify: Discord通知完了（{len(articles)}件）")


if __name__ == "__main__":
    main()
