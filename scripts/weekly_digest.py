"""FR-09：週次ダイジェスト配信。

``docs/data/index.json`` から直近7日分の digests エントリを抽出し、対応する
``docs/data/{file}.json`` を集計して、件数サマリー・カテゴリ内訳・注目記事トップ5を
Discord へ送信する。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

DATA_DIR = "docs/data"
INDEX_PATH = os.path.join(DATA_DIR, "index.json")
HTTP_TIMEOUT = 10
JST = timezone(timedelta(hours=9))
TOP_N = 5

CATEGORY_EMOJI = {
    "ニュース": "🗞️",
    "研究": "🔬",
    "活用事例": "💡",
    "ツール": "🛠️",
}
CATEGORY_ORDER = ["ニュース", "研究", "活用事例", "ツール"]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def last_7_days_jst() -> list[str]:
    today = datetime.now(tz=JST).date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def collect_week_articles(index: dict, dates: set[str]) -> list[dict]:
    """digestsからdatesに含まれるエントリを抽出し、対応するdocs/data/{file}.jsonのarticlesを集約する。"""
    entries = [d for d in index.get("digests", []) if d.get("date") in dates]
    articles: list[dict] = []
    for entry in entries:
        file_key = entry.get("file")
        if not file_key:
            continue
        path = os.path.join(DATA_DIR, f"{file_key}.json")
        try:
            daily = load_json(path)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[WARN]  weekly_digest: {path} の読み込みに失敗 ({e})")
            continue
        articles.extend(daily.get("articles", []))
    return articles


def build_discord_payload(articles: list[dict], start_date: str, end_date: str) -> dict:
    categories: dict[str, int] = {}
    for art in articles:
        cat = art.get("category", "")
        categories[cat] = categories.get(cat, 0) + 1

    cat_line = " / ".join(
        f"{CATEGORY_EMOJI.get(cat, '📄')} {cat} {categories.get(cat, 0)}件"
        for cat in CATEGORY_ORDER
        if categories.get(cat)
    )

    top_articles = sorted(articles, key=lambda a: a.get("importance", 0), reverse=True)[:TOP_N]
    top_lines = "\n".join(
        f"{CATEGORY_EMOJI.get(a.get('category', ''), '📄')} {a['title_ja']} → {a['url']}"
        for a in top_articles
    )

    header = f"📅 Neura Weekly — {start_date}〜{end_date}（計{len(articles)}件）"

    return {
        "embeds": [
            {
                "title": header,
                "color": 0x7C6AFF,
                "fields": [
                    {"name": "カテゴリ内訳", "value": cat_line or "（記事なし）", "inline": False},
                    {"name": "今週の注目記事", "value": top_lines or "（記事なし）", "inline": False},
                ],
                "footer": {"text": "Neura Weekly Digest"},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
        ]
    }


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set")
        sys.exit(1)

    dates = last_7_days_jst()
    start_date, end_date = dates[-1], dates[0]

    try:
        index = load_json(INDEX_PATH)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN]  weekly_digest: index.json not found or invalid, skip weekly digest ({e})")
        return

    articles = collect_week_articles(index, set(dates))
    if not articles:
        print("[INFO]  weekly_digest: No data for the past week, skip weekly digest")
        return

    payload = build_discord_payload(articles, start_date, end_date)
    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT)

    if response.status_code != 204:
        print(f"[ERROR] Discord webhook failed: {response.status_code}")
        sys.exit(1)

    print(f"[INFO]  weekly_digest: 週次ダイジェスト送信完了（{len(articles)}件）")


if __name__ == "__main__":
    main()
