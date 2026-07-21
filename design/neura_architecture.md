# アーキテクチャ設計書

> **プロジェクト名**：Neura
> **対象フェーズ**：Phase 1（MVP）のみ
> **このドキュメントの用途**：Claude Codeでの実装に使用する。技術スタック・システム構成・ディレクトリ構成・環境変数を記載している。
> **関連ドキュメント**：
> - `neura_requirements.md`（機能要件・非機能要件）
> - `neura_setup.md`（開発着手前チェックリスト・各種設定手順）
> - `neura_basic_design.md`（画面仕様・モック実装指示 ※技術スタック・ディレクトリ構成をSection 0に転記する）

---

## 技術スタック

| カテゴリ | 採用技術 | バージョン | 選定理由 |
|---|---|---|---|
| 言語 | Python | 3.11 | データ収集・HTTP処理・AI API連携すべてに対応。GitHub Actionsとの親和性が高く、asyncioによる並列HTTPリクエストが容易 |
| 非同期HTTP | aiohttp | 3.9 | asyncioと組み合わせて全ソースへの並列リクエストを実現。requests と異なり async/await で書けるため並列収集のコードが簡潔 |
| RSS解析 | feedparser | 6.0 | RSSおよびAtomフィードのパースに特化。エンコーディング・日付の正規化を自動処理するため自前パースが不要 |
| 本文抽出 | trafilatura | 1.12.2 | 記事URLから本文テキストを抽出するライブラリ。広告・ナビゲーション等のノイズを除去し、コードブロックを含む本文だけを返す。ペイウォール・403の場合はNoneを返す（1.8系は依存衝突のため1.12系を採用） |
| AI要約・翻訳 | google-genai | 1.x | Gemini Flash（gemini-2.5-flash）の無料枠（1500 req/日）を使用。Stage 1（選定）・Stage 2（翻訳）の2段階呼び出しで要約・全文翻訳・カテゴリ分類・重要度スコアリングを処理 |
| Discord通知 | requests | 2.31 | Discord Webhook へのPOSTのみ。asyncio不要の単純なHTTPリクエストなのでrequestsで十分 |
| スケジューラ | GitHub Actions + cron-job.org | - | GitHub Actionsの`schedule`は1〜4時間遅延するため、外部の無料cronサービスcron-job.orgから正確な時刻に`workflow_dispatch`を叩く方式を採用（`daily.yml`に`schedule:`ブロックは存在しない）。無料枠2000分/月で1回5分以内の実行なら余裕で収まる |
| フロントエンド | バニラHTML/CSS/JS | - | フレームワーク不要の静的1ファイル構成。GitHub Pagesで即時配信可能。ビルドステップが不要でメンテが容易 |
| ホスティング | GitHub Pages | - | GitHubリポジトリの `docs/` フォルダを直接配信。月額ゼロ・CDN付き・カスタムドメイン対応 |
| データ保存 | JSONファイル（Gitリポジトリ） | - | DBサーバー不要。GitHub Actionsが生成したJSONをコミットするだけで永続化とバージョン管理が同時に完了 |

---

## システム構成図

```
[config/config.json] ←─ GitHub Contents API（PUT）←─ [docs/index.html 設定画面（SCR-04）]
        |                                                  ブラウザからPAT認証で直接更新（FR-06）
        | 読み込み（config_loader.py）
        ↓
[cron-job.org] notify_schedulesの有効スロット数分のジョブ（JST時刻） ──trigger(workflow_dispatch)──→ [daily.yml]
        |
        ↓
[collect.py：並列HTTPリクエスト（asyncio + aiohttp）／config.sources・keywords を使用]
        |
        ├──→ Hacker News Firebase API
        │     https://hacker-news.firebaseio.com/v0/topstories.json
        │
        ├──→ Reddit RSS × 2（.json はBotブロックのためRSS）
        │     https://www.reddit.com/r/artificial/top/.rss?t=day
        │     https://www.reddit.com/r/MachineLearning/top/.rss?t=day
        │
        ├──→ RSS（feedparser）× 3
        │     TechCrunch AI / MIT Tech Review AI / VentureBeat AI
        │
        ├──→ Zenn RSS（feedparser）
        │     https://zenn.dev/topics/ai/feed
        │
        └──→ はてなブックマーク hotentry RSS（feedparser・.json は302のためRSS）
              https://b.hatena.ne.jp/hotentry/it.rss
                        |
                        ↓ 全ソース結果をマージ・AIキーワードフィルタ・重複排除・上位20件
[summarize.py：AI要約・分類（2段階）]
        |
        ├─ Stage 1 ─→ Gemini Flash API（google-genai）
        │             gemini-2.5-flash / タイトル＋冒頭700文字で記事選定（URLリスト返却）
        │
        └─ Stage 2 ─→ Gemini Flash API（google-genai）
                      gemini-2.5-flash / 選定記事のみ翻訳・要約・カテゴリ・重要度・key_pointsを生成
                        |
                        ↓ 最終記事オブジェクト（スロットフィルタ後 1〜10件）
        ┌───────────────┴───────────────┐
        ↓                               ↓
[notify.py]                      [archive.py]
Discord Webhook POST              docs/data/{YYYY-MM-DD}.json 生成
key_points含む・6000字超過時は     docs/data/index.json 更新
重要度の低い記事から削って調整            |
（requests）                      ↓ git commit & push（GITHUB_TOKEN）
        |                       [GitHubリポジトリ docs/]
        ↓                               |
[Discordチャンネル]                      ↓ GitHub Pages 自動配信
                                 [docs/index.html]
                                 ブラウザでアーカイブ閲覧・既読管理（localStorage・FR-07）

─────────────────────────────────────────────────────────────

[cron-job.org] 固定ジョブ：毎日9:00 JST ──trigger(workflow_dispatch)──→ [remind.yml]
        ↓
[remind.py：FR-08] docs/data/{前日日付}.json の存在確認
        |
        ↓ 存在する場合のみ
[Discordチャンネル] 「昨日のダイジェストまだの方はこちら」1通のみ送信

─────────────────────────────────────────────────────────────

[cron-job.org] 固定ジョブ：毎週土曜12:00 JST ──trigger(workflow_dispatch)──→ [weekly.yml]
        ↓
[weekly_digest.py：FR-09] docs/data/index.json 経由で直近7日分の digests を抽出し、対応する docs/data/{file}.json を集計
        |
        ↓
[Discordチャンネル] 週間サマリー（件数・カテゴリ内訳・注目記事トップ5）
```

### 処理の補足

| 処理 | 使用API / ライブラリ | 認証方式 |
|---|---|---|
| HN記事取得 | Firebase REST API（`GET topstories.json` → 各 `GET {id}.json`） | 不要 |
| Reddit記事取得 | Reddit RSS（`GET /r/{sub}/top/.rss?t=day` → feedparser） | 不要（browser風User-Agent必須。.jsonはBotブロック） |
| RSS取得 | `feedparser.parse(url)` | 不要 |
| Zenn RSS取得 | `feedparser.parse(url)` | 不要 |
| はてブ取得 | `GET https://b.hatena.ne.jp/hotentry/it.rss`（feedparser・hatena:bookmarkcount） | 不要 |
| Gemini API呼び出し | `genai.Client(api_key=...).models.generate_content(model='gemini-2.5-flash', ...)` | `GEMINI_API_KEY`（環境変数） |
| Discord通知 | `requests.post(DISCORD_WEBHOOK_URL, json=payload)` | `DISCORD_WEBHOOK_URL`（環境変数） |
| GitHubコミット | `git add / commit / push`（GitHub Actions内） | `GITHUB_TOKEN`（Actions自動提供） |
| 設定読み込み（FR-06） | `config_loader.load_config()`（ローカルの `config/config.json` を読む） | 不要（チェックアウト済みファイル） |
| 設定更新（FR-06） | ブラウザから `GET/PUT https://api.github.com/repos/{owner}/{repo}/contents/config/config.json` | GitHub PAT（`localStorage` に保存。`repo` スコープ） |
| 既読管理（FR-07） | ブラウザの `localStorage.getItem/setItem('neura_read_articles')` | 不要（サーバー通信なし） |
| リマインド送信（FR-08） | `requests.post(DISCORD_WEBHOOK_URL, json=payload)` | `DISCORD_WEBHOOK_URL`（環境変数。notify.pyと共用） |
| 週次ダイジェスト送信（FR-09） | `requests.post(DISCORD_WEBHOOK_URL, json=payload)` | `DISCORD_WEBHOOK_URL`（環境変数。notify.pyと共用） |

---

## ディレクトリ構成

```
neura/                                    ← プロジェクトルート
├── .github/
│   └── workflows/
│       ├── daily.yml                     # cron-job.orgからのworkflow_dispatchで起動。全スクリプトを順番に呼び出す（`schedule:`ブロックなし）
│       ├── remind.yml                    # FR-08：cron-job.orgの固定ジョブ（毎日9:00 JST）から起動。remind.pyを実行
│       └── weekly.yml                    # FR-09：cron-job.orgの固定ジョブ（毎週土曜12:00 JST）から起動。weekly_digest.pyを実行
├── config/
│   └── config.json                       # FR-06：収集設定（ソース・キーワード・Geminiプロンプト・notify_schedules）。デフォルト値を同梱し、設定画面から GitHub API で更新する
├── scripts/
│   ├── schemas.py                        # Python TypedDict共通型定義（AppConfig・CollectedArticle・Article・DailyDigest・DigestIndex）※標準ライブラリ types との衝突回避のため types.py としない
│   ├── config_loader.py                  # FR-06：config/config.json を読み込む。不在/破損時はデフォルト値を返す。collect.py・summarize.py から使用
│   ├── collect.py                        # FR-01：config の sources/keywords を読み、全ソースから並列取得・フィルタ・重複排除
│   ├── summarize.py                      # FR-02：config の gemini_prompt/genres を読み、Gemini Flash APIで日本語要約・カテゴリ分類・ジャンル絞込み
│   ├── notify.py                         # FR-03：Discord Webhookでサマリー送信（key_points・6000字切り詰め対応）
│   ├── archive.py                        # FR-04：JSONファイル生成・index.json更新・gitコミット
│   ├── remind.py                         # FR-08：前日データの存在確認・未読リマインド送信
│   └── weekly_digest.py                  # FR-09：直近7日分の集計・週次サマリー送信
├── docs/
│   ├── index.html                        # FR-05/FR-06/FR-07：GitHub Pagesで配信するアーカイブサイト＋設定画面＋既読管理（1ファイル完結）
│   └── data/
│       ├── index.json                    # 日付×時刻ごとのdigestメタ情報一覧（降順・最新100件、各エントリが`file`キーで対応する日次JSONファイル名を持つ）
│       └── {YYYY-MM-DD}_{HH}.json       # 日次記事データ（1配信スロットごとに1ファイル。Actions実行ごとに自動生成）
├── requirements.txt                      # Python依存パッケージ一覧
├── .env.example                          # 環境変数テンプレート（コミット対象）
└── README.md
```

### 各ファイルの責務

| ファイル | 責務 |
|---|---|
| `.github/workflows/daily.yml` | cron-job.orgからの`workflow_dispatch`で起動。Python環境セットアップ・`collect.py`→`summarize.py`→`notify.py`→`archive.py` の順次実行・シークレット注入を担う |
| `.github/workflows/remind.yml` | FR-08：cron-job.orgの固定ジョブ（毎日9:00 JST）からの`workflow_dispatch`で起動。Python環境セットアップ・`remind.py` の実行・シークレット注入を担う |
| `.github/workflows/weekly.yml` | FR-09：cron-job.orgの固定ジョブ（毎週土曜12:00 JST）からの`workflow_dispatch`で起動。Python環境セットアップ・`weekly_digest.py` の実行・シークレット注入を担う |
| `config/config.json` | FR-06の収集設定。`sources`・`keywords`・`gemini_prompt`・`notify_schedules`（`cron_job_id`含む）を保持。リポジトリにデフォルト値を同梱する。設定画面（`docs/index.html`）が GitHub Contents API 経由で直接更新する |
| `scripts/schemas.py` | Python TypedDictによる共通型定義。`AppConfig`・`CollectedArticle`・`Article`・`DailyDigest`・`DigestIndex` を定義し、全スクリプトからimportして使用する。※ファイル名を `types.py` にすると標準ライブラリ `types` を `sys.path[0]` でシャドーイングし依存ライブラリが壊れるため `schemas.py` とする |
| `scripts/config_loader.py` | `config/config.json` を読み込み `AppConfig` を返す。ファイル不在・JSONパース失敗時はデフォルト値を返す（`[WARN]` ログ）。`collect.py`・`summarize.py` から使用する |
| `scripts/collect.py` | `config_loader` で設定を読み、`sources`（有効なもののみ・`type`でパーサ振分け）・`keywords` に従って全ソースへ並列HTTPリクエスト・AIキーワードフィルタ・重複URL排除・上位20件の選定（スコア系14件＋日付系6件）・`trafilatura` による本文テキスト取得。結果を `/tmp/neura_collected.json` に書き出して次スクリプトに渡す |
| `scripts/summarize.py` | `collect.py` の出力を受け取り Gemini Flash API を2段階で呼び出す。Stage 1: 冒頭700文字で最大10件を選定（URLリスト返却）。Stage 2: 選定記事のみ `config.gemini_prompt` で翻訳・要約・カテゴリ・重要度・`key_points`を生成。スロット設定のジャンルフィルタ・件数上限を適用して `/tmp/neura_summarized.json` に保存 |
| `scripts/notify.py` | `summarize.py` の出力をDiscord Embed形式（`key_points`箇条書き含む）に変換してWebhook POSTする。全embed合計が6,000字を超える場合は`importance`昇順に`key_points`を削って調整する。エラー時はログ出力のみ |
| `scripts/archive.py` | `summarize.py` の出力を `docs/data/{date}_{hour}.json`（JST時刻付き。1配信スロット1ファイル）に書き出し・`index.json` を更新・`git commit & push` する |
| `scripts/remind.py` | FR-08：JST基準の前日日付で `docs/data/index.json` の `digests` に前日分のエントリが存在するか確認し、存在する場合のみDiscordへ簡易リマインド1通をPOSTする |
| `scripts/weekly_digest.py` | FR-09：`docs/data/index.json` からJST基準で直近7日分の `digests` エントリを抽出し、各 `file` キーが指す `docs/data/{file}.json` を集計して件数・カテゴリ内訳・`importance`上位5件をDiscord Embedで送信する |
| `docs/index.html` | GitHub Pagesで配信する静的サイト本体。SCR-01（月別折りたたみ一覧）・SCR-02（日次詳細・全文翻訳展開・既読管理）・SCR-03（キーワード検索・既読管理）をバニラJSで実装。既読状態は`localStorage`の`neura_read_articles`キーで管理する（FR-07）。markdownレンダリング・シンタックスハイライトもインライン実装（外部CDN不使用） |
| `docs/data/index.json` | 日付×時刻ごとのdigestメタ情報（`date`・`time`・`file`・`count`・`categories`・`titles`）を降順配列で保持。`archive.py` が毎回更新する。同一`(date, time)`は上書き、100件超は古い順に削除 |
| `docs/data/{YYYY-MM-DD}_{HH}.json` | 1配信スロット分の記事データ。`archive.py` が生成。GitHub Pagesから直接fetchされる |
| `requirements.txt` | `aiohttp`・`feedparser`・`trafilatura`・`google-genai`・`requests` のバージョン固定 |
| `.env.example` | 環境変数テンプレート。実際の値は入れずにGitにコミットする |

---

## 環境変数

```bash
# .env.example

# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here    # Gemini Flash API認証キー

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...    # DiscordチャンネルのWebhook URL

# GITHUB_TOKEN はGitHub Actionsが自動提供するため定義不要
```

### 環境変数の取得場所

| 環境変数 | 取得場所 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio（aistudio.google.com）→ 「Get API key」→ 「Create API key」 |
| `DISCORD_WEBHOOK_URL` | Discord → 対象チャンネル → チャンネル編集 → 「連携サービス」→「ウェブフック」→「新しいウェブフック」→「ウェブフックURLをコピー」 |

### GitHub Actionsシークレットへの登録方法

上記2つの環境変数はGitHub Actionsのシークレットとして登録する（`.env` ファイルは使用しない）。

```
GitHubリポジトリ → Settings → Secrets and variables → Actions → New repository secret
  - Name: GEMINI_API_KEY       / Secret: {取得したAPIキー}
  - Name: DISCORD_WEBHOOK_URL  / Secret: {取得したWebhook URL}
```

---

## GitHub Actions ワークフロー定義

### `daily.yml` の骨格

`schedule:` トリガーは持たない。cron-job.orgが `notify_schedules` の有効スロット数分、正確なJST時刻に `workflow_dispatch` を叩く方式。

```yaml
name: Neura Daily Digest

on:
  workflow_dispatch:   # cron-job.org から正確な時刻にトリガーする

jobs:
  daily-digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # git push のために必要
      actions: write         # Pages デプロイ失敗時の再実行トリガーに必要

    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Collect articles (FR-01)
        run: python scripts/collect.py

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

      - name: Retry Pages deployment if it fails
        continue-on-error: true
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Pages自動デプロイの一時的失敗を監視し、失敗時はrerunする（詳細は daily.yml 実物を参照）
```

### `remind.yml` の骨格（FR-08・新規）

cron-job.orgの固定ジョブ（毎日9:00 JST）から `workflow_dispatch` で起動する。`notify_schedules` の設定変更とは独立しており、設定画面での編集対象外。

```yaml
name: Neura Unread Reminder

on:
  workflow_dispatch:   # cron-job.org の固定ジョブ（毎日9:00 JST）からトリガーする

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Send unread reminder (FR-08)
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python scripts/remind.py
```

### `weekly.yml` の骨格（FR-09・新規）

cron-job.orgの固定ジョブ（毎週土曜12:00 JST）から `workflow_dispatch` で起動する。

```yaml
name: Neura Weekly Digest

on:
  workflow_dispatch:   # cron-job.org の固定ジョブ（毎週土曜12:00 JST）からトリガーする

jobs:
  weekly-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Send weekly digest (FR-09)
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python scripts/weekly_digest.py
```

> 3ワークフローとも `workflow_dispatch` のみを持つため、GitHubのActionsタブから手動実行してテストできる。
