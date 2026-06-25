"""FR-01：AIニュース収集。

config の sources（有効なもの）・keywords に従い、全ソースから並列で記事を収集し、
AIキーワードフィルタ・重複排除・スコア/日付別ランキング・本文テキスト取得を行い、
``/tmp/neura_collected.json`` に書き出す。
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone

import aiohttp
import feedparser
import trafilatura

from config_loader import load_config
from schemas import CollectedArticle, Keywords, Source

OUTPUT_PATH = "/tmp/neura_collected.json"
STATUS_PATH = "/tmp/neura_collect_status.json"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)  # NF-01：各リクエスト10秒
USER_AGENT = "Mozilla/5.0 (compatible; Neura/1.0; +https://github.com/yourname/neura)"
BODY_MAX_CHARS = 5000


# ── ユーティリティ ──────────────────────────────────────────────


def _unix_to_iso(unix_ts: float) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _struct_to_iso(struct_time) -> str:
    """feedparser の published_parsed (time.struct_time) を ISO 8601 UTC に変換する。"""
    try:
        from calendar import timegm

        return _unix_to_iso(timegm(struct_time))
    except Exception:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 各ソース取得関数 ────────────────────────────────────────────
# 全関数は失敗時に [] を返し、[WARN] をログ出力する（処理を止めない）。


async def fetch_hackernews(session: aiohttp.ClientSession, url: str) -> list[CollectedArticle]:
    name = "HackerNews"
    try:
        async with session.get(url, timeout=HTTP_TIMEOUT) as resp:
            ids = await resp.json()
        top_ids = ids[:100]

        async def fetch_item(item_id: int) -> CollectedArticle | None:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            try:
                async with session.get(item_url, timeout=HTTP_TIMEOUT) as r:
                    item = await r.json()
                if not item or not item.get("url"):
                    return None  # Ask HN 等（url なし）はスキップ
                return {
                    "title": item.get("title", ""),
                    "url": item["url"],
                    "source": "HackerNews",
                    "score": int(item.get("score", 0)),
                    "published_at": _unix_to_iso(item.get("time", 0)),
                    "body_text": None,
                }
            except Exception:
                return None

        items = await asyncio.gather(*[fetch_item(i) for i in top_ids])
        articles = [a for a in items if a is not None]
        print(f"[INFO]  collect: {name} → {len(articles)}件取得")
        return articles
    except asyncio.TimeoutError:
        print(f"[WARN]  collect: {name} timeout（スキップ）")
        return []
    except Exception as e:
        print(f"[WARN]  collect: {name} 取得失敗 {e}（スキップ）")
        return []


async def fetch_rss(session: aiohttp.ClientSession, url: str, source: str) -> list[CollectedArticle]:
    # source: "Reddit" | "RSS" | "Zenn"（Reddit/RSS は EN フィルタ、Zenn はフィルタ不要）
    try:
        # feedparser は同期処理のため、HTTP取得のみ aiohttp で行いパースをスレッドに逃がす
        async with session.get(url, timeout=HTTP_TIMEOUT) as resp:
            raw = await resp.read()
        parsed = await asyncio.to_thread(feedparser.parse, raw)
        articles: list[CollectedArticle] = []
        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            published_at = _struct_to_iso(published) if published else datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            articles.append(
                {
                    "title": entry.get("title", ""),
                    "url": link,
                    "source": source,
                    "score": 0,
                    "published_at": published_at,
                    "body_text": None,
                }
            )
        print(f"[INFO]  collect: {source}({url}) → {len(articles)}件取得")
        return articles
    except asyncio.TimeoutError:
        print(f"[WARN]  collect: {source}({url}) timeout（スキップ）")
        return []
    except Exception as e:
        print(f"[WARN]  collect: {source}({url}) 取得失敗 {e}（スキップ）")
        return []


async def fetch_hatena(session: aiohttp.ClientSession, url: str) -> list[CollectedArticle]:
    # はてブは hotentry RSS（RDF）を feedparser で解析する。
    # 各エントリの hatena_bookmarkcount をスコアとして使い、20以上のみ採用する。
    name = "HatenaBookmark"
    try:
        async with session.get(url, timeout=HTTP_TIMEOUT) as resp:
            raw = await resp.read()
        parsed = await asyncio.to_thread(feedparser.parse, raw)
        articles: list[CollectedArticle] = []
        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue
            try:
                count = int(entry.get("hatena_bookmarkcount") or 0)
            except (ValueError, TypeError):
                count = 0
            if count < 20:  # 低品質記事を除外
                continue
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            published_at = _struct_to_iso(published) if published else datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            articles.append(
                {
                    "title": entry.get("title", ""),
                    "url": link,
                    "source": "HatenaBookmark",
                    "score": count,
                    "published_at": published_at,
                    "body_text": None,
                }
            )
        print(f"[INFO]  collect: {name} → {len(articles)}件取得")
        return articles
    except asyncio.TimeoutError:
        print(f"[WARN]  collect: {name} timeout（スキップ）")
        return []
    except Exception as e:
        print(f"[WARN]  collect: {name} 取得失敗 {e}（スキップ）")
        return []


def fetch_body_text(url: str) -> str | None:
    """trafilatura で本文テキストを抽出する。失敗時は None。"""
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return None
        body = trafilatura.extract(html, include_comments=False, include_tables=False)
        if not body:
            return None
        return body[:BODY_MAX_CHARS]
    except Exception:
        return None


# ── フィルタ・ランキング ───────────────────────────────────────


def matches_ai_keyword(title: str, source: str, keywords: Keywords) -> bool:
    if source == "Zenn":
        return True  # Zenn は ai タグフィードのためフィルタ不要
    kw_list = keywords["ja"] if source == "HatenaBookmark" else keywords["en"]
    lower = title.lower()
    return any(kw.lower() in lower for kw in kw_list)


def filter_and_rank(articles: list[CollectedArticle], keywords: Keywords) -> list[CollectedArticle]:
    """フィルタ・重複排除・ソートを行い上位30件（スコア系20件・日付系10件）を返す。"""
    # 1. URLバリデーション（NF-03）
    articles = [a for a in articles if a["url"].startswith(("http://", "https://"))]

    # 2. AIキーワードフィルタ
    articles = [a for a in articles if matches_ai_keyword(a["title"], a["source"], keywords)]

    # 3. URL重複排除（正規化後に先着1件のみ残す）
    seen: set[str] = set()
    unique: list[CollectedArticle] = []
    for a in articles:
        key = a["url"].rstrip("/").split("?")[0]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # 4. ソース別に分離してソート
    #    スコアを持つ HackerNews / HatenaBookmark はスコア降順、
    #    RSS化した Reddit や RSS/Zenn は公開日時降順で並べる（score=0 が沈まないよう分離）。
    score_based = sorted(
        [a for a in unique if a["source"] in ("HackerNews", "HatenaBookmark")],
        key=lambda a: a["score"],
        reverse=True,
    )
    date_based = sorted(
        [a for a in unique if a["source"] in ("Reddit", "RSS", "Zenn")],
        key=lambda a: a["published_at"],
        reverse=True,
    )

    # 5. スコア系最大20件・日付系最大10件を結合（計最大30件）
    return score_based[:20] + date_based[:10]


# ── ディスパッチ・メイン ──────────────────────────────────────


def build_tasks(session: aiohttp.ClientSession, sources: list[Source]) -> list[tuple[str, object]]:
    """(source.name, coroutine) ペアのリストを返す。ステータス記録にsource.nameを使う。"""
    tasks = []
    for s in sources:
        if not s.get("enabled"):
            continue
        name = s["name"]
        t = s["type"]
        if t == "hackernews":
            tasks.append((name, fetch_hackernews(session, s["url"])))
        elif t == "reddit":
            tasks.append((name, fetch_rss(session, s["url"], "Reddit")))
        elif t == "rss":
            tasks.append((name, fetch_rss(session, s["url"], "RSS")))
        elif t == "zenn":
            tasks.append((name, fetch_rss(session, s["url"], "Zenn")))
        elif t == "hatena":
            tasks.append((name, fetch_hatena(session, s["url"])))
        else:
            print(f"[WARN]  collect: 未知のtype {t}（スキップ）")
    return tasks


def flatten(results) -> list[CollectedArticle]:
    """リストのみ展開する（Exception オブジェクトはスキップ）。"""
    out: list[CollectedArticle] = []
    for r in results:
        if isinstance(r, list):
            out.extend(r)
    return out


async def main() -> None:
    config = load_config()  # FR-06：設定読込（不在時デフォルト）

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        named_tasks = build_tasks(session, config["sources"])
        names = [n for n, _ in named_tasks]
        coros = [c for _, c in named_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

    # ソース別ステータスを記録（成功＝list返却、失敗＝Exception or空list）
    source_status: dict = {}
    for name, result in zip(names, results):
        if isinstance(result, list) and result:
            source_status[name] = {"status": "ok", "count": len(result)}
        elif isinstance(result, list):
            source_status[name] = {"status": "failed", "count": 0}
        else:
            source_status[name] = {"status": "failed", "count": 0}
    save_json(STATUS_PATH, {
        "run_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": source_status,
    })
    print(f"[INFO]  collect: collect_status.json 書き出し完了")

    articles = filter_and_rank(flatten(results), config["keywords"])

    if not articles:
        print("[ERROR] All sources failed")  # ERR-04
        sys.exit(1)

    print(f"[INFO]  collect: フィルタ・ランキング後 → {len(articles)}件")

    # 各記事の本文取得（trafilatura は同期のためスレッドで並列化）
    bodies = await asyncio.gather(*[asyncio.to_thread(fetch_body_text, a["url"]) for a in articles])
    for article, body in zip(articles, bodies):
        article["body_text"] = body
    got = sum(1 for a in articles if a["body_text"])
    print(f"[INFO]  collect: 本文取得 → {got}/{len(articles)}件成功")

    save_json(OUTPUT_PATH, articles)
    print(f"[INFO]  collect: {OUTPUT_PATH} 書き出し完了")


if __name__ == "__main__":
    asyncio.run(main())
