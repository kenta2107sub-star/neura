"""FR-01：AIニュース収集。

config の sources（有効なもの）・keywords に従い、全ソースから並列で記事を収集し、
AIキーワードフィルタ・重複排除・スコア/日付別ランキング・本文テキスト取得を行い、
``/tmp/neura_collected.json`` に書き出す。
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
import feedparser
import trafilatura

from config_loader import load_config
from schemas import CollectedArticle, Keywords, Source

OUTPUT_PATH = "/tmp/neura_collected.json"
STATUS_PATH = "/tmp/neura_collect_status.json"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)  # NF-01：各リクエスト10秒
USER_AGENT = "Mozilla/5.0 (compatible; Neura/1.0; +https://github.com/yourname/neura)"
BODY_MAX_CHARS = 5000
FEED_MAX_BYTES = 1 * 1024 * 1024
ARTICLE_MAX_BYTES = 2 * 1024 * 1024
BODY_FETCH_CONCURRENCY = 5
MAX_REDIRECTS = 3


class UnsafeUrlError(ValueError):
    """外部から受け取ったURLが公開インターネットへ安全に接続できない。"""


class ResponseTooLargeError(ValueError):
    """レスポンスが収集時の上限を超えた。"""


def validate_public_url(raw_url: str, allowed_schemes: tuple[str, ...]) -> str:
    """スキーム・認証情報・ホストを検証し、接続可能なURL文字列を返す。"""
    if not isinstance(raw_url, str):
        raise UnsafeUrlError("URL is not a string")
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port  # 不正なポート表記をここで検出する
    except ValueError as exc:
        raise UnsafeUrlError("URL is malformed") from exc
    if parsed.scheme not in allowed_schemes or not parsed.hostname:
        raise UnsafeUrlError("URL scheme or host is not allowed")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL credentials are not allowed")
    if port is not None and not 1 <= port <= 65535:
        raise UnsafeUrlError("URL port is not allowed")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        if not _is_public_ip(parsed.hostname):
            raise UnsafeUrlError("URL address is not public")
    return parsed.geturl()


def _is_public_ip(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def is_allowed_article_url(raw_url: str) -> bool:
    """記事として保持できるHTTP(S) URLかを、DNS解決前の境界で判定する。"""
    try:
        parsed = urlsplit(validate_public_url(raw_url, ("http", "https")))
        host = parsed.hostname
        if not host:
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return _is_public_ip(host)
    except UnsafeUrlError:
        return False


class PublicInternetResolver(AbstractResolver):
    """DNSの解決結果を検査し、その結果だけをaiohttpへ渡して再解決を防ぐ。"""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            host,
            port,
            family=family,
            type=socket.SOCK_STREAM,
        )
        resolved = []
        for record_family, socktype, proto, _canonname, sockaddr in records:
            address = sockaddr[0]
            if not _is_public_ip(address):
                raise UnsafeUrlError(f"non-public address: {address}")
            resolved.append({
                "hostname": host,
                "host": address,
                "port": port,
                "family": record_family,
                "proto": proto,
                "flags": 0,
            })
        if not resolved:
            raise UnsafeUrlError("host did not resolve to a public address")
        return resolved

    async def close(self) -> None:
        return None


async def read_limited(response: aiohttp.ClientResponse, max_bytes: int) -> bytes:
    content_length = response.content_length
    if content_length is not None and content_length > max_bytes:
        raise ResponseTooLargeError(f"response exceeds {max_bytes} bytes")

    data = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ResponseTooLargeError(f"response exceeds {max_bytes} bytes")
    return bytes(data)


async def fetch_public_bytes(
    session: aiohttp.ClientSession,
    raw_url: str,
    *,
    allowed_schemes: tuple[str, ...],
    max_bytes: int,
) -> bytes:
    """公開IPに固定した接続で、上限付きレスポンスを取得する。"""
    current_url = validate_public_url(raw_url, allowed_schemes)
    for redirect_count in range(MAX_REDIRECTS + 1):
        async with session.get(current_url, timeout=HTTP_TIMEOUT, allow_redirects=False) as response:
            if 300 <= response.status < 400 and response.headers.get("Location"):
                if redirect_count == MAX_REDIRECTS:
                    raise UnsafeUrlError("too many redirects")
                current_url = validate_public_url(
                    urljoin(current_url, response.headers["Location"]),
                    allowed_schemes,
                )
                continue
            response.raise_for_status()
            return await read_limited(response, max_bytes)
    raise UnsafeUrlError("redirect handling failed")


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
        ids = json.loads((await fetch_public_bytes(
            session, url, allowed_schemes=("https",), max_bytes=FEED_MAX_BYTES,
        )).decode("utf-8"))
        top_ids = ids[:100]

        async def fetch_item(item_id: int) -> CollectedArticle | None:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            try:
                item = json.loads((await fetch_public_bytes(
                    session, item_url, allowed_schemes=("https",), max_bytes=FEED_MAX_BYTES,
                )).decode("utf-8"))
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
        raw = await fetch_public_bytes(
            session, url, allowed_schemes=("https",), max_bytes=FEED_MAX_BYTES,
        )
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
        raw = await fetch_public_bytes(
            session, url, allowed_schemes=("https",), max_bytes=FEED_MAX_BYTES,
        )
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


async def fetch_body_text(session: aiohttp.ClientSession, url: str) -> str | None:
    """公開URLから本文を上限付きで取得し、trafilaturaで抽出する。"""
    try:
        html = await fetch_public_bytes(
            session, url, allowed_schemes=("http", "https"), max_bytes=ARTICLE_MAX_BYTES,
        )
        body = await asyncio.to_thread(
            trafilatura.extract,
            html,
            include_comments=False,
            include_tables=False,
        )
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
    """フィルタ・重複排除・ソートを行い上位20件（スコア系14件・日付系6件）を返す。"""
    # 1. URLバリデーション（NF-03）
    articles = [a for a in articles if is_allowed_article_url(a["url"])]

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

    # 5. スコア系最大14件・日付系最大6件を結合（計最大20件）
    return score_based[:14] + date_based[:6]


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

    connector = aiohttp.TCPConnector(
        resolver=PublicInternetResolver(),
        use_dns_cache=False,
    )
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, connector=connector) as session:
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

    # 各記事の本文取得は、公開IP検証済みの接続に固定して最大5件ずつ実行する。
    semaphore = asyncio.Semaphore(BODY_FETCH_CONCURRENCY)

    body_connector = aiohttp.TCPConnector(
        resolver=PublicInternetResolver(),
        use_dns_cache=False,
    )
    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, connector=body_connector) as body_session:
        async def fetch_limited(article: CollectedArticle) -> str | None:
            async with semaphore:
                return await fetch_body_text(body_session, article["url"])

        bodies = await asyncio.gather(*[fetch_limited(a) for a in articles])
    for article, body in zip(articles, bodies):
        article["body_text"] = body
    got = sum(1 for a in articles if a["body_text"])
    print(f"[INFO]  collect: 本文取得 → {got}/{len(articles)}件成功")

    save_json(OUTPUT_PATH, articles)
    print(f"[INFO]  collect: {OUTPUT_PATH} 書き出し完了")


if __name__ == "__main__":
    asyncio.run(main())
