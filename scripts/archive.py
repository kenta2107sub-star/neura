"""FR-04：JSONアーカイブ保存。

``/tmp/neura_summarized.json`` を読み込み、日次JSONファイルの生成・index.json 更新・
git commit & push を行う。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from schemas import Article

INPUT_PATH = "/tmp/neura_summarized.json"
STATUS_SRC_PATH = "/tmp/neura_collect_status.json"
DATA_DIR = "docs/data"
INDEX_PATH = os.path.join(DATA_DIR, "index.json")
MAX_INDEX_DATES = 100


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_index_meta(today: str, time_str: str, file_key: str, articles: list[Article]) -> dict:
    """日次記事から index 用メタ（件数・カテゴリ内訳・タイトル一覧）を生成する。"""
    cats = Counter(a.get("category", "") for a in articles)
    cats.pop("", None)
    titles = [{"t": a.get("title_ja", ""), "c": a.get("category", "")} for a in articles[:10]]
    return {
        "date": today,
        "time": time_str,
        "file": file_key,
        "count": len(articles),
        "categories": dict(cats),
        "titles": titles,
    }


def update_index(index: dict, meta: dict) -> dict:
    """index に meta を追加する。同一 (date, time) は除去して先頭に追加し、最大100件に切り詰める。"""
    key = (meta["date"], meta.get("time", ""))
    digests = [d for d in index.get("digests", []) if (d.get("date"), d.get("time", "")) != key]
    digests.insert(0, meta)
    return {"digests": digests[:MAX_INDEX_DATES]}


def run_git_commands(today: str) -> None:
    commit_commands = [
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "add", "docs/data/"],
        ["git", "commit", "-m", f"chore: add daily digest {today}"],
    ]
    for cmd in commit_commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Git command failed: {' '.join(cmd)}")
            print(result.stderr)
            sys.exit(1)

    # push が non-fast-forward で失敗した場合（設定画面が同タイミングで
    # config/config.json を更新した等）、pull --rebase 後に1回だけ再試行する
    push = subprocess.run(["git", "push"], capture_output=True, text=True)
    if push.returncode != 0:
        print("[WARN]  archive: git push 失敗（non-fast-forward の可能性）→ git pull --rebase 後に1回だけ再試行")
        print(push.stderr)
        rebase = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
        if rebase.returncode != 0:
            print("[ERROR] Git command failed: git pull --rebase")
            print(rebase.stderr)
            sys.exit(1)
        retry = subprocess.run(["git", "push"], capture_output=True, text=True)
        if retry.returncode != 0:
            print("[ERROR] Git command failed: git push (retry)")
            print(retry.stderr)
            sys.exit(1)


def main() -> None:
    articles: list[Article] = load_json(INPUT_PATH)
    now_jst = datetime.now(tz=timezone.utc) + timedelta(hours=9)
    today = now_jst.strftime("%Y-%m-%d")
    hour_jst = now_jst.hour
    file_key = f"{today}_{hour_jst:02d}"
    time_str = f"{hour_jst:02d}:00"
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 0. ソース別収集ステータスファイルをリポジトリへコピー（git add docs/data/ で一緒にコミット）
    if os.path.exists(STATUS_SRC_PATH):
        os.makedirs(DATA_DIR, exist_ok=True)
        shutil.copy(STATUS_SRC_PATH, os.path.join(DATA_DIR, "collect_status.json"))
        print(f"[INFO]  archive: collect_status.json 更新")

    # 1. 日次JSONを生成（ファイル名に JST 時刻を含める）
    daily_data = {"date": today, "time": time_str, "generated_at": generated_at, "articles": articles}
    daily_path = os.path.join(DATA_DIR, f"{file_key}.json")
    save_json(daily_path, daily_data)
    print(f"[INFO]  archive: {daily_path} 生成")

    # 2. index.json を更新（件数・カテゴリ内訳を集計して追記。同一(date,time)は上書き、最大100件）
    meta = build_index_meta(today, time_str, file_key, articles)
    index = load_json(INDEX_PATH) if os.path.exists(INDEX_PATH) else {"digests": []}
    index = update_index(index, meta)
    save_json(INDEX_PATH, index)
    print(f"[INFO]  archive: index.json 更新（{len(index['digests'])}件）")

    # 3. git commit & push
    run_git_commands(today)
    print("[INFO]  archive: git push 完了")


if __name__ == "__main__":
    main()
