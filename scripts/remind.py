"""FR-08：未読リマインド通知。

``docs/data/index.json`` を読み込み、前日分の配信が1件でもあれば
Discord へ簡易リマインドメッセージ（Embedなし、プレーンテキスト1通）を送信する。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

INDEX_PATH = "docs/data/index.json"
HTTP_TIMEOUT = 10
JST = timezone(timedelta(hours=9))


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def has_digest_for_date(index: dict, date: str) -> bool:
    return any(d.get("date") == date for d in index.get("digests", []))


def build_site_url() -> str:
    """GitHub Actions が自動提供する GITHUB_REPOSITORY（"owner/repo"）からサイトURLを組み立てる。"""
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    owner, _, repo = repo_full.partition("/")
    if not owner or not repo:
        return ""
    return f"https://{owner}.github.io/{repo}/"


def main() -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set")
        sys.exit(1)

    yesterday = (datetime.now(tz=JST) - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        index = load_json(INDEX_PATH)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN]  remind: index.json not found or invalid, skip reminder ({e})")
        return

    if not has_digest_for_date(index, yesterday):
        print(f"[INFO]  remind: No digest for {yesterday}, skip reminder")
        return

    site_url = build_site_url()
    payload = {"content": f"🌙 昨日のAIニュースダイジェスト、まだご覧になっていない方はこちら → {site_url}"}

    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT)
    if response.status_code != 204:
        print(f"[ERROR] Discord webhook failed: {response.status_code}")
        sys.exit(1)

    print(f"[INFO]  remind: リマインド送信完了（{yesterday}分）")


if __name__ == "__main__":
    main()
