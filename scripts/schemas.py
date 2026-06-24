"""共通型定義（TypedDict）。

ファイル名を ``types.py`` にすると Python 標準ライブラリの ``types`` モジュールを
``sys.path[0]`` でシャドーイングし、依存ライブラリ内部の ``import types`` を壊すため
``schemas.py`` とする（neura_architecture.md 参照）。
"""

from __future__ import annotations

from typing import Optional, TypedDict


class Source(TypedDict):
    """収集ソース定義（config.json の sources 要素）。"""

    name: str
    url: str
    type: str  # "hackernews" | "reddit" | "rss" | "zenn" | "hatena"
    enabled: bool


class Keywords(TypedDict):
    """AIキーワードフィルタ定義（config.json の keywords）。"""

    en: list[str]
    ja: list[str]


class AppConfig(TypedDict):
    """収集設定（config/config.json 全体）。"""

    genres: dict[str, bool]  # {"ニュース": True, "研究": True, ...}
    sources: list[Source]
    keywords: Keywords
    gemini_prompt: str  # {articles} プレースホルダーを含む
    run_hour_jst: int  # GitHub Actions の実行時刻（JST 0〜23）


class CollectedArticle(TypedDict):
    """collect.py が出力する収集済み記事。"""

    title: str
    url: str
    source: str  # "HackerNews" | "Reddit" | "RSS" | "Zenn" | "HatenaBookmark"
    score: int
    published_at: str  # ISO 8601 UTC
    body_text: Optional[str]


class Article(TypedDict):
    """summarize.py が出力する最終記事オブジェクト。"""

    title_ja: str
    summary_ja: str
    translation_ja: Optional[str]
    category: str  # "ニュース" | "研究" | "活用事例" | "ツール"
    importance: int  # 1〜5
    url: str
    source: str
    published_at: str


class DailyDigest(TypedDict):
    """日次データ（docs/data/{YYYY-MM-DD}.json）。"""

    date: str  # YYYY-MM-DD
    generated_at: str  # ISO 8601 UTC
    articles: list[Article]


class DigestMeta(TypedDict):
    """日付ごとのメタ情報（index.json の digests 要素）。"""

    date: str  # YYYY-MM-DD
    count: int  # その日の記事件数
    categories: dict[str, int]  # カテゴリ別件数（存在するカテゴリのみ）


class DigestIndex(TypedDict):
    """日付インデックス（docs/data/index.json）。"""

    digests: list[DigestMeta]  # 降順・最大100件
