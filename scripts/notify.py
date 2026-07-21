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


EMBED_CHAR_LIMIT = 6000
SUMMARY_TRUNCATE_LEN = 100


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_field(art: Article, include_key_points: bool, truncate_summary: bool = False) -> dict:
    emoji = CATEGORY_EMOJI.get(art.get("category", ""), "📄")
    source = SOURCE_LABEL.get(art.get("source", ""), art.get("source", ""))
    summary = art["summary_ja"]
    if truncate_summary and len(summary) > SUMMARY_TRUNCATE_LEN:
        summary = summary[:SUMMARY_TRUNCATE_LEN] + "…"

    lines = [summary]
    if include_key_points:
        lines += [f"・{kp}" for kp in art.get("key_points", [])]
    lines.append(f"[{source}]({art['url']})\n​")

    return {
        "name": f"{emoji} {art['title_ja']}",
        "value": "\n".join(lines),
        "inline": False,
    }


def embed_char_count(embed: dict) -> int:
    total = len(embed.get("title", "")) + len(embed.get("footer", {}).get("text", ""))
    for f in embed.get("fields", []):
        total += len(f.get("name", "")) + len(f.get("value", ""))
    return total


def build_embed(articles: list[Article], date: str, fields: list[dict]) -> dict:
    return {
        "title": f"🧠 Neura Daily — {date}（{len(articles)}件）",
        "color": 0x7C6AFF,  # アクセントパープル
        "fields": fields,
        "footer": {"text": "Neura by GitHub Actions"},
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def fit_embed_to_char_limit(articles: list[Article], date: str) -> dict:
    """全embed合計が6,000字を超える場合、importance昇順に key_points → summary_ja の順で削って収める（FR-03）。"""
    fields = {art["url"]: build_field(art, include_key_points=True) for art in articles}
    embed = build_embed(articles, date, [fields[a["url"]] for a in articles])
    if embed_char_count(embed) <= EMBED_CHAR_LIMIT:
        return embed

    by_importance_asc = sorted(articles, key=lambda a: a.get("importance", 0))

    for art in by_importance_asc:
        fields[art["url"]] = build_field(art, include_key_points=False)
        embed = build_embed(articles, date, [fields[a["url"]] for a in articles])
        if embed_char_count(embed) <= EMBED_CHAR_LIMIT:
            return embed

    for art in by_importance_asc:
        fields[art["url"]] = build_field(art, include_key_points=False, truncate_summary=True)
        embed = build_embed(articles, date, [fields[a["url"]] for a in articles])
        if embed_char_count(embed) <= EMBED_CHAR_LIMIT:
            return embed

    return embed


def build_discord_payload(articles: list[Article], date: str) -> dict:
    # content：Discordのプッシュ通知プレビューに全記事タイトルを表示するためのプレーンテキスト
    # （embedsのみだとプッシュ通知本文に記事タイトルが反映されないため）
    title_list = "\n".join(f"{i + 1}. {art['title_ja']}" for i, art in enumerate(articles))

    return {
        "content": f"🧠 Neura Daily — {date}（{len(articles)}件）\n{title_list}",
        "embeds": [fit_embed_to_char_limit(articles, date)],
    }


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set")
        sys.exit(1)

    articles: list[Article] = load_json(INPUT_PATH)

    if not articles:
        print("[ERROR] notify: 通知対象の記事が0件のため送信をスキップ")
        sys.exit(1)

    date = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")

    payload = build_discord_payload(articles, date)
    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT)

    if response.status_code != 204:
        print(f"[ERROR] Discord webhook failed: {response.status_code}")
        sys.exit(1)

    print(f"[INFO]  notify: Discord通知完了（{len(articles)}件）")


if __name__ == "__main__":
    main()
