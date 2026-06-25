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
| AI要約・翻訳 | google-generativeai | 0.7 | Gemini Flash（gemini-1.5-flash）の無料枠（1500 req/日）を使用。日本語要約・全文翻訳・カテゴリ分類・重要度スコアリングを1リクエストで処理 |
| Discord通知 | requests | 2.31 | Discord Webhook へのPOSTのみ。asyncio不要の単純なHTTPリクエストなのでrequestsで十分 |
| スケジューラ | GitHub Actions | - | cron `0 4 * * *`（毎日04:00 UTC = 13:00 JST）。無料枠2000分/月で1回5分以内の実行なら余裕で収まる |
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
[GitHub Actions] cron: 0 4 * * * （毎日13:00 JST）
        |
        ↓ trigger
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
                        ↓ 全ソース結果をマージ・AIキーワードフィルタ・重複排除・上位30件
[summarize.py：AI要約・分類]
        |
        └──→ Gemini Flash API（google-generativeai）
              gemini-1.5-flash / 1リクエストで要約・カテゴリ・重要度を生成
                        |
                        ↓ 最終記事オブジェクト（スロットフィルタ後 1〜10件）
        ┌───────────────┴───────────────┐
        ↓                               ↓
[notify.py]                      [archive.py]
Discord Webhook POST              docs/data/{YYYY-MM-DD}.json 生成
（requests）                      docs/data/index.json 更新
        |                               |
        ↓                               ↓ git commit & push（GITHUB_TOKEN）
[Discordチャンネル]              [GitHubリポジトリ docs/]
                                        |
                                        ↓ GitHub Pages 自動配信
                                 [docs/index.html]
                                 ブラウザでアーカイブ閲覧
```

### 処理の補足

| 処理 | 使用API / ライブラリ | 認証方式 |
|---|---|---|
| HN記事取得 | Firebase REST API（`GET topstories.json` → 各 `GET {id}.json`） | 不要 |
| Reddit記事取得 | Reddit RSS（`GET /r/{sub}/top/.rss?t=day` → feedparser） | 不要（browser風User-Agent必須。.jsonはBotブロック） |
| RSS取得 | `feedparser.parse(url)` | 不要 |
| Zenn RSS取得 | `feedparser.parse(url)` | 不要 |
| はてブ取得 | `GET https://b.hatena.ne.jp/hotentry/it.rss`（feedparser・hatena:bookmarkcount） | 不要 |
| Gemini API呼び出し | `genai.GenerativeModel('gemini-1.5-flash').generate_content()` | `GEMINI_API_KEY`（環境変数） |
| Discord通知 | `requests.post(DISCORD_WEBHOOK_URL, json=payload)` | `DISCORD_WEBHOOK_URL`（環境変数） |
| GitHubコミット | `git add / commit / push`（GitHub Actions内） | `GITHUB_TOKEN`（Actions自動提供） |
| 設定読み込み（FR-06） | `config_loader.load_config()`（ローカルの `config/config.json` を読む） | 不要（チェックアウト済みファイル） |
| 設定更新（FR-06） | ブラウザから `GET/PUT https://api.github.com/repos/{owner}/{repo}/contents/config/config.json` | GitHub PAT（`localStorage` に保存。`repo` スコープ） |

---

## ディレクトリ構成

```
neura/                                    ← プロジェクトルート
├── .github/
│   └── workflows/
│       └── daily.yml                     # GitHub Actions cron定義・全スクリプトを順番に呼び出す
├── config/
│   └── config.json                       # FR-06：収集設定（ジャンル・ソース・キーワード・Geminiプロンプト）。デフォルト値を同梱し、設定画面から GitHub API で更新する
├── scripts/
│   ├── schemas.py                        # Python TypedDict共通型定義（AppConfig・CollectedArticle・Article・DailyDigest・DigestIndex）※標準ライブラリ types との衝突回避のため types.py としない
│   ├── config_loader.py                  # FR-06：config/config.json を読み込む。不在/破損時はデフォルト値を返す。collect.py・summarize.py から使用
│   ├── collect.py                        # FR-01：config の sources/keywords を読み、全ソースから並列取得・フィルタ・重複排除
│   ├── summarize.py                      # FR-02：config の gemini_prompt/genres を読み、Gemini Flash APIで日本語要約・カテゴリ分類・ジャンル絞込み
│   ├── notify.py                         # FR-03：Discord Webhookでサマリー送信
│   └── archive.py                        # FR-04：JSONファイル生成・index.json更新・gitコミット
├── docs/
│   ├── index.html                        # FR-05/FR-06：GitHub Pagesで配信するアーカイブサイト＋設定画面（1ファイル完結）
│   └── data/
│       ├── index.json                    # 日付一覧（降順・最新100件）
│       └── {YYYY-MM-DD}.json            # 日次記事データ（Actions実行ごとに自動生成）
├── requirements.txt                      # Python依存パッケージ一覧
├── .env.example                          # 環境変数テンプレート（コミット対象）
└── README.md
```

### 各ファイルの責務

| ファイル | 責務 |
|---|---|
| `.github/workflows/daily.yml` | cronスケジュール定義。Python環境セットアップ・`collect.py`→`summarize.py`→`notify.py`→`archive.py` の順次実行・シークレット注入を担う |
| `config/config.json` | FR-06の収集設定。`genres`・`sources`・`keywords`・`gemini_prompt` を保持。リポジトリにデフォルト値を同梱する。設定画面（`docs/index.html`）が GitHub Contents API 経由で直接更新する |
| `scripts/schemas.py` | Python TypedDictによる共通型定義。`AppConfig`・`CollectedArticle`・`Article`・`DailyDigest`・`DigestIndex` を定義し、全スクリプトからimportして使用する。※ファイル名を `types.py` にすると標準ライブラリ `types` を `sys.path[0]` でシャドーイングし依存ライブラリが壊れるため `schemas.py` とする |
| `scripts/config_loader.py` | `config/config.json` を読み込み `AppConfig` を返す。ファイル不在・JSONパース失敗時はデフォルト値を返す（`[WARN]` ログ）。`collect.py`・`summarize.py` から使用する |
| `scripts/collect.py` | `config_loader` で設定を読み、`sources`（有効なもののみ・`type`でパーサ振分け）・`keywords` に従って全ソースへ並列HTTPリクエスト・AIキーワードフィルタ・重複URL排除・上位30件の選定・`trafilatura` による本文テキスト取得。結果を `/tmp/neura_collected.json` に書き出して次スクリプトに渡す |
| `scripts/summarize.py` | `collect.py` の出力を受け取り、`config.gemini_prompt` を使って Gemini Flash APIに1リクエストで要約・全文翻訳（`translation_ja`）・カテゴリ・重要度を生成させる。`config.genres` で無効なカテゴリを除外してから重要度上位を選定する。JSONパース失敗時は即終了 |
| `scripts/notify.py` | `summarize.py` の出力をDiscord Embed形式に変換してWebhook POSTする。エラー時はログ出力のみ |
| `scripts/archive.py` | `summarize.py` の出力を `docs/data/{date}.json` に書き出し・`index.json` を更新・`git commit & push` する |
| `docs/index.html` | GitHub Pagesで配信する静的サイト本体。SCR-01（月別折りたたみ一覧）・SCR-02（日次詳細・全文翻訳展開）・SCR-03（キーワード検索）をバニラJSで実装。markdownレンダリング・シンタックスハイライトもインライン実装（外部CDN不使用） |
| `docs/data/index.json` | 存在する日次JSONの日付を降順配列で保持。`archive.py` が毎回更新する。100件超は古い順に削除 |
| `docs/data/{YYYY-MM-DD}.json` | 日次記事データ。`archive.py` が生成。GitHub Pagesから直接fetchされる |
| `requirements.txt` | `aiohttp`・`feedparser`・`trafilatura`・`google-generativeai`・`requests` のバージョン固定 |
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

## GitHub Actions ワークフロー定義（`daily.yml` の骨格）

```yaml
name: Neura Daily Digest

on:
  schedule:
    - cron: '0 4 * * *'    # 毎日04:00 UTC = 13:00 JST
  workflow_dispatch:         # 手動実行も可能（テスト用）

jobs:
  daily-digest:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # git push のために必要

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Collect articles
        run: python scripts/collect.py

      - name: Summarize with Gemini
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python scripts/summarize.py

      - name: Notify Discord
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python scripts/notify.py

      - name: Archive to GitHub Pages
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/archive.py
```

> `workflow_dispatch` を追加することで、GitHubのActionsタブから手動実行してテストできる。
