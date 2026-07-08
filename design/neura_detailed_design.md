# 詳細設計書

> **プロジェクト名**：Neura
> **対象フェーズ**：Phase 1（MVP）本実装用
> **このドキュメントの用途**：Claude Codeが本実装（Pythonスクリプト・GitHub Actions・フロントエンド）を行うための仕様書。
> **逆算元のファイル**：
> - `neura_basic_design.md`（データモデル・画面仕様・エラー定義）
> - `neura_requirements.md`（FR一覧・NF・エラー定義）
> - `docs/index.html`（モックコード・コンポーネント構造・ダミーデータ形状）
> **関連ドキュメント**：
> - `neura_architecture.md`（技術スタック・ディレクトリ構成・環境変数）
> **次のステップ**：このドキュメントと `neura_architecture.md` を渡して本実装を開始する

---

## 1. JSONファイルスキーマ（データ永続化層）

本プロジェクトはDBを使用せず、JSONファイルをGitリポジトリに保存する。

### 1-1. `docs/data/index.json`（日付インデックス）

ホーム画面（SCR-01）が**1回のfetchで日付一覧・記事件数・カテゴリ分布バー**を描画できるよう、各実行スロットのメタ情報を保持する。1日複数回通知設定の場合、同日に複数エントリが存在する。

```json
{
  "digests": [
    {
      "date": "2026-06-18",
      "time": "18:00",
      "file": "2026-06-18_18",
      "count": 7,
      "categories": { "ニュース": 3, "研究": 1, "活用事例": 1, "ツール": 2 },
      "titles": [{"t": "記事タイトル", "c": "ニュース"}]
    },
    {
      "date": "2026-06-18",
      "time": "08:00",
      "file": "2026-06-18_08",
      "count": 5,
      "categories": { "ニュース": 2, "ツール": 3 },
      "titles": []
    }
  ]
}
```

| フィールド | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `digests` | `DigestMeta[]` | ✅ | 降順ソート・最大100件 | 各実行スロットのメタ情報一覧 |
| `digests[].date` | `string` | ✅ | YYYY-MM-DD（JST） | 対象日付 |
| `digests[].time` | `string` | ✅ | HH:00（JST） | 実行時刻 |
| `digests[].file` | `string` | ✅ | `YYYY-MM-DD_HH` | 日次JSONのファイル名（拡張子なし）。フェッチ先は `docs/data/${file}.json` |
| `digests[].count` | `number` | ✅ | 0以上 | 記事件数 |
| `digests[].categories` | `dict[str,int]` | ✅ | 存在するカテゴリのみ | カテゴリ別件数 |
| `digests[].titles` | `{t:string,c:string}[]` | ✅ | 最大10件 | ホームに表示する記事タイトル一覧 |

- `archive.py` が各実行後に更新する。同一 `(date, time)` キーは上書き、異なるキーは追記。
- 100件を超えた場合は末尾（最古）から削除する
- `docs/index.html` が起動時にfetchする
- 検索（SCR-03）は `digests[].file` を列挙して各日次JSONを並列取得する
- **後方互換**：`file` フィールドがない旧エントリは `date` フィールドをファイル名として使用する

---

### 1-2. `docs/data/YYYY-MM-DD.json`（日次記事データ）

```json
{
  "date": "2026-06-18",
  "generated_at": "2026-06-18T04:00:00Z",
  "articles": [
    {
      "title_ja": "OpenAI、GPT-5を正式リリース",
      "summary_ja": "OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...",
      "key_points": ["推論能力が大幅に向上", "コンテキスト長が200万トークンに拡大", "SWE-benchで85%を達成"],
      "translation_ja": "## OpenAI、GPT-5を正式リリース\n\nOpenAIは本日...\n\n```python\nclient.chat...\n```",
      "category": "ニュース",
      "importance": 5,
      "url": "https://example.com/article",
      "source": "HackerNews",
      "published_at": "2026-06-18T03:00:00Z"
    }
  ]
}
```

#### DailyDigest（ファイル全体）

| フィールド | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `date` | `string` | ✅ | YYYY-MM-DD形式 | 対象日付 |
| `generated_at` | `string` | ✅ | ISO 8601 UTC | GitHub Actionsの実行日時 |
| `articles` | `Article[]` | ✅ | スロット設定による（1〜10件） | 記事オブジェクトの配列（重要度降順） |

#### Article（記事オブジェクト）

| フィールド | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `title_ja` | `string` | ✅ | 30文字以内 | 日本語タイトル（英語記事は翻訳済み） |
| `summary_ja` | `string` | ✅ | 150文字以内 | 日本語要約 |
| `key_points` | `string[]` | ✅ | 最大3件・各40文字以内 | 伝えたいこと。内容が薄い場合は1〜2件、本文取得不可時は空配列 |
| `translation_ja` | `string \| null` | ✅ | markdown形式 | 全文日本語翻訳。本文取得失敗時は `null` |
| `category` | `string` | ✅ | 下記4値のいずれか | 記事カテゴリ |
| `importance` | `number` | ✅ | 1〜5の整数 | 重要度スコア（5が最重要） |
| `url` | `string` | ✅ | `https://` or `http://` で始まる | 元記事URL |
| `source` | `string` | ✅ | 下記5値のいずれか | 情報ソース名 |
| `published_at` | `string` | ✅ | ISO 8601 UTC | 元記事の公開日時 |

**`category` の許容値**：`"ニュース"` / `"研究"` / `"活用事例"` / `"ツール"`

**`source` の許容値**：`"HackerNews"` / `"Reddit"` / `"RSS"` / `"Zenn"` / `"HatenaBookmark"`

**`translation_ja` の形式**：
- コードブロックは ` ```言語名 ` で囲む（翻訳しない）
- インラインコードは `` `backtick` `` で囲む（翻訳しない）
- 見出しは `##` / `###` で構造を維持する
- 箇条書きは `-` で保持する
- 重要ワードは `**太字**` で保持する
- URLリンクは除去してプレーンテキストにする

---

### 1-3. `config/config.json`（収集設定 / FR-06）

リポジトリにデフォルト値を同梱し、設定画面（SCR-04）が GitHub Contents API で更新する。`collect.py`・`summarize.py` が起動時に読み込む。

```json
{
  "sources": [
    { "name": "Hacker News", "url": "https://hacker-news.firebaseio.com/v0/topstories.json", "type": "hackernews", "enabled": true },
    { "name": "Reddit r/artificial", "url": "https://www.reddit.com/r/artificial/top/.rss?t=day", "type": "reddit", "enabled": true },
    { "name": "Reddit r/MachineLearning", "url": "https://www.reddit.com/r/MachineLearning/top/.rss?t=day", "type": "reddit", "enabled": true },
    { "name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "type": "rss", "enabled": true },
    { "name": "MIT Technology Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "type": "rss", "enabled": true },
    { "name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "type": "rss", "enabled": true },
    { "name": "Zenn AI", "url": "https://zenn.dev/topics/ai/feed", "type": "zenn", "enabled": true },
    { "name": "Qiita AI", "url": "https://qiita.com/tags/ai/feed", "type": "zenn", "enabled": true },
    { "name": "ITmedia AI+", "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", "type": "rss", "enabled": true },
    { "name": "はてなブックマーク IT", "url": "https://b.hatena.ne.jp/hotentry/it.rss", "type": "hatena", "enabled": true }
  ],
  "keywords": {
    "en": ["ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic", "machine learning", "deep learning", "neural", "chatbot", "agent", "generative"],
    "ja": ["AI", "LLM", "GPT", "Claude", "Gemini", "OpenAI", "Anthropic", "機械学習", "生成AI", "チャットボット", "エージェント"]
  },
  "gemini_prompt": "以下のAI関連記事から...\n\n記事一覧:\n{articles}",
  "notify_schedules": [
    { "hour": 13, "enabled": true,  "max_articles": 5, "genres": {"ニュース": false, "研究": false, "活用事例": true, "ツール": true} },
    { "hour": 19, "enabled": true,  "max_articles": 5, "genres": {"ニュース": true,  "研究": false, "活用事例": false, "ツール": false} },
    { "hour":  8, "enabled": false, "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true} }
  ]
}
```

> グローバルの `genres` / `max_articles` / `run_hour_jst` は廃止済み。旧形式が残っている場合は `config_loader.py` が自動マイグレーションしてスロット内に移行する（後述）。

#### AppConfig（ファイル全体）

| フィールド | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `sources` | `Source[]` | ✅ | 1件以上 | 収集ソース定義 |
| `keywords.en` | `string[]` | ✅ | — | 海外ソース用フィルタキーワード |
| `keywords.ja` | `string[]` | ✅ | — | はてブ用フィルタキーワード |
| `gemini_prompt` | `string` | ✅ | `{articles}` を含む | Geminiプロンプトのテンプレート |
| `notify_schedules` | `NotifySchedule[]` | ✅ | 最大3件 | 通知スケジュール（1日最大3スロット） |
| `notify_schedules[].hour` | `int` | ✅ | 0〜23（JST） | スロットの実行時刻。enabled:true のスロットが cron-job.org のジョブ時刻に対応 |
| `notify_schedules[].enabled` | `bool` | ✅ | — | スロット有効/無効。少なくとも1件は true が必要 |
| `notify_schedules[].max_articles` | `int` | ✅ | 1〜10 | そのスロットで選出する記事の上限件数 |
| `notify_schedules[].genres` | `dict[str, bool]` | ✅ | キーは4カテゴリ名 | そのスロットで通知するカテゴリON/OFF |

#### Source（ソース定義）

| フィールド | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `name` | `string` | ✅ | — | 表示名 |
| `url` | `string` | ✅ | — | 収集元URL |
| `type` | `string` | ✅ | 下記5値 | パーサ振分けキー |
| `enabled` | `boolean` | ✅ | — | `false` のソースは収集対象外 |

**`type` の許容値**：`"hackernews"` / `"reddit"` / `"rss"` / `"zenn"` / `"hatena"`
- `"rss"` と `"zenn"` はどちらも feedparser でパースする。違いは `"zenn"` がAIキーワードフィルタをスキップし `source="Zenn"` を付与する点
- 設定画面からユーザーが追加できるのは `"rss"` のみ

**フォールバック**：`config/config.json` が存在しない、またはパース失敗時は `config_loader.py` が上記デフォルト値を返す。

---

### 1-4. `docs/data/collect_status.json`（ソース別収集ステータス）

`collect.py` が実行後にソース別の収集結果を `/tmp/neura_collect_status.json` に書き出し、`archive.py` がそれを `docs/data/collect_status.json` にコピーしてgitコミットに含める。設定画面（SCR-04）がGitHub Contents API経由でこのファイルを読み、各ソース行に「取得失敗」バッジを表示する（`fetchSourceStatus()` 参照）。

```json
{
  "run_at": "2026-06-25T04:05:00Z",
  "sources": {
    "Hacker News":         { "status": "ok",     "count": 30 },
    "Reddit r/artificial": { "status": "ok",     "count": 18 },
    "ITmedia AI+":         { "status": "failed", "count": 0  }
  }
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `run_at` | `string` | 実行日時（ISO 8601 UTC） |
| `sources` | `dict[str, SourceStatus]` | キーは `config.json sources[].name` と一致させる |
| `sources[name].status` | `"ok" \| "failed"` | `"ok"`：1件以上取得成功、`"failed"`：例外・タイムアウトで取得ゼロ |
| `sources[name].count` | `number` | フィルタ前の取得件数（`"failed"` 時は 0） |

> **注意**：`collect.py` が全ソース失敗（exit(1)）した場合は `archive.py` が実行されないため `docs/data/collect_status.json` は前回実行時のまま更新されない。その場合は `fetchLastRunStatus()` が設定画面に `❌ 失敗` を表示するため、ユーザーはワークフロー全体失敗として認識できる。

---

## 2. Pythonスクリプト仕様

### 2-1. スクリプト間のデータ受け渡し方式

各スクリプトは `/tmp/neura_*.json` のtempファイルで結果を受け渡す。

```
collect.py  → /tmp/neura_collected.json     → summarize.py
collect.py  → /tmp/neura_collect_status.json → archive.py（docs/data/collect_status.json に書き出し）
summarize.py → /tmp/neura_summarized.json   → notify.py + archive.py
```

---

### 2-2. `scripts/config_loader.py`（FR-06）

#### 役割
`config/config.json` を読み込み `AppConfig` を返す。ファイル不在・JSONパース失敗時はデフォルト値を返す（クラッシュさせない）。`collect.py`・`summarize.py` から使用する。

```python
import json, os
from schemas import AppConfig  # ※ scripts/schemas.py（types.pyは標準ライブラリと衝突するため不可）

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")

DEFAULT_GENRES = {"ニュース": True, "研究": True, "活用事例": True, "ツール": True}
DEFAULT_MAX_ARTICLES = 10

DEFAULT_CONFIG: AppConfig = {
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
    "gemini_prompt": "（FR-02のデフォルトプロンプト全文。{articles} を含む）",
    "notify_schedules": [
        {"hour": 13, "enabled": True,  "max_articles": DEFAULT_MAX_ARTICLES, "genres": DEFAULT_GENRES},
        {"hour": 19, "enabled": False, "max_articles": DEFAULT_MAX_ARTICLES, "genres": DEFAULT_GENRES},
        {"hour":  8, "enabled": False, "max_articles": DEFAULT_MAX_ARTICLES, "genres": DEFAULT_GENRES},
    ],
}

def load_config() -> AppConfig:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARN]  config: config.json not found/invalid, using defaults ({e})")
        return DEFAULT_CONFIG

    # 旧フィールド run_hour_jst → notify_schedules へのマイグレーション
    if "run_hour_jst" in cfg and "notify_schedules" not in cfg:
        h = cfg.pop("run_hour_jst")
        cfg["notify_schedules"] = [
            {"hour": h, "enabled": True},
            {"hour": 19, "enabled": False},
            {"hour":  8, "enabled": False},
        ]

    # グローバル genres / max_articles → スロット内へのマイグレーション
    global_genres = cfg.pop("genres", DEFAULT_GENRES)
    global_max = int(cfg.pop("max_articles", DEFAULT_MAX_ARTICLES))
    for slot in cfg.get("notify_schedules", []):
        if "genres" not in slot:
            slot["genres"] = dict(global_genres)
        if "max_articles" not in slot:
            slot["max_articles"] = global_max

    # トップレベルキーの欠落をデフォルトで補完する（浅いマージ）
    return {**DEFAULT_CONFIG, **cfg}
```

> `gemini_prompt` に `{articles}` が含まれない場合の保険：summarize.py 側で `{articles}` 不在を検知したらデフォルトプロンプトにフォールバックする（`[WARN]` ログ）。プロンプトは config.json を直接編集する運用のため UI バリデーションは設けない。

---

### 2-3. `scripts/collect.py`（FR-01）

#### 役割
config の `sources`（有効なもの）・`keywords` に従い、全ソースから並列でAI記事を収集し、フィルタ・重複排除・本文取得を行い `/tmp/neura_collected.json` に保存する。

#### 処理フロー

```python
# 疑似コード（実装の設計意図を示す）
from config_loader import load_config

# typeごとのfetch関数ディスパッチ表
# 戻り値: list[tuple[str, Coroutine]] ← (source.name, coroutine) のペア
def build_tasks(session, sources: list[Source]) -> list[tuple[str, ...]]:
    tasks = []
    for s in sources:
        if not s["enabled"]:
            continue
        name = s["name"]   # config.json の sources[].name をキーとしてステータスに使う
        t = s["type"]
        if t == "hackernews":
            tasks.append((name, fetch_hackernews(session, s["url"])))
        elif t == "reddit":
            tasks.append((name, fetch_rss(session, s["url"], "Reddit")))
        elif t in ("rss", "zenn"):
            tasks.append((name, fetch_rss(session, s["url"], t.capitalize())))
        elif t == "hatena":
            tasks.append((name, fetch_hatena(session, s["url"])))
        else:
            print(f"[WARN]  collect: 未知のtype {t}（スキップ）")
    return tasks

async def main():
    # 0. 設定を読み込む（FR-06）。不在時はデフォルト値
    config = load_config()

    async with aiohttp.ClientSession(...) as session:
        named_tasks = build_tasks(session, config["sources"])
        names = [n for n, _ in named_tasks]
        coros = [c for _, c in named_tasks]

        # 1. 有効なソースのみ並列リクエスト（asyncio.gather）
        # return_exceptions=True で例外もリストとして返す（クラッシュしない）
        results = await asyncio.gather(*coros, return_exceptions=True)

    # 2. ソース別ステータスを記録して /tmp/neura_collect_status.json に書き出す
    source_status = {}
    for name, result in zip(names, results):
        if isinstance(result, list):
            source_status[name] = {"status": "ok", "count": len(result)}
        else:
            source_status[name] = {"status": "failed", "count": 0}
    save_json("/tmp/neura_collect_status.json", {
        "run_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": source_status,
    })

    # flatten: リストのみ展開する（Exception オブジェクトはスキップする）
    # 3. フラット化・AIキーワードフィルタ（config.keywords使用）・重複排除・ソース別ソート・上位20件
    articles = filter_and_rank(flatten(results), config["keywords"])

    # 4. 各記事URLから本文テキストを並列取得（asyncio.to_thread + asyncio.gather）
    bodies = await asyncio.gather(*[asyncio.to_thread(fetch_body_text, a["url"]) for a in articles])
    for article, body in zip(articles, bodies):
        article["body_text"] = body  # 失敗時はNone

    # 5. /tmp/neura_collected.json に書き出し
    save_json("/tmp/neura_collected.json", articles)
```

> **全ソースが無効（enabled全false）または該当ソースなしの場合**：`build_tasks` が空になり収集0件。`filter_and_rank` が空配列を返すため、`[ERROR] All sources failed` 相当として扱い exit(1) する（後続スクリプトを起動しない）。

#### 各ソース取得関数の仕様

**各 fetch_*() 関数の共通エラーハンドリングパターン**
```python
# 全ての fetch_*() 関数は以下のパターンに従う:
# try:
#     ... (HTTPリクエスト・パース処理)
#     return articles  # CollectedArticle のリスト
# except asyncio.TimeoutError:
#     print(f"[WARN]  collect: {source_name} timeout（スキップ）")
#     return []
# except Exception as e:
#     print(f"[WARN]  collect: {source_name} 取得失敗 {e}（スキップ）")
#     return []
```

> 各fetch関数の引数 `url` は config の `sources[].url` をそのまま受け取る。これにより収集元URLの変更を設定画面（FR-06）から行える。

**`fetch_hackernews(url: str)`**
```python
# 1. GET {url}（既定: https://hacker-news.firebaseio.com/v0/topstories.json）→ ID配列
# 2. 上位100件のIDに対して並列で GET https://hacker-news.firebaseio.com/v0/item/{id}.json
# 3. url が None（Ask HN等）はスキップ
# 出力フィールド: title, url, source="HackerNews", score=item.score, published_at=item.time(unix→ISO)
```

> Reddit は `.json` がBotブロックされるため RSS（`/top/.rss?t=day`）を `fetch_rss(url, "Reddit")` で取得する（専用 fetch_reddit は廃止）。セッションに browser 風 User-Agent を設定すること。RSSのためスコアは無く日付系ランキング扱い。

**`fetch_rss(feed_url: str, source: str)`**
```python
# HTTP取得は aiohttp、パースは feedparser.parse(bytes) を asyncio.to_thread で実行
# source は "Reddit" | "RSS" | "Zenn" を呼び出し側から渡す
# 出力フィールド: title=entry.title, url=entry.link, source=source, score=0, published_at=entry.published_parsed(→ISO)
# AIキーワードフィルタは source=="Zenn" のみスキップ（filter_and_rank 側で判定）
```

**`fetch_hatena(url: str)`**
```python
# はてブは hotentry RSS（RDF）を feedparser で解析する（.json は302で存在しない）
# GET {url}（既定: https://b.hatena.ne.jp/hotentry/it.rss）→ feedparser.parse(bytes)
# 各 entry: title=entry.title, url=entry.link,
#   score=int(entry.hatena_bookmarkcount or 0), published_at=entry.published_parsed(→ISO)
# フィルタ: hatena_bookmarkcount >= 20 のエントリのみ採用（fetch_hatena 内で適用）
#   ＋AIキーワード（日本語）は filter_and_rank 側で判定
# 出力フィールド: title, url, source="HatenaBookmark", score=bookmarkcount, published_at
```

**`fetch_body_text(url: str) -> str | None`**
```python
# trafilatura.fetch_url(url, timeout=10) → HTML文字列
# trafilatura.extract(html, include_comments=False, include_tables=False) → 本文テキスト
# 失敗（None返却・例外）: return None
# 成功: return body_text[:5000]  # 最大5000文字
```

#### `filter_and_rank` 関数の仕様

```python
def filter_and_rank(articles: list[CollectedArticle], keywords: dict) -> list[CollectedArticle]:
    """
    フィルタ・重複排除・ソートを行い、上位20件（スコア系14件・日付系6件）を返す。
    スコア系（HN/HatenaBookmark）とdate系（Reddit/RSS/Zenn）は別々にソートして結合する。
    RedditはRSS化でスコアを持たないため date系に含める。
    score=0 の記事が単純スコアソートで沈まないようにするため分離する。
    keywords は config の {"en": [...], "ja": [...]}。
    """
    # 1. URLバリデーション
    articles = [a for a in articles if a["url"].startswith(("http://", "https://"))]

    # 2. AIキーワードフィルタ（config.keywords使用）
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
    score_based = sorted(
        [a for a in unique if a["source"] in ("HackerNews", "HatenaBookmark")],
        key=lambda a: a["score"], reverse=True
    )
    date_based = sorted(
        [a for a in unique if a["source"] in ("Reddit", "RSS", "Zenn")],
        key=lambda a: a["published_at"], reverse=True
    )

    # 5. スコア系最大14件・日付系最大6件を結合（計最大20件）
    return score_based[:14] + date_based[:6]
```

#### AIキーワードフィルタ定義

キーワードは config（`config.keywords`）から取得する。デフォルト値は `config_loader.DEFAULT_CONFIG` および requirements.md FR-01 を参照。

```python
def matches_ai_keyword(title: str, source: str, keywords: dict) -> bool:
    # keywords = {"en": [...], "ja": [...]}（configから渡される）
    if source == "Zenn":
        return True  # Zennはaiタグフィードのためフィルタ不要
    kw_list = keywords["ja"] if source == "HatenaBookmark" else keywords["en"]
    return any(kw.lower() in title.lower() for kw in kw_list)
```

#### 出力ファイル形式（`/tmp/neura_collected.json`）

```json
[
  {
    "title": "OpenAI releases GPT-5",
    "url": "https://example.com/article",
    "source": "HackerNews",
    "score": 1523,
    "published_at": "2026-06-18T03:00:00Z",
    "body_text": "OpenAI today released GPT-5, its next-generation..."
  },
  {
    "title": "Zennで学ぶRAGの最新実装パターン",
    "url": "https://zenn.dev/example/rag",
    "source": "Zenn",
    "score": 0,
    "published_at": "2026-06-18T01:00:00Z",
    "body_text": null
  }
]
```

#### エラーハンドリング

| 状況 | 挙動 |
|---|---|
| 特定ソースがタイムアウト（10秒） | `[WARN] {source} timeout` をログ出力してそのソースをスキップ |
| 全ソースが失敗 | `[ERROR] All sources failed` をログ出力してexit(1)（後続スクリプトが起動しない） |
| 本文取得の失敗（個別URL） | `body_text: null` として続行（記事自体はスキップしない） |

---

### 2-4. `scripts/summarize.py`（FR-02）

#### 役割
`/tmp/neura_collected.json` を読み込み、Gemini Flash API を**2段階**で呼び出して要約・全文翻訳・カテゴリ・重要度を生成し、`/tmp/neura_summarized.json` に保存する。

#### 定数

| 定数 | 値 | 用途 |
|---|---|---|
| `BODY_MAX_CHARS_SELECT` | 700 | Stage 1 選定用の本文上限文字数 |
| `BODY_MAX_CHARS_TRANSLATE` | 3000 | Stage 2 翻訳用の本文上限文字数 |
| `SELECT_MAX` | 10 | Stage 1 で選ぶ件数の上限 |

Stage 1 で実際に選ぶ件数（`select_n`）はスロットの `max_articles`（`slot_max`）を基準に
`select_n = min(SELECT_MAX, slot_max + 5)` で決める。Stage 2 でのカテゴリ判定・重複除去により
一部が有効ジャンル外として弾かれるため、`slot_max` ちょうどではなく余裕（バッファ）を持たせる。
バッファは「Stage 2 応答が長くなりすぎて途中で切れる（JSON parse失敗）リスク」とのトレードオフのため、
`SELECT_MAX`（＝これまで実運用で問題なく処理できていた上限）を超えないようにキャップする。

#### 処理フロー

```python
def main():
    config = load_config()
    articles = load_json("/tmp/neura_collected.json")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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

    # ── Stage 1: タイトル＋冒頭700文字で選定 ─────────────────────────
    # 入力: 最大20件 × 700文字 ≒ 14,000文字（旧: 30件 × 3,000文字 ≒ 90,000文字）
    # スロットの有効ジャンルに該当する記事のみを選ぶよう Stage 1 プロンプトで明示的に指示する
    # （「優先」ではなく「該当する記事のみ」というハード制約。Stage 2 のジャンルフィルタで
    # 想定外に弾かれる件数を減らすため）
    slot_max = max(1, min(10, int(slot.get("max_articles", MAX_ARTICLES))))
    select_n = min(SELECT_MAX, slot_max + 5)
    sel_text = _call_gemini(client, build_selection_prompt(articles, n=select_n, genres=slot_genres), types)
    selected_urls = json.loads(sel_text)  # ["https://...", ...]
    selected = [a for a in articles if normalize_url(a["url"]) in url_set]
    # パース失敗・0件時は全件をフォールバック

    # ── Stage 2: 選定記事のみ翻訳・要約 ──────────────────────────────
    # response_schema を指定することで category が必ず enum 4値のいずれかになる
    result = _call_gemini_json(client, build_prompt(selected, config["gemini_prompt"]), types, response_schema=article_schema)
    # [{url, title_ja, summary_ja, key_points, translation_ja, category, importance}, ...]

    # カテゴリ正規化（念のため英語・日本語バリエーションをマッピング）
    for r in result:
        r["category"] = normalize_category(r.get("category"))

    # URL重複除去 → ジャンルフィルタ → 重要度降順で slot_max 件選定
    # 有効カテゴリの記事が0件の場合は [ERROR] をログ出力して exit(1)
    # → source/published_at を元記事から復元 → /tmp/neura_summarized.json に保存
```

#### 件数不足時のバックフィル

Stage 1のプロンプト指示（該当ジャンルのみ・絞りすぎない）だけでは、Gemini側の
選定漏れやStage 2での再分類により `slot_max` に届かないことがある
（例：2026-07-03・07-06・07-08 に実際に発生）。プロンプト調整のみでは解決しなかったため、
コード側で決定的に補うバックフィルを行う。

```
if len(result_sorted) < slot_max:
    tried_urls = 既にStage1で選定試行した記事のURL集合
    remaining = articles のうち tried_urls に含まれないもの（＝まだ試していない収集記事）
    shortfall = slot_max - len(result_sorted)
    if remaining:
        backfill_n = min(SELECT_MAX, shortfall + 5, len(remaining))
        # remaining だけを対象に Stage 1 選定プロンプトを再実行
        backfill_selected = build_selection_prompt(remaining, n=backfill_n, genres=slot_genres) → Gemini → URL照合
        if backfill_selected:
            # Stage 2 と同じ翻訳・要約・改行補正・カテゴリ正規化を行い、
            # 既存 result に重複除去しつつ追加
            result_sorted = select_articles(result, slot_genres, slot_max)  # 再計算
```

バックフィルは最大1回のみ（無限ループ防止）。`remaining` が空、またはバックフィルの
Stage 1選定結果が0件の場合はそのまま既存の `result_sorted` を採用する
（Gemini APIコール回数の上限は通常時2回・不足時最大4回）。

#### `_call_gemini` ヘルパー（APIリトライ共通化）

API例外のみリトライ対象。JSONパース失敗はリトライしない（→ `_call_gemini_json` を使う）。

```python
def _call_gemini(client, prompt: str, types) -> str:
    """最大3回リトライ・30秒間隔。API例外のみリトライ対象。全失敗時は sys.exit(1)。"""
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            return response.text
        except Exception as e:
            if attempt < 3:
                time.sleep(30)
    sys.exit(1)
```

#### `_call_gemini_json` ヘルパー（Stage 2用 JSONパースリトライ）

Stage 2専用。`_call_gemini` でのAPI呼び出し＋JSONパースをセットでリトライする。
Geminiが不正なJSONを返した場合も再呼び出しすることで回復を試みる。

```python
def _call_gemini_json(client, prompt: str, types, max_retries: int = 3) -> list:
    """APIエラー・JSONパース失敗どちらもリトライ対象。全失敗時は sys.exit(1)。"""
    for attempt in range(1, max_retries + 1):
        text = _call_gemini(client, prompt, types)
        try:
            result = json.loads(text)
            if not isinstance(result, list):
                raise ValueError("not a JSON array")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[WARN]  summarize: Stage 2 JSON parse attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(30)
    print("[ERROR] Gemini API failed after all retries")
    sys.exit(1)
```

#### `normalize_category` ヘルパー

Gemini が英語表記・日本語バリエーションでカテゴリを返した場合に正規4値へマッピングする。
正規値（`"ニュース" | "研究" | "活用事例" | "ツール"`）はそのまま返す。
マッピング不能な値は `[WARN]` を出力してそのまま返す（`select_articles` でフィルタされる）。

```python
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

def normalize_category(cat: str | None) -> str:
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
```

#### Stage 1 選定プロンプト（`SELECTION_PROMPT`）

`{genres}` にはスロットで有効なジャンルのみを渡す。「優先」という弱い表現ではなく、
該当ジャンル**のみ**を選ぶよう明示的に制約する（無効ジャンルの記事が選ばれてStage 2後に
弾かれる＝件数不足になる事態を防ぐため）。

```
以下のAI関連記事から、AIを学び始めた一般人が「面白い・試してみたい」と感じる記事を最大{n}件選んでください。
次のジャンルに該当する記事のみを選んでください（それ以外のジャンルの記事は選ばないでください）: {genres}
選んだ記事のURLだけをJSON配列（文字列のリスト）で返してください。

記事一覧:
[1] タイトル: ...
    URL: ...
    ソース: ...
    本文: ...（冒頭700文字）
...

URLのJSON配列のみを返してください。説明文は不要です。
```

#### Stage 2 翻訳プロンプト（`config.gemini_prompt` テンプレート）

プロンプト本文は config（`config.gemini_prompt`）のテンプレートを使い、`{articles}` を記事一覧テキストに置換する。

```python
def build_prompt(articles: list[dict], template: str) -> str:
    articles_text = "\n\n".join([
        f"[{i+1}] タイトル: {a['title']}\nURL: {a['url']}\nソース: {a['source']}\n"
        f"本文: {a['body_text'][:3000] if a['body_text'] else '（本文取得不可）'}"
        for i, a in enumerate(articles)
    ])

    # config由来のテンプレートに {articles} が無い場合はデフォルトにフォールバック
    if "{articles}" not in template:
        print("[WARN]  summarize: gemini_prompt に {articles} が無いためデフォルトを使用")
        template = DEFAULT_GEMINI_PROMPT  # config_loader.DEFAULT_CONFIG["gemini_prompt"]

    return template.replace("{articles}", articles_text)
```

**`DEFAULT_GEMINI_PROMPT`（テンプレート全文。`config_loader.DEFAULT_CONFIG["gemini_prompt"]` の実体）**
```
以下のAI関連記事から、最も重要・興味深い最大15件を選び、
各記事について以下の形式でJSON配列を返してください。
海外・日本語の両ソースからバランスよく選んでください。

各記事のJSONフィールド：
- url: 元記事のURLをそのまま返す（変更禁止）
- title_ja: 日本語タイトル（30文字以内。元が日本語の場合はそのまま使用）
- summary_ja: 日本語要約（80文字以内）
- key_points: この記事が伝えたいことを最大3つ、日本語の配列で返す（各項目40文字以内。内容が薄い記事は1〜2件でも可。本文取得不可の場合は空配列 []）
- translation_ja: 記事本文の全文日本語翻訳（markdown形式）
    - コードブロックは ```言語名 で囲んでそのまま保持（翻訳しない）
    - インラインコード（関数名・変数名・ライブラリ名）は `backtick` で囲んでそのまま保持
    - 見出しは ## / ### で構造を維持する
    - 箇条書きは - で保持する
    - 重要ワードは **太字** で保持する
    - URLリンクは除去してプレーンテキストにする
    - 本文が「（本文取得不可）」の場合は null を返す
- category: "ニュース" | "研究" | "活用事例" | "ツール" のいずれか
- importance: 1〜5の整数（5が最重要。AI業界への影響度・新規性・実用性で判断）

記事一覧:
{articles}

JSON配列のみを返してください。説明文・マークダウンの囲み・前後の文章は不要です。
```

#### 出力ファイル形式（`/tmp/neura_summarized.json`）

```json
[
  {
    "url": "https://example.com/article",
    "title_ja": "OpenAI、GPT-5を正式リリース",
    "summary_ja": "OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...",
    "key_points": ["推論能力が大幅に向上", "コンテキスト長が200万トークンに拡大", "SWE-benchで85%を達成"],
    "translation_ja": "## OpenAI、GPT-5を正式リリース\n\n...",
    "category": "ニュース",
    "importance": 5,
    "source": "HackerNews",
    "published_at": "2026-06-18T03:00:00Z"
  }
]
```

#### エラーハンドリング

| 状況 | 挙動 |
|---|---|
| `GEMINI_API_KEY` 未設定 | `[ERROR] GEMINI_API_KEY is not set` をログ出力してexit(1) |
| Gemini API 失敗（例外） | `[WARN]` をログ出力して30秒待機後リトライ（最大3回）。3回失敗で exit(1) |
| JSONパース失敗（Stage 2） | `[WARN]` をログ出力して30秒待機後リトライ（最大3回）。3回連続失敗で exit(1) |
| Gemini が非標準カテゴリを返却 | `response_schema` の enum 制約により発生しにくい。それでも非標準値が来た場合は `normalize_category` でマッピング。未知値は `[WARN]` ログ出力後 `select_articles` でフィルタ |
| Gemini が同じ URL を重複返却 | URL 正規化後に先着1件のみ残して除去（`[WARN] Gemini重複 N件を除去`） |
| 有効カテゴリの記事が0件 | `[ERROR] 有効カテゴリの記事が0件` をログ出力して exit(1)（後続の notify.py が実行されない） |
| 選出件数が5件未満 | そのまま続行（`[WARN] Only {n} articles selected`） |

---

### 2-5. `scripts/notify.py`（FR-03）

#### 役割
`/tmp/neura_summarized.json` を読み込み、Discord Webhookにサマリーを投稿する。

#### Discord Embed構造

```python
def build_discord_payload(articles: list[dict], date: str) -> dict:
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

    fields = []
    for art in articles:
        emoji = CATEGORY_EMOJI.get(art["category"], "📄")
        source = SOURCE_LABEL.get(art["source"], art["source"])
        # 各記事の value 末尾に \n​（ゼロ幅スペース）を付与して記事間の余白を確保
        fields.append({
            "name": f"{emoji} {art['title_ja']}",
            "value": f"{art['summary_ja']}\n[{source}]({art['url']})\n​",
            "inline": False
        })

    return {
        "embeds": [{
            "title": f"🧠 Neura Daily — {date}（{len(articles)}件）",
            "color": 0x7c6aff,  # アクセントパープル
            "fields": fields,
            "footer": {"text": "Neura by GitHub Actions"},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
```

#### 送信処理

```python
def main():
    articles = load_json("/tmp/neura_summarized.json")

    if not articles:
        print("[ERROR] notify: 通知対象の記事が0件のため送信をスキップ")
        sys.exit(1)

    date = datetime.utcnow().strftime("%Y/%m/%d")

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set")
        sys.exit(1)

    payload = build_discord_payload(articles, date)
    response = requests.post(webhook_url, json=payload, timeout=10)

    if response.status_code != 204:
        print(f"[ERROR] Discord webhook failed: {response.status_code}")
        sys.exit(1)

    print(f"[INFO] Discord notified: {len(articles)} articles")
```

#### エラーハンドリング

| 状況 | 挙動 |
|---|---|
| 記事リストが空（0件） | `[ERROR] 通知対象の記事が0件` をログ出力してexit(1)（Discord送信は行わない） |
| `DISCORD_WEBHOOK_URL` 未設定 | `[ERROR] DISCORD_WEBHOOK_URL is not set` をログ出力してexit(1) |
| HTTPステータスが204以外 | `[ERROR] Discord webhook failed: {status}` をログ出力してexit(1) |

---

### 2-6. `scripts/archive.py`（FR-04）

#### 役割
`/tmp/neura_summarized.json` を読み込み、日次JSONファイルの生成・`index.json` 更新・gitコミット＆プッシュを行う。

#### 処理フロー

```python
def main():
    articles = load_json("/tmp/neura_summarized.json")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    generated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # 0. ソース別収集ステータスファイルをリポジトリにコピー（git add docs/data/ で一緒にコミットされる）
    import shutil
    status_src = "/tmp/neura_collect_status.json"
    if os.path.exists(status_src):
        shutil.copy(status_src, os.path.join(DATA_DIR, "collect_status.json"))
        print("[INFO]  archive: collect_status.json 更新")

    # JST時刻を計算（ファイル名・timeフィールドに使用）
    now_jst = datetime.now(tz=timezone.utc) + timedelta(hours=9)
    today = now_jst.strftime("%Y-%m-%d")
    hour_jst = now_jst.hour
    file_key = f"{today}_{hour_jst:02d}"   # 例: "2026-06-25_18"
    time_str = f"{hour_jst:02d}:00"        # 例: "18:00"

    # 1. 日次JSONを生成（ファイル名に時刻を含める）
    daily_data = {
        "date": today,
        "time": time_str,
        "generated_at": generated_at,
        "articles": articles
    }
    daily_path = f"docs/data/{file_key}.json"   # 例: docs/data/2026-06-25_18.json
    save_json(daily_path, daily_data)
    print(f"[INFO] Created {daily_path}")

    # 2. index.jsonを更新（件数・カテゴリ内訳を集計して追記）
    from collections import Counter
    cats = Counter(a["category"] for a in articles)
    titles = [{"t": a.get("title_ja",""), "c": a.get("category","")} for a in articles[:10]]
    meta = {
        "date": today,
        "time": time_str,
        "file": file_key,
        "count": len(articles),
        "categories": dict(cats),
        "titles": titles,
    }

    index_path = "docs/data/index.json"
    index = load_json(index_path) if os.path.exists(index_path) else {"digests": []}
    # 同一 (date, time) の既存エントリを除去してから先頭に追加
    key = (today, time_str)
    index["digests"] = [d for d in index["digests"] if (d["date"], d.get("time","")) != key]
    index["digests"].insert(0, meta)
    index["digests"] = index["digests"][:100]
    save_json(index_path, index)
    print(f"[INFO] Updated index.json: {len(index['digests'])} digests")

    # 3. git commit & push
    run_git_commands(today)

def run_git_commands(today: str):
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
```

#### エラーハンドリング

| 状況 | 挙動 |
|---|---|
| `git commit` 失敗 | `[ERROR] Git command failed` をログ出力してexit(1) |
| `git push` が non-fast-forward で失敗 | 設定画面（FR-06）が同タイミングで `config/config.json` を更新した場合に発生し得る。`[WARN]` をログ出力し `git pull --rebase` 後に1回だけ再push を試みる。それでも失敗する場合（rebase自体の失敗含む）は `[ERROR]` をログ出力してexit(1) |

---

## 3. フロントエンド仕様（`docs/index.html`）

### 3-1. 画面・関数マップ

| 画面 | URLパラメータ | 主要関数 |
|---|---|---|
| SCR-01：ホーム | なし | `showHome()` → `loadHome()` → `renderHome(index)` |
| SCR-02：日次詳細 | `?date=YYYY-MM-DD` | `showDetail(date)` → `loadDetail(date)` → `renderDetail(digest)` |
| SCR-03：検索結果 | `?q=キーワード` | `showSearch(q)` → `loadSearch(q)` → `renderSearch(q, allArticles)` |
| SCR-04：設定 | `?view=settings` | `showSettings()` → `loadConfig()` → `renderSettings(config)` |

**共通ユーティリティ関数**

| 関数 | 用途 |
|---|---|
| `toggleTranslation(idx)` | SCR-02の翻訳パネルを展開/折りたたむ |
| `toggleTranslationById(panelId, btnId)` | SCR-03の翻訳パネルを展開/折りたたむ |
| `toggleMonth(ym)` | SCR-01の月グループを展開/折りたたむ |
| `matchesQuery(art, keywords)` | SCR-03のAND検索マッチ判定 |
| `renderMarkdown(md)` | markdown文字列をHTML文字列に変換（翻訳パネル内で使用） |
| `keyPointsBlock(keyPoints)` | `key_points` 配列を箇条書きHTMLに変換（翻訳パネル先頭に挿入。空配列時は空文字列） |
| `highlightKeyword(container, kw)` | SCR-03の検索結果内キーワードを紫色ハイライト |
| `goHome()` / `goDetail(date)` / `goSearch(q)` / `goSettings()` | HistoryAPI を使った画面遷移 |
| `ghGetConfig()` / `ghPutConfig(config)` | GitHub Contents API で config.json を取得/更新（SCR-04・FR-06） |
| `jstHourToCron(hour)` | JST 時刻（0〜23）を UTC cron 式（`'0 {utc} * * *'`）に変換（cron-job.org 設定用） |
| `getGithubCreds()` / `setGithubCreds()` | localStorage の owner/repo/PAT を読み書き（SCR-04・FR-06） |
| `fetchLastRunStatus()` | GitHub Actions API で最終ワークフロー実行のステータスを取得し `#src-run-status` に反映 |
| `fetchSourceStatus()` | GitHub Contents API で `docs/data/collect_status.json` を取得し、各ソース行に失敗バッジを表示 |

### 3-2. ルーター

```javascript
// URLパラメータを読んで適切な画面を表示する
function init() {
    const params = new URLSearchParams(window.location.search);
    const date = params.get('date');
    const q    = params.get('q');
    const view = params.get('view');
    if (view === 'settings') showSettings();
    else if (date)           showDetail(date);
    else if (q)              showSearch(q);
    else                     showHome();
}

window.addEventListener('popstate', init);  // ブラウザ戻る/進む対応
```

### 3-3. データ取得関数

本実装では `/tmp` ではなく `docs/data/` からfetchする。

```javascript
// index.jsonを取得してSCR-01を描画する
async function loadHome() {
    try {
        const res = await fetch('./data/index.json');
        if (!res.ok) throw new Error(res.status);
        const index = await res.json();
        renderHome(index);
    } catch (e) {
        showState('home', 'error');
    }
}

// 日次JSONを取得してSCR-02を描画する（fileは "2026-06-25_18" 形式）
async function loadDetail(file) {
    const date = file.slice(0, 10);  // 表示用日付を抽出
    try {
        const res = await fetch(`./data/${file}.json`);
        if (!res.ok) throw new Error(res.status);
        const digest = await res.json();
        renderDetail(digest, date);
    } catch (e) {
        showState('detail', 'error');
    }
}

// 全スロットのJSONを並列fetchしてSCR-03を描画する
async function loadSearch(q) {
    showState('search', 'loading');
    try {
        const indexRes = await fetch('./data/index.json');
        const index = await indexRes.json();

        // 全日次JSONを並列取得（一部失敗してもallSettledで続行）
        // meta.file がある場合はそれを、ない場合は meta.date をファイル名として使用（後方互換）
        const digests = await Promise.allSettled(
            index.digests.map(meta =>
                fetch(`./data/${meta.file || meta.date}.json`).then(r => r.json()).then(d => ({ date: meta.date, digest: d }))
            )
        );

        const allArticles = digests
            .filter(r => r.status === 'fulfilled')
            .flatMap(r => r.value.digest.articles.map(art => ({ ...art, date: r.value.date })));

        renderSearch(q, allArticles);
    } catch (e) {
        showState('search', 'error');
    }
}

// SCR-03のAND検索ロジック（renderSearch内で使用）
// q をスペース区切りで分割し、全キーワードが haystack に含まれる記事のみ返す（AND検索）
// 検索対象フィールド: title_ja, summary_ja, category, source（translation_ja は対象外）
function matchesQuery(art, keywords) {
    const haystack = [art.title_ja, art.summary_ja, art.category, sourceLabel(art.source)]
        .join(' ').toLowerCase();
    return keywords.every(kw => haystack.includes(kw));
}
// 呼び出し例:
//   const keywords = q.toLowerCase().split(/\s+/).filter(Boolean);
//   const hits = allArticles.filter(art => matchesQuery(art, keywords));
```

### 3-4. 状態管理

```javascript
// 各画面の表示状態を切り替えるヘルパー
// stateは 'loading' | 'content' | 'empty' | 'error' のいずれか
function showState(screen, state) { ... }

// 現在表示中の日付（SCR-02で使用）
let currentDate = null;
```

### 3-5. markdownレンダラー（インライン実装）

外部ライブラリを使用せず、以下の記法のみをサポートする。

| markdown記法 | 変換先HTML |
|---|---|
| ` ```lang\n...\n``` ` | `<pre><code>...</code></pre>`（シンタックスハイライト付き） |
| `` `code` `` | `<code>code</code>` |
| `**text**` | `<strong>text</strong>` |
| `## 見出し` | `<h2>見出し</h2>` |
| `### 見出し` | `<h3>見出し</h3>` |
| `- item` | `<ul><li>item</li></ul>` |
| 空行区切り | `<p>...</p>` |

**シンタックスハイライト対応言語**：`python` / `javascript`（エイリアス `js`） / `typescript`（エイリアス `ts`） / `bash`（エイリアス `sh`）（トークンベースの簡易実装）

### 3-6. 翻訳パネルのトグル

SCR-02 用（記事インデックスで管理）とSCR-03 用（ID文字列で管理）の2種類がある。

```javascript
// SCR-02 用：記事インデックス番号でパネルを特定する
function toggleTranslation(idx) {
    const panel = document.getElementById(`trans-panel-${idx}`);
    const btn   = document.getElementById(`trans-btn-${idx}`);
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    btn.textContent = isOpen ? '▼ 全文翻訳を見る' : '▲ 閉じる';
}

// SCR-03 用：検索結果は記事インデックスが動的に変わるためIDを直接渡す
// panelId: "sr-trans-{idx}"  /  btnId: "sr-trans-{idx}-btn"
function toggleTranslationById(panelId, btnId) {
    const panel = document.getElementById(panelId);
    const btn   = document.getElementById(btnId);
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    btn.textContent = isOpen ? '▼ 全文翻訳を見る' : '▲ 閉じる';
}
```

#### 伝えたいことブロック（`key_points`）

翻訳パネル（`.translation-panel`）の先頭要素として、`renderMarkdown(translation_ja)` の**前**に挿入する。全文翻訳モーダルは翻訳パネルの `innerHTML` をそのままコピーして表示するため、この配置により「モーダルタイトル直下」に表示される。

```javascript
function keyPointsBlock(keyPoints) {
    if (!keyPoints || keyPoints.length === 0) return '';  // 空配列・未定義（旧データ）は非表示
    const items = keyPoints.map(p => `<li>${escHtml(p)}</li>`).join('');
    return `<div class="key-points-block"><p class="key-points-label">💡 この記事が伝えたいこと</p><ul class="key-points-list">${items}</ul></div>`;
}

// transPanel 構築時（SCR-02・SCR-03 共通）
const transPanel = art.translation_ja
    ? `<div class="translation-panel" id="${panelId}">${keyPointsBlock(art.key_points)}${renderMarkdown(art.translation_ja)}</div>`
    : `<div class="translation-panel" id="${panelId}">${keyPointsBlock(art.key_points)}<p class="translation-unavailable">// 翻訳を取得できませんでした</p></div>`;
```

### 3-7. SCR-01：月別折りたたみ

```javascript
// 日付を月（YYYY-MM）でグループ化して月ヘッダーとカードを生成する
function renderHome(index) {
    // index.digests: [{date, count, categories}, ...]（降順）
    const byMonth = groupByMonth(index.digests);  // { "2026-06": [{date,count,categories}, ...] }
    const latestMonth = Object.keys(byMonth).sort().reverse()[0];
    // 各カードは meta.count と meta.categories から件数・カテゴリ分布バーを描画する
    // 最新月のみ自動展開、過去月は折りたたんだ状態で表示する
}

function toggleMonth(ym) {
    const el = document.getElementById(`mg-${ym}`);
    el.classList.toggle('open');
}
```

### 3-8. SCR-04：設定画面（FR-06）

#### GitHub接続情報（localStorage）

```javascript
// owner / repo / PAT は localStorage にのみ保存する（config.jsonには含めない）
function getGithubCreds() {
    return {
        owner: localStorage.getItem('neura_github_owner') || '',
        repo:  localStorage.getItem('neura_github_repo')  || '',
        pat:   localStorage.getItem('neura_github_pat')   || '',
    };
}
function setGithubCreds({ owner, repo, pat }) {
    if (owner !== undefined) localStorage.setItem('neura_github_owner', owner);
    if (repo  !== undefined) localStorage.setItem('neura_github_repo',  repo);
    if (pat   !== undefined) localStorage.setItem('neura_github_pat',   pat);
}
function clearGithubPat() { localStorage.removeItem('neura_github_pat'); }

// cron-job.org APIキー（localStorage にのみ保存）
function getCronJobKey() { return localStorage.getItem('neura_cronjob_apikey') || ''; }
function setCronJobKey(key) { localStorage.setItem('neura_cronjob_apikey', key); }
```

#### config.json の取得（GitHub Contents API）

```javascript
// 戻り値: { config: AppConfig, sha: string }
// sha は更新（PUT）時に必要なので保持する
async function ghGetConfig() {
    const { owner, repo, pat } = getGithubCreds();
    const res = await fetch(
        `https://api.github.com/repos/${owner}/${repo}/contents/config/config.json`,
        { headers: { Authorization: `Bearer ${pat}`, Accept: 'application/vnd.github+json' } }
    );
    if (res.status === 401) throw { code: 'ERR-08' };
    if (res.status === 403) throw { code: 'ERR-09' };
    if (res.status === 404) {
        // リポジトリは存在するがconfig.json未作成 → デフォルトで初期化（shaなし）
        // リポジトリ自体が無い場合も404になり得る。owner/repo設定の確認を促す。
        return { config: DEFAULT_CONFIG_JS, sha: null };
    }
    if (!res.ok) throw { code: 'ERR-11' };
    const data = await res.json();
    const config = JSON.parse(decodeBase64Utf8(data.content));  // atob + UTF-8デコード
    return { config, sha: data.sha };
}
```

#### config.json の更新（GitHub Contents API）

```javascript
async function ghPutConfig(config, sha) {
    const { owner, repo, pat } = getGithubCreds();
    const body = {
        message: 'chore: update config via settings UI',
        content: encodeBase64Utf8(JSON.stringify(config, null, 2)),  // UTF-8→Base64
        ...(sha ? { sha } : {})   // 既存ファイル更新時のみshaを付与
    };
    const res = await fetch(
        `https://api.github.com/repos/${owner}/${repo}/contents/config/config.json`,
        {
            method: 'PUT',
            headers: { Authorization: `Bearer ${pat}`, Accept: 'application/vnd.github+json' },
            body: JSON.stringify(body)
        }
    );
    if (res.status === 401) throw { code: 'ERR-08' };
    if (res.status === 403) throw { code: 'ERR-09' };
    if (res.status === 404) throw { code: 'ERR-10' };
    if (!res.ok) throw { code: 'ERR-11' };
    return await res.json();
}
```

#### ソース別収集ステータスの取得と表示（`fetchSourceStatus()`）

```javascript
// docs/data/collect_status.json を GitHub Contents API 経由で取得し、
// 各ソース行の .src-status-badge を更新する。
// loadConfig() 成功後に呼び出す。失敗時はサイレント（バッジ非表示のまま）。
async function fetchSourceStatus() {
    const { owner, repo, pat } = getGithubCreds();
    if (!pat || !owner || !repo) return;
    try {
        const res = await fetch(
            `https://api.github.com/repos/${owner}/${repo}/contents/docs/data/collect_status.json`,
            { headers: { Authorization: `Bearer ${pat}`, Accept: 'application/vnd.github+json' } }
        );
        if (!res.ok) return;
        const data = await res.json();
        const status = JSON.parse(decodeBase64Utf8(data.content));

        // 各ソース行の src-name 値をキーにして失敗バッジを表示/非表示切り替え
        document.querySelectorAll('#cfg-sources .source-row').forEach(row => {
            const name = row.querySelector('.src-name').value.trim();
            const badge = row.querySelector('.src-status-badge');
            if (!badge) return;
            const s = status.sources?.[name];
            if (s?.status === 'failed') {
                badge.textContent = '⚠ 取得失敗';
                badge.style.color = 'var(--warn)';
                badge.style.display = 'inline';
            } else if (s?.status === 'ok') {
                badge.textContent = '✓ 取得成功';
                badge.style.color = 'var(--accent)';
                badge.style.display = 'inline';
            } else {
                badge.style.display = '';
            }
        });
    } catch { /* サイレント */ }
}
```

**ソース行の `.src-status-badge` 要素**：`addSourceRow()` が各行に `<span class="src-status-badge">` を生成する（デフォルト `display:none`）。ソース行の右端（`×` ボタンの右）に配置する。成功時は `color:var(--accent)`（グリーン）、失敗時は `color:var(--warn)`（アンバー）で表示する。

**`src-run-status` の配置**：`## 収集ソース` セクションではなく、`## 実行スケジュール` セクションの直下（`cfg-schedules` の前）に配置する。

> **Base64とUTF-8の注意**：日本語を含むJSONを `btoa()` に直接渡すと文字化けする。`encodeBase64Utf8` は `btoa(unescape(encodeURIComponent(str)))`、`decodeBase64Utf8` は `decodeURIComponent(escape(atob(str)))` 相当の実装とする（またはTextEncoder/TextDecoderを使用）。

#### daily.yml の cron 式更新（廃止）

`daily.yml` の `on.schedule` は削除済み（GitHub Actions 内蔵 cron の遅延問題のため）。
スケジュール変更は cron-job.org API のみで行う（下記「cron-job.org スケジュール更新」セクション参照）。

#### cron-job.org スケジュール更新（cron-job.org API）

```javascript
// enabled かつ cron_job_id が設定されているスロットをすべて更新する
// APIキー未設定（空文字）の場合は何もしない（optional 機能）
// 失敗時: ERR-14 をスロー（daily.yml は更新済みのため saveSettings はエラー表示だけして継続）
async function cronJobOrgUpdate(schedules) {
    const apiKey = getCronJobKey();
    if (!apiKey) return;
    for (const slot of schedules.filter(s => s.enabled && s.cron_job_id)) {
        const res = await fetch(`https://api.cron-job.org/jobs/${slot.cron_job_id}`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job: {
                    schedule: {
                        timezone: 'Asia/Tokyo',
                        hours:  [slot.hour],
                        minutes: [0],
                        mdays:   [-1],
                        months:  [-1],
                        wdays:   [-1]
                    }
                }
            })
        });
        if (!res.ok) throw { code: 'ERR-14' };
    }
}
```

**cron-job.org API補足**：`PATCH /jobs/{jobId}` のリクエストボディは上記 `job.schedule` 構造を使用する。`timezone: 'Asia/Tokyo'` を指定することで JST 時刻をそのまま `hours` に渡せる。`-1` は cron の `*`（すべて）を意味する。

#### 保存フロー（バリデーション含む）

```javascript
async function saveSettings(config, prevSchedules) {
    // ERR-12: 有効ソースの URL が空または https:// 以外
    const invalidSrcs = config.sources.filter(s => s.enabled && !s.url.startsWith('https://'));
    if (invalidSrcs.length > 0) {
        highlightInvalidUrls();   // 該当行の URL 欄を赤枠表示
        showSrcError('ERR-12');
        return;
    }
    // 少なくとも1スロットが enabled でなければならない（ERR-13）
    if (!config.notify_schedules.some(s => s.enabled)) {
        showSchedError('ERR-13');
        return;
    }
    const { pat } = getGithubCreds();
    if (!pat) { showBanner('PAT未設定'); return; }   // 保存ボタンは通常disabled

    try {
        const { sha } = await ghGetConfig();   // 最新shaを取得
        await ghPutConfig(config, sha);
    } catch (e) {
        showBanner(ERROR_MESSAGES[e.code] || ERROR_MESSAGES['ERR-11']);
        return;
    }

    // notify_schedules が変更された場合のみ cron-job.org を更新する
    // ※ daily.yml は workflow_dispatch のみで schedule ブロックを持たないため ghPutWorkflow() は呼ばない
    const schedulesChanged = JSON.stringify(config.notify_schedules.map(s => ({hour: s.hour, enabled: s.enabled})))
        !== JSON.stringify((prevSchedules || []).map(s => ({hour: s.hour, enabled: s.enabled})));
    if (schedulesChanged) {
        // cron-job.org APIキーが設定されている場合のみ更新（任意機能）
        try {
            await cronJobOrgUpdate(config.notify_schedules);
        } catch (e) {
            showBanner(ERROR_MESSAGES['ERR-14']);  // config は保存済みのため return しない
        }
    }

    showToast('✅ 設定を保存しました。次回の定時実行から反映されます。');
}
```

#### デフォルト設定（フロントエンド）

`DEFAULT_CONFIG_JS` は config.json が未作成（404）の場合にフォームへ表示する初期値。requirements.md FR-06 / detailed_design §1-3 のデフォルト値と同一内容をJSオブジェクトで保持する。

---

## 4. 型定義

### 4-1. Python TypedDict（`scripts/`共通）

```python
# scripts/schemas.py（共通型定義ファイル。types.pyは標準ライブラリと衝突するため不可）
from typing import TypedDict, Optional

class Source(TypedDict):
    name: str
    url: str
    type: str            # "hackernews" | "reddit" | "rss" | "zenn" | "hatena"
    enabled: bool

class Keywords(TypedDict):
    en: list[str]
    ja: list[str]

class NotifySchedule(TypedDict):
    hour: int               # JST 0〜23
    enabled: bool
    max_articles: int       # このスロットの通知件数上限（1〜10）
    genres: dict[str, bool] # このスロットで通知するジャンル
    cron_job_id: Optional[str]  # cron-job.org のジョブID（UI管理・Pythonスクリプトは不使用）

class AppConfig(TypedDict):
    sources: list[Source]
    keywords: Keywords
    gemini_prompt: str          # {articles} プレースホルダーを含む
    notify_schedules: list[NotifySchedule]  # 通知スケジュール（最大3件）

class CollectedArticle(TypedDict):
    title: str
    url: str
    source: str          # "HackerNews" | "Reddit" | "RSS" | "Zenn" | "HatenaBookmark"
    score: int
    published_at: str    # ISO 8601 UTC
    body_text: Optional[str]

class Article(TypedDict):
    title_ja: str
    summary_ja: str
    key_points: list[str]  # 最大3件。内容が薄い記事は1〜2件、本文取得不可時は空配列
    translation_ja: Optional[str]
    category: str        # "ニュース" | "研究" | "活用事例" | "ツール"
    importance: int      # 1〜5
    url: str
    source: str
    published_at: str

class DailyDigest(TypedDict):
    date: str            # YYYY-MM-DD
    generated_at: str    # ISO 8601 UTC
    articles: list[Article]

class DigestMeta(TypedDict):
    date: str                  # YYYY-MM-DD
    count: int                 # その日の記事件数
    categories: dict[str, int] # カテゴリ別件数（存在するカテゴリのみ）

class DigestIndex(TypedDict):
    digests: list[DigestMeta]  # 降順・最大100件
```

### 4-2. フロントエンド型（JSDoc形式）

```javascript
/**
 * @typedef {Object} Article
 * @property {string} title_ja
 * @property {string} summary_ja
 * @property {string[]} key_points  - 伝えたいこと（最大3件）。過去データには存在しない場合あり
 * @property {string|null} translation_ja  - markdown形式。取得失敗時はnull
 * @property {"ニュース"|"研究"|"活用事例"|"ツール"} category
 * @property {number} importance  - 1〜5
 * @property {string} url
 * @property {"HackerNews"|"Reddit"|"RSS"|"Zenn"|"HatenaBookmark"} source
 * @property {string} published_at  - ISO 8601 UTC
 */

/**
 * @typedef {Object} DailyDigest
 * @property {string} date  - YYYY-MM-DD
 * @property {string} generated_at  - ISO 8601 UTC
 * @property {Article[]} articles
 */

/**
 * @typedef {Object} DigestMeta
 * @property {string} date  - YYYY-MM-DD
 * @property {number} count  - その日の記事件数
 * @property {Object.<string, number>} categories  - カテゴリ別件数
 *
 * @typedef {Object} DigestIndex
 * @property {DigestMeta[]} digests  - 降順・最大100件
 */

/**
 * SCR-03専用：日付情報を付加した記事型
 * @typedef {Article & { date: string }} ArticleWithDate
 */

/**
 * SCR-04専用：収集設定（config/config.json）
 * @typedef {Object} Source
 * @property {string} name
 * @property {string} url
 * @property {"hackernews"|"reddit"|"rss"|"zenn"|"hatena"} type
 * @property {boolean} enabled
 *
 * @typedef {Object} NotifySchedule
 * @property {number} hour  - 0〜23（JST）
 * @property {boolean} enabled
 * @property {number} max_articles  - 1〜10
 * @property {Object.<string, boolean>} genres
 *
 * @typedef {Object} AppConfig
 * @property {Source[]} sources
 * @property {{en: string[], ja: string[]}} keywords
 * @property {string} gemini_prompt  - {articles} プレースホルダーを含む
 * @property {NotifySchedule[]} notify_schedules  - 最大3件
 */
```

---

## 5. `requirements.txt`

```
aiohttp==3.9.5
feedparser==6.0.11
trafilatura==1.12.2
google-genai
requests==2.31.0
```

> `google-genai`：Google の新しい Python SDK（旧 `google-generativeai` から移行済み）。`from google import genai` でインポートし `genai.Client(api_key=...)` で使用する。バージョンピン留めなし（最新を使用）。
> `trafilatura` は 1.8.0 だと依存（htmldate / lxml.html.clean）が現行 lxml と衝突するため 1.12.2 に更新済み。`fetch_url` / `extract` の API は同一。

---

## 6. GitHub Actions ワークフロー詳細（`.github/workflows/daily.yml`）

```yaml
name: Neura Daily Digest

on:
  schedule:
    # notify_schedules の enabled:true スロット数分の cron エントリが生成される（最大3件）
    # 設定画面（SCR-04）で notify_schedules が変更されると自動で書き換えられる
    - cron: '0 4 * * *'    # スロット1: 13:00 JST（デフォルト）
    # - cron: '0 11 * * *' # スロット2: 20:00 JST（有効にすると追加）
    # - cron: '0 23 * * *' # スロット3: 08:00 JST（有効にすると追加）
  workflow_dispatch:         # 手動実行（テスト用）

jobs:
  daily-digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # git push のために必要

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'       # requirements.txtをキャッシュして高速化

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Collect articles (FR-01)
        run: python scripts/collect.py
        # 失敗時: 後続ステップはすべてスキップされる（exit(1)による）

      - name: Summarize with Gemini (FR-02)
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python scripts/summarize.py

      - name: Notify Discord (FR-03)
        continue-on-error: true   # Discord失敗でもarchive.pyを必ず実行する
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python scripts/notify.py

      - name: Archive to GitHub Pages (FR-04)
        run: python scripts/archive.py
        # GITHUB_TOKEN はcheckout時に自動設定されるため env: 不要
```

---

## 7. エラー定義一覧

| エラーID | 対応FR | 発生箇所 | 発生条件 | 挙動 |
|---|---|---|---|---|
| ERR-01 | FR-05 | フロントエンド | `index.json` のfetch失敗 | SCR-01にエラーメッセージを表示 |
| ERR-02 | FR-05 | フロントエンド | 存在しない `?date=` を指定 | SCR-02にエラーメッセージ＋「← 一覧に戻る」を表示 |
| ERR-03 | FR-05 | フロントエンド | 当日13時前にアクセス（JSONがまだ存在しない） | ERR-02と同じメッセージを表示 |
| ERR-04 | FR-01 | `collect.py` | 全収集ソースが失敗 | `[ERROR] All sources failed` をログ出力してexit(1) |
| ERR-05 | FR-02 | `summarize.py` | Gemini APIタイムアウト（最大3回リトライ後exit(1)）・JSONパース失敗（Stage 2で最大3回リトライ後exit(1)） | `[ERROR]` をログ出力してexit(1)、Discord通知なし |
| ERR-06 | FR-03 | `notify.py` | Discord Webhook失敗 | `[ERROR]` をログ出力してexit(1) |
| ERR-07 | FR-04 | `archive.py` | gitコミット失敗 | `[ERROR]` をログ出力してexit(1) |
| ERR-08 | FR-06 | フロントエンド（SCR-04） | GitHub API 401（PAT認証失敗） | バナー表示：`"GitHub PATの認証に失敗しました。PATが正しいか確認してください。"` |
| ERR-09 | FR-06 | フロントエンド（SCR-04） | GitHub API 403（権限不足） | バナー表示：`"PATにリポジトリへの書き込み権限がありません。スコープ 'repo' を確認してください。"` |
| ERR-10 | FR-06 | フロントエンド（SCR-04） | GitHub API 404（リポジトリ未発見） | バナー表示：`"リポジトリが見つかりません。Owner / Repo の設定を確認してください。"` |
| ERR-11 | FR-06 | フロントエンド（SCR-04） | その他HTTP/ネットワークエラー | バナー表示：`"設定の保存に失敗しました。しばらく後に再試行してください。"` |
| ERR-12 | FR-06 | フロントエンド（SCR-04） | URL が空または `https://` 以外 | ソースセクション上部に表示：`"URLが未入力またはhttps://で始まっていないソースがあります。"` 該当行URL欄を赤枠表示 |
| ERR-13 | FR-06 | フロントエンド（SCR-04） | `.github/workflows/daily.yml` の PUT 失敗（権限不足・置換失敗等） | バナー表示：`"設定は保存しましたが、実行時刻の更新に失敗しました。PATに 'workflow' スコープがあるか確認してください。"`（config.json は保存済み） |
| ERR-14 | FR-06 | フロントエンド（SCR-04） | cron-job.org API の PATCH 失敗（APIキー無効・ジョブID誤り・CORS等） | バナー表示：`"設定は保存しましたが、cron-job.org のスケジュール更新に失敗しました。APIキーとジョブIDを確認してください。"`（config.json・daily.yml は保存済み） |

> ERR-04〜07はすべてGitHub Actionsのログおよびワークフロー失敗通知で検知する。
> - ERR-04・ERR-05：Pythonスクリプトのexit(1)によりワークフローが失敗状態になる。GitHub Actionsのデフォルト失敗通知（メール等）で検知する
> - ERR-06：`continue-on-error: true` により後続のarchive.pyは実行される。Discordへのエラー通知はDiscord自体が宛先のため実装しない
> - ERR-07：gitコミット失敗はGitHub Actionsのステップログで確認する
> - ERR-08〜12・ERR-13：設定画面（SCR-04）のブラウザ内エラー。バナーまたはフィールド直下に表示する。
> - `fetchLastRunStatus()`：PAT 設定済み時に `GET /repos/{owner}/{repo}/actions/workflows/daily.yml/runs?per_page=1` を呼び出し、`workflow_runs[0].conclusion` と `created_at` を `#src-run-status` 要素に反映する。失敗時は非表示（サイレント）。
> - なお `config/config.json` の不在・パース失敗はエラーではなくデフォルト値で続行する（`config_loader.py`・`[WARN]`）。

---

## 8. ログ出力規則

全スクリプトで以下のフォーマットを統一する。

```python
print(f"[INFO]  collect: HackerNews → 12件取得")
print(f"[INFO]  collect: フィルタ後 → 8件")
print(f"[WARN]  collect: Reddit timeout（スキップ）")
print(f"[INFO]  summarize: Gemini → 7件選出")
print(f"[INFO]  notify: Discord通知完了")
print(f"[INFO]  archive: docs/data/2026-06-18.json 生成")
print(f"[INFO]  archive: index.json 更新（30件）")
print(f"[ERROR] summarize: Gemini APIタイムアウト")
```

GitHubのActionsタブでステップごとのログを確認できる。
