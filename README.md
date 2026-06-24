# Neura — AI Daily Digest

> 毎日定刻に AI ニュースを自動収集・要約して Discord に通知し、GitHub Pages でアーカイブするシステム。月額費用ゼロで運用できる。

---

## 目次

- [概要](#概要)
- [機能](#機能)
- [技術スタック](#技術スタック)
- [セットアップ](#セットアップ)
- [使い方](#使い方)
- [ディレクトリ構成](#ディレクトリ構成)
- [環境変数](#環境変数)

---

## 概要

Neura は GitHub Actions を起点に、Hacker News・Reddit・各種 RSS フィード（8ソース）から AI 関連記事を毎日自動収集し、Gemini Flash API で日本語要約・カテゴリ分類を行って Discord に通知するシステムです。収集結果は GitHub Pages 上のアーカイブサイトにも自動保存されます。

ブラウザ上の設定画面（GitHub Contents API 連携）から収集ソース・キーワード・実行スケジュールをいつでも変更できます。

**アーカイブサイト：** `https://{GitHubユーザー名}.github.io/neura/`

---

## 機能

- **AIニュース収集**：Hacker News / Reddit / TechCrunch AI / MIT Technology Review AI / VentureBeat AI / Zenn / はてなブックマーク（8ソース）から AI 関連記事を並列取得
- **日本語要約・分類**：Gemini Flash API で日本語タイトル・要約・全文翻訳・カテゴリ（ニュース / 研究 / 活用事例 / ツール）・重要度を自動生成
- **Discord 通知**：毎日定刻に Webhook でダイジェストを配信。カテゴリバッジ・重要度付き
- **アーカイブサイト**：GitHub Pages で過去ダイジェストを日付別に閲覧可能。全文翻訳の展開表示・キーワード検索対応
- **ブラウザ設定画面**：GitHub Contents API 経由で収集ソース・キーワード・Gemini プロンプト・実行時刻を変更可能（PAT を localStorage に保存）

---

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| 言語 | Python 3.11 |
| 非同期 HTTP | aiohttp 3.9 |
| RSS 解析 | feedparser 6.0 |
| 本文抽出 | trafilatura 1.12.2 |
| AI 要約 | Gemini Flash API（`gemini-1.5-flash`、無料枠 1500 req/日） |
| スケジューラ | GitHub Actions（cron、無料枠 2000 分/月） |
| フロントエンド | バニラ HTML/CSS/JS（1 ファイル完結） |
| ホスティング | GitHub Pages（`docs/` フォルダを配信） |
| データ保存 | JSON ファイル（Git リポジトリ内） |

---

## セットアップ

### 前提条件

- Python 3.11 以上
- GitHub アカウント（パブリックリポジトリ + GitHub Pages が必要）
- Google アカウント（Gemini API キー取得用）
- Discord サーバーの管理者権限

### 1. リポジトリの準備

```bash
git clone https://github.com/{ユーザー名}/neura.git
cd neura
pip install -r requirements.txt
cp .env.example .env
# .env を編集して GEMINI_API_KEY・DISCORD_WEBHOOK_URL を記入する
```

### 2. 外部サービスの設定

| サービス | 手順 |
|---|---|
| **Gemini API キー** | [Google AI Studio](https://aistudio.google.com) → 「Get API key」→「Create API key」 |
| **Discord Webhook** | Discord チャンネル → チャンネル編集 → 「連携サービス」→「ウェブフックを作成」→ URL をコピー |
| **GitHub Pages** | Settings → Pages → Source: `main` / `/docs` |
| **GitHub Secrets** | Settings → Secrets → `GEMINI_API_KEY`・`DISCORD_WEBHOOK_URL` を登録 |
| **Workflow permissions** | Settings → Actions → General → 「Read and write permissions」 |
| **GitHub PAT** | Settings → Developer → Personal access tokens → scope: `repo` + `workflow` |

> 詳細な手順は [`design/neura_setup.md`](design/neura_setup.md) を参照してください。

### 3. 動作確認

```bash
# 収集スクリプト
python scripts/collect.py
# → /tmp/neura_collected.json が生成されれば OK

# 要約スクリプト（collect 実行後）
python scripts/summarize.py
# → /tmp/neura_summarized.json が生成されれば OK

# Discord 通知（summarize 実行後）
python scripts/notify.py
# → Discord に通知が届けば OK
```

GitHub Actions での本番実行：リポジトリの **Actions** タブ → 「Neura Daily Digest」→「Run workflow」

---

## 使い方

### アーカイブサイトの閲覧

`https://{ユーザー名}.github.io/neura/` を開くと、日付別のダイジェスト一覧が表示されます。

- 日付カードをクリック → その日の記事一覧（カテゴリ・重要度付き）
- 「全文翻訳」をクリック → 記事の日本語全文翻訳を展開表示
- キーワード入力 → 過去記事のフィルタリング

### 設定の変更

`https://{ユーザー名}.github.io/neura/?view=settings` を開き、GitHub の Owner / Repo / PAT を入力して設定画面にアクセスします。

- 収集ソースの有効 / 無効切り替え
- AIキーワードフィルタの編集
- Gemini プロンプトのカスタマイズ
- 実行時刻の変更（JST 0〜23 時）→ `daily.yml` の cron 式が自動更新される

---

## ディレクトリ構成

```
neura/
├── .github/
│   └── workflows/
│       └── daily.yml          # GitHub Actions cron 定義
├── config/
│   └── config.json            # 収集設定（設定画面から GitHub API で更新）
├── design/                    # 設計書
│   ├── neura_requirements.md
│   ├── neura_architecture.md
│   ├── neura_basic_design.md
│   ├── neura_detailed_design.md
│   ├── neura_setup.md
│   └── neura_business.md
├── docs/
│   ├── index.html             # アーカイブサイト＋設定画面（1 ファイル完結）
│   └── data/
│       ├── index.json         # 日付一覧
│       └── {YYYY-MM-DD}.json  # 日次記事データ
├── scripts/
│   ├── schemas.py             # 共通 TypedDict 型定義
│   ├── config_loader.py       # config.json 読み込み（デフォルト値フォールバック付き）
│   ├── collect.py             # 記事収集（並列 HTTP リクエスト）
│   ├── summarize.py           # Gemini Flash API による要約・分類
│   ├── notify.py              # Discord Webhook 通知
│   └── archive.py             # JSON 保存・git コミット
├── tests/                     # pytest テスト（22 件）
├── .env.example               # 環境変数テンプレート
├── requirements.txt
└── README.md
```

---

## 環境変数

`.env` に以下を設定してください（GitHub Actions では Secrets として登録）。

| 変数名 | 必須 | 説明 | 取得場所 |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | Gemini Flash API 認証キー | [Google AI Studio](https://aistudio.google.com) |
| `DISCORD_WEBHOOK_URL` | ✅ | Discord チャンネルの Webhook URL | Discord チャンネル設定 → 連携サービス |
| `GITHUB_TOKEN` | — | GitHub Actions が自動提供（定義不要） | — |

> `.env.example` にテンプレートがあります。PAT（設定画面用）は `.env` には記載せず、設定画面から入力して localStorage に保存します。
