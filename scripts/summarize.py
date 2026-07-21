"""FR-02：AI要約・分類。

``/tmp/neura_collected.json`` を読み込み、Gemini Flash API を2段階で呼び出す。
Stage 1: タイトル＋冒頭700文字で記事を選定（URLリストを返す）
Stage 2: 選定記事の本文フルで翻訳・要約・カテゴリ・重要度を生成し
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
BODY_MAX_CHARS_SELECT = 700      # Stage 1 選定用（タイトル＋冒頭のみ）
BODY_MAX_CHARS_TRANSLATE = 5000  # Stage 2 翻訳用（フル本文）
SELECT_MAX = 10                  # Stage 1 で選ぶ件数の上限
MAX_ARTICLES = 10  # スロット設定が未設定の場合のフォールバック
JST = timezone(timedelta(hours=9))

VALID_CATEGORIES = {"ニュース", "研究", "活用事例", "ツール"}

CATEGORY_NORM: dict[str, str] = {
    # 英語表記
    "news": "ニュース",
    "research": "研究",
    "use case": "活用事例", "use cases": "活用事例",
    "application": "活用事例", "applications": "活用事例",
    "tool": "ツール", "tools": "ツール",
    "product": "ツール", "products": "ツール",
    # 日本語バリエーション
    "ニュース・動向": "ニュース", "最新ニュース": "ニュース",
    "研究・論文": "研究", "学術研究": "研究",
    "活用事例・ビジネス": "活用事例", "活用事例・実践": "活用事例",
    "ツール・製品": "ツール", "ツール・サービス": "ツール",
}

SELECTION_PROMPT = (
    "以下のAI関連記事から、AIを学び始めた一般人が「面白い・試してみたい」と感じる記事を最大{n}件選んでください。\n"
    "次のジャンルに該当する記事のみを選んでください（それ以外のジャンルの記事は選ばないでください）: {genres}\n"
    "後工程で数件が除外される可能性があるため、該当ジャンルの記事が複数あるなら少なめに絞らず、"
    "{n}件に近づくよう可能な限り多く選んでください。\n"
    "選んだ記事のURLだけをJSON配列（文字列のリスト）で返してください。\n\n"
    "記事一覧:\n"
    "{articles}\n\n"
    "URLのJSON配列のみを返してください。説明文は不要です。"
)


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


def normalize_category(cat: str | None) -> str:
    """Geminiが返したカテゴリ値を正規4値にマッピングする。"""
    if not cat:
        return ""
    if cat in VALID_CATEGORIES:
        return cat
    normalized = CATEGORY_NORM.get(cat) or CATEGORY_NORM.get(cat.lower().strip())
    if normalized:
        print(f"[INFO]  summarize: category正規化 '{cat}' → '{normalized}'")
        return normalized
    print(f"[WARN]  summarize: 未知のcategory '{cat}' → フィルタで除外される")
    return cat


def select_articles(result: list[Article], genres: dict[str, bool], max_articles: int = MAX_ARTICLES) -> list[Article]:
    """無効カテゴリ(genres=false)を除外し、重要度降順で上位 max_articles 件を返す。"""
    enabled = {g for g, on in genres.items() if on}
    filtered = [r for r in result if r.get("category") in enabled]
    return sorted(filtered, key=lambda x: x.get("importance", 0), reverse=True)[:max_articles]


def build_selection_prompt(articles: list[CollectedArticle], n: int = SELECT_MAX, genres: dict[str, bool] | None = None) -> str:
    """Stage 1 用：タイトル＋冒頭文のみで選定プロンプトを構築する。"""
    enabled = [g for g, on in genres.items() if on] if genres else list(VALID_CATEGORIES)
    genres_text = "・".join(enabled) if enabled else "すべて"
    articles_text = "\n\n".join(
        f"[{i + 1}] タイトル: {a['title']}\n"
        f"    URL: {a['url']}\n"
        f"    ソース: {a['source']}\n"
        f"    本文: {a['body_text'][:BODY_MAX_CHARS_SELECT] if a.get('body_text') else '（本文取得不可）'}"
        for i, a in enumerate(articles)
    )
    return SELECTION_PROMPT.format(n=n, genres=genres_text, articles=articles_text)


def build_prompt(articles: list[CollectedArticle], template: str) -> str:
    """Stage 2 用：フル本文で翻訳・要約プロンプトを構築する。"""
    articles_text = "\n\n".join(
        f"[{i + 1}] タイトル: {a['title']}\nURL: {a['url']}\nソース: {a['source']}\n"
        f"本文: {a['body_text'][:BODY_MAX_CHARS_TRANSLATE] if a.get('body_text') else '（本文取得不可）'}"
        for i, a in enumerate(articles)
    )

    if "{articles}" not in template:
        print("[WARN]  summarize: gemini_prompt に {articles} が無いためデフォルトを使用")
        template = DEFAULT_GEMINI_PROMPT

    return template.replace("{articles}", articles_text)


def _call_gemini(client, prompt: str, types, response_schema=None) -> str:
    """リトライ付き Gemini 呼び出し。レスポンステキストを返す。API例外のみリトライ対象。失敗時は sys.exit(1)。"""
    max_retries = 5
    retry_wait = 60
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.3,
                    max_output_tokens=32768,
                    http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT * 1000),  # ミリ秒指定（NF-01）
                ),
            )
            return response.text
        except Exception as e:
            print(f"[WARN]  summarize: Gemini API attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_wait)
    print("[ERROR] Gemini API failed after all retries")
    sys.exit(1)


def _call_gemini_json(client, prompt: str, types, response_schema=None, max_retries: int = 3) -> list:
    """Stage 2専用。API呼び出し＋JSONパースをセットでリトライする。
    Geminiが不正なJSONを返した場合も再呼び出しして回復を試みる。失敗時は sys.exit(1)。
    """
    retry_wait = 30
    for attempt in range(1, max_retries + 1):
        text = _call_gemini(client, prompt, types, response_schema=response_schema)
        try:
            result = json.loads(text)
            if not isinstance(result, list):
                raise ValueError("not a JSON array")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN]  summarize: Stage 2 JSON parse attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_wait)
    print("[ERROR] Gemini API failed after all retries")
    sys.exit(1)


def main() -> None:
    from google import genai  # 遅延import（モジュール読込を軽量に保つ）
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set")
        sys.exit(1)

    config = load_config()  # FR-06
    articles: list[CollectedArticle] = load_json(INPUT_PATH)
    client = genai.Client(api_key=api_key)

    # Stage 2 用レスポンススキーマ：category を enum に強制して null 返却を防ぐ
    article_schema = types.Schema(
        type=types.Type.ARRAY,
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "url": types.Schema(type=types.Type.STRING),
                "title_ja": types.Schema(type=types.Type.STRING),
                "summary_ja": types.Schema(type=types.Type.STRING),
                "key_points": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "translation_ja": types.Schema(type=types.Type.STRING, nullable=True),
                "category": types.Schema(
                    type=types.Type.STRING,
                    enum=["ニュース", "研究", "活用事例", "ツール"],
                ),
                "importance": types.Schema(type=types.Type.INTEGER),
            },
            required=["url", "title_ja", "summary_ja", "key_points", "category", "importance"],
        ),
    )

    # スロット設定を Stage 1 の前に取得してジャンル誘導に使う
    slot = get_current_slot(config.get("notify_schedules", []))
    slot_genres = slot.get("genres") or {"ニュース": True, "研究": True, "活用事例": True, "ツール": True}
    slot_max = max(1, min(10, int(slot.get("max_articles", MAX_ARTICLES))))
    enabled_genres = sorted(g for g, on in slot_genres.items() if on)
    print(f"[INFO]  summarize: スロット hour={slot.get('hour','?')} 有効ジャンル={enabled_genres} max={slot_max}")

    # ── Stage 1: タイトル＋冒頭文で選定（有効ジャンルをハード制約として指示） ─────
    # Stage 2 の応答が長くなりすぎて途中で切れるのを防ぐため、
    # スロットの max_articles に近い件数だけを選ぶ（ジャンル誤判定・重複除去の余裕分として+5、SELECT_MAXでキャップ）
    select_n = min(SELECT_MAX, slot_max + 5)
    print(f"[INFO]  summarize: Stage 1 選定（{len(articles)}件 → 最大{select_n}件）")
    sel_text = _call_gemini(client, build_selection_prompt(articles, n=select_n, genres=slot_genres), types)
    try:
        selected_urls: list[str] = json.loads(sel_text)
        if not isinstance(selected_urls, list):
            raise ValueError("not a list")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN]  summarize: Stage 1 パース失敗 → 全件を Stage 2 へ ({e})")
        selected_urls = [a["url"] for a in articles]

    url_set = {normalize_url(u) for u in selected_urls if isinstance(u, str)}
    selected = [a for a in articles if normalize_url(a["url"]) in url_set]
    if not selected:
        print("[WARN]  summarize: Stage 1 の選定結果が0件 → 全件を Stage 2 へ")
        selected = articles
    if len(selected) > select_n:
        # Gemini が上限指示を無視した場合の保険（Stage 2 応答の途中切れを防ぐ）
        print(f"[WARN]  summarize: Stage 1 が上限{select_n}件を超過（{len(selected)}件） → {select_n}件に切り詰め")
        selected = selected[:select_n]
    print(f"[INFO]  summarize: Stage 1 完了 → {len(selected)}件選定")

    # ── Stage 2: 選定記事を翻訳・要約 ────────────────────────────────
    print(f"[INFO]  summarize: Stage 2 翻訳・要約（{len(selected)}件）")
    result = _call_gemini_json(client, build_prompt(selected, config["gemini_prompt"]), types, response_schema=article_schema)

    # Geminiが改行を過剰エスケープし、JSON文字列内に本物の改行ではなく
    # リテラルな "\n"（バックスラッシュ+n の2文字）を返すことがあるため補正する
    for r in result:
        for field in ("title_ja", "summary_ja", "translation_ja"):
            if isinstance(r.get(field), str):
                r[field] = r[field].replace("\\n", "\n")
        if isinstance(r.get("key_points"), list):
            r["key_points"] = [
                kp.replace("\\n", "\n") if isinstance(kp, str) else kp
                for kp in r["key_points"]
            ]

    # カテゴリ正規化（Geminiが英語や日本語バリエーションを返す場合に備える）
    raw_cats = [r.get("category") for r in result]
    print(f"[INFO]  summarize: Gemini返却カテゴリ（正規化前）: {raw_cats}")
    for r in result:
        r["category"] = normalize_category(r.get("category"))

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

    # FR-06：無効カテゴリ（genres=false）を除外してから重要度上位を選定する
    result_sorted = select_articles(result, slot_genres, slot_max)

    # プロンプト指示（該当ジャンルのみ・絞りすぎない）だけでは目標件数に届かないことがあるため、
    # 未使用の収集記事が残っていれば不足分だけ追加で選定・翻訳して1回だけ補充する
    if len(result_sorted) < slot_max:
        tried_urls = {normalize_url(a["url"]) for a in selected}
        remaining = [a for a in articles if normalize_url(a["url"]) not in tried_urls]
        shortfall = slot_max - len(result_sorted)
        if remaining:
            backfill_n = min(SELECT_MAX, shortfall + 5, len(remaining))
            print(f"[INFO]  summarize: 件数不足（あと{shortfall}件）→ 残り{len(remaining)}件から{backfill_n}件を追加選定")
            backfill_sel_text = _call_gemini(client, build_selection_prompt(remaining, n=backfill_n, genres=slot_genres), types)
            try:
                backfill_urls: list[str] = json.loads(backfill_sel_text)
                if not isinstance(backfill_urls, list):
                    raise ValueError("not a list")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[WARN]  summarize: 追加選定のパース失敗 → 補充をスキップ ({e})")
                backfill_urls = []

            backfill_url_set = {normalize_url(u) for u in backfill_urls if isinstance(u, str)}
            backfill_selected = [a for a in remaining if normalize_url(a["url"]) in backfill_url_set][:backfill_n]

            if backfill_selected:
                print(f"[INFO]  summarize: 追加選定 → {len(backfill_selected)}件を翻訳・要約")
                backfill_result = _call_gemini_json(
                    client, build_prompt(backfill_selected, config["gemini_prompt"]), types, response_schema=article_schema
                )
                for r in backfill_result:
                    for field in ("title_ja", "summary_ja", "translation_ja"):
                        if isinstance(r.get(field), str):
                            r[field] = r[field].replace("\\n", "\n")
                    if isinstance(r.get("key_points"), list):
                        r["key_points"] = [
                            kp.replace("\\n", "\n") if isinstance(kp, str) else kp
                            for kp in r["key_points"]
                        ]
                    r["category"] = normalize_category(r.get("category"))
                    key = normalize_url(r.get("url", ""))
                    if key and key not in seen_urls:
                        seen_urls.add(key)
                        result.append(r)

                result_sorted = select_articles(result, slot_genres, slot_max)
                print(f"[INFO]  summarize: 補充後 → {len(result_sorted)}件選出")

    if not result_sorted:
        print("[ERROR] summarize: 有効カテゴリの記事が0件（genres設定を確認）")
        sys.exit(1)

    if len(result_sorted) < slot_max:
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
    print(f"[INFO]  summarize: 完了 → {len(result_sorted)}件選出 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
