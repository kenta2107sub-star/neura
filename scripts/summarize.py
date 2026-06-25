"""FR-02：AI要約・分類。

``/tmp/neura_collected.json`` を読み込み、Gemini Flash API で要約・全文翻訳・カテゴリ・
重要度を生成する。config の genres で無効カテゴリを除外し、重要度上位を選定して
``/tmp/neura_summarized.json`` に書き出す。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

from config_loader import DEFAULT_GEMINI_PROMPT, load_config
from schemas import Article, CollectedArticle

INPUT_PATH = "/tmp/neura_collected.json"
OUTPUT_PATH = "/tmp/neura_summarized.json"
MODEL_NAME = "gemini-2.5-flash"
GEMINI_TIMEOUT = 30  # NF-01
BODY_MAX_CHARS_IN_PROMPT = 3000
MAX_ARTICLES = 10  # スロット設定が未設定の場合のフォールバック
JST = timezone(timedelta(hours=9))


def get_current_slot(notify_schedules: list) -> dict:
    """現在の JST 時刻に対応するスロットを返す。一致しなければ最初の有効スロットを返す。"""
    current_hour = datetime.now(JST).hour
    for slot in notify_schedules:
        if slot.get("enabled") and slot.get("hour") == current_hour:
            return slot
    for slot in notify_schedules:
        if slot.get("enabled"):
            return slot
    return {}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_url(url: str) -> str:
    return url.rstrip("/").split("?")[0]


def select_articles(result: list[Article], genres: dict[str, bool], max_articles: int = MAX_ARTICLES) -> list[Article]:
    """無効カテゴリ(genres=false)を除外し、重要度降順で上位 max_articles 件を返す。"""
    enabled = {g for g, on in genres.items() if on}
    filtered = [r for r in result if r.get("category") in enabled]
    return sorted(filtered, key=lambda x: x.get("importance", 0), reverse=True)[:max_articles]


def build_prompt(articles: list[CollectedArticle], template: str) -> str:
    articles_text = "\n\n".join(
        f"[{i + 1}] タイトル: {a['title']}\nURL: {a['url']}\nソース: {a['source']}\n"
        f"本文: {a['body_text'][:BODY_MAX_CHARS_IN_PROMPT] if a.get('body_text') else '（本文取得不可）'}"
        for i, a in enumerate(articles)
    )

    if "{articles}" not in template:
        print("[WARN]  summarize: gemini_prompt に {articles} が無いためデフォルトを使用")
        template = DEFAULT_GEMINI_PROMPT

    return template.replace("{articles}", articles_text)


def main() -> None:
    from google import genai  # 遅延import（モジュール読込を軽量に保つ）
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set")
        sys.exit(1)

    config = load_config()  # FR-06
    articles: list[CollectedArticle] = load_json(INPUT_PATH)

    prompt = build_prompt(articles, config["gemini_prompt"])

    client = genai.Client(api_key=api_key)

    max_retries = 3
    retry_wait = 30  # seconds
    response = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            break
        except Exception as e:
            print(f"[WARN]  summarize: Gemini API attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_wait)
    if response is None:
        print("[ERROR] Gemini API failed after all retries")
        sys.exit(1)

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] Failed to parse Gemini response: {e}")
        sys.exit(1)

    if not isinstance(result, list):
        print("[ERROR] Failed to parse Gemini response: not a JSON array")
        sys.exit(1)

    # Gemini が同じ URL を重複して返すケースを除去
    seen_urls: set[str] = set()
    deduped: list[Article] = []
    for r in result:
        key = normalize_url(r.get("url", ""))
        if key and key not in seen_urls:
            seen_urls.add(key)
            deduped.append(r)
    if len(deduped) < len(result):
        print(f"[WARN]  summarize: Gemini重複 {len(result) - len(deduped)}件を除去")
    result = deduped

    # 現在のスロット設定を取得（JST 時刻で照合）
    slot = get_current_slot(config.get("notify_schedules", []))
    slot_genres = slot.get("genres") or {"ニュース": True, "研究": True, "活用事例": True, "ツール": True}
    slot_max = max(1, min(10, int(slot.get("max_articles", MAX_ARTICLES))))
    print(f"[INFO]  summarize: スロット hour={slot.get('hour','?')} genres={list(slot_genres)} max={slot_max}")

    # FR-06：無効カテゴリ（genres=false）を除外してから重要度上位を選定する
    result_sorted = select_articles(result, slot_genres, slot_max)
    if not result_sorted:
        print("[WARN]  summarize: 有効カテゴリの記事が0件（genres設定を確認）")

    if len(result_sorted) < 5:
        print(f"[WARN]  summarize: Only {len(result_sorted)} articles selected")

    # 元記事の source / published_at を URL 照合で復元する
    url_map = {normalize_url(a["url"]): a for a in articles}
    for item in result_sorted:
        original = url_map.get(normalize_url(item.get("url", "")), {})
        if not original:
            print(f"[WARN]  summarize: URL照合失敗 → {item.get('url')}")
        item["source"] = original.get("source", "")
        item["published_at"] = original.get("published_at", "")

    save_json(OUTPUT_PATH, result_sorted)
    print(f"[INFO]  summarize: Gemini → {len(result_sorted)}件選出 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
