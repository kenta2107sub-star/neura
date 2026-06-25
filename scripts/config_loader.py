"""FR-06：config/config.json を読み込む。

ファイル不在・JSONパース失敗時はデフォルト値を返す（クラッシュさせない）。
collect.py・summarize.py から ``load_config()`` を呼び出して使用する。
"""

from __future__ import annotations

import json
import os

from schemas import AppConfig

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")

# Gemini プロンプトのデフォルトテンプレート（{articles} を含む）。
# config.json の gemini_prompt と同一内容を保つこと。
DEFAULT_GEMINI_PROMPT = (
    "以下のAI関連記事から、最も重要・興味深い5〜10件を選び、\n"
    "各記事について以下の形式でJSON配列を返してください。\n"
    "海外・日本語の両ソースからバランスよく選んでください。\n\n"
    "各記事のJSONフィールド：\n"
    "- url: 元記事のURLをそのまま返す（変更禁止）\n"
    "- title_ja: 日本語タイトル（30文字以内。元が日本語の場合はそのまま使用）\n"
    "- summary_ja: 日本語要約（150文字以内）\n"
    "- translation_ja: 以下のルールで生成する（markdown形式）\n"
    "    - 元記事が日本語の場合：本文をそのままmarkdown形式で返す（翻訳・要約不要）\n"
    "    - 元記事が英語またはその他の言語の場合：日本語に翻訳したうえで、要点を残しながら2000字以内にまとめる（記事の論旨・重要な数値・結論を必ず含める）\n"
    "    - コードブロックは ```言語名 で囲んでそのまま保持（翻訳しない）\n"
    "    - インラインコード（関数名・変数名・ライブラリ名）は `backtick` で囲んでそのまま保持\n"
    "    - 見出しは ## / ### で構造を維持する\n"
    "    - 箇条書きは - で保持する\n"
    "    - 重要ワードは **太字** で保持する\n"
    "    - URLリンクは除去してプレーンテキストにする\n"
    "    - 本文が「（本文取得不可）」の場合は null を返す\n"
    '- category: "ニュース" | "研究" | "活用事例" | "ツール" のいずれか\n'
    "- importance: 1〜5の整数（5が最重要。AI業界への影響度・新規性・実用性で判断）\n\n"
    "記事一覧:\n"
    "{articles}\n\n"
    "JSON配列のみを返してください。説明文・マークダウンの囲み・前後の文章は不要です。"
)

DEFAULT_CONFIG: AppConfig = {
    "genres": {"ニュース": True, "研究": True, "活用事例": True, "ツール": True},
    "sources": [
        {"name": "Hacker News", "url": "https://hacker-news.firebaseio.com/v0/topstories.json", "type": "hackernews", "enabled": True},
        {"name": "Reddit r/artificial", "url": "https://www.reddit.com/r/artificial/top/.rss?t=day", "type": "reddit", "enabled": True},
        {"name": "Reddit r/MachineLearning", "url": "https://www.reddit.com/r/MachineLearning/top/.rss?t=day", "type": "reddit", "enabled": True},
        {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "type": "rss", "enabled": True},
        {"name": "MIT Technology Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "type": "rss", "enabled": True},
        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "type": "rss", "enabled": True},
        {"name": "Zenn AI", "url": "https://zenn.dev/topics/ai/feed", "type": "zenn", "enabled": True},
        {"name": "Qiita AI", "url": "https://qiita.com/tags/ai/feed", "type": "zenn", "enabled": True},
        {"name": "ITmedia AI+", "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "type": "rss", "enabled": True},
        {"name": "はてなブックマーク IT", "url": "https://b.hatena.ne.jp/hotentry/it.rss", "type": "hatena", "enabled": True},
    ],
    "keywords": {
        "en": ["ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic", "machine learning", "deep learning", "neural", "chatbot", "agent", "generative"],
        "ja": ["AI", "LLM", "GPT", "Claude", "Gemini", "OpenAI", "Anthropic", "機械学習", "生成AI", "チャットボット", "エージェント"],
    },
    "gemini_prompt": DEFAULT_GEMINI_PROMPT,
    "notify_schedules": [
        {"hour": 13, "enabled": True},
        {"hour": 20, "enabled": False},
        {"hour":  8, "enabled": False},
    ],
    "max_articles": 10,
}


def load_config(path: str = CONFIG_PATH) -> AppConfig:
    """config/config.json を読み込んで AppConfig を返す。

    ファイル不在・JSONパース失敗時は DEFAULT_CONFIG を返す。
    必須キーが欠けている場合はデフォルト値で補完する（トップレベルの浅いマージ）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN]  config: config.json not found/invalid, using defaults ({e})")
        return DEFAULT_CONFIG

    # 旧フィールド run_hour_jst → notify_schedules へのマイグレーション
    if "run_hour_jst" in cfg and "notify_schedules" not in cfg:
        h = cfg.pop("run_hour_jst")
        cfg["notify_schedules"] = [
            {"hour": h, "enabled": True},
            {"hour": 20, "enabled": False},
            {"hour":  8, "enabled": False},
        ]

    # トップレベルキーの欠落をデフォルトで補完する
    merged: AppConfig = {**DEFAULT_CONFIG, **cfg}  # type: ignore[typeddict-item]
    return merged
