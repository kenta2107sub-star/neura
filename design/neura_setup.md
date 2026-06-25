# セットアップガイド

> **プロジェクト名**：Neura
> **対象フェーズ**：Phase 1（MVP）のみ
> **このドキュメントの用途**：開発着手前の環境構築・各種サービスの設定手順をまとめたガイド。初回セットアップ時に上から順に実施する。
> **関連ドキュメント**：
> - `neura_requirements.md`（機能要件・非機能要件）
> - `neura_architecture.md`（技術スタック・システム構成・ディレクトリ構成・環境変数）
> - `neura_basic_design.md`（画面仕様・モック実装指示 ※セットアップ完了後に作成）

---

## ⚠️ 開発着手前チェックリスト

### 🔑 A. APIキー・認証情報の取得

| # | 確認項目 | 取得場所 | 環境変数名 | 完了 |
|---|---|---|---|---|
| A-1 | Gemini APIキーを取得済み | Google AI Studio（aistudio.google.com）→「Get API key」→「Create API key」 | `GEMINI_API_KEY` | [ ] |
| A-2 | Discord Webhook URLを取得済み | Discord → 対象チャンネル → チャンネル編集 → 「連携サービス」→「ウェブフック」→「新しいウェブフック」→「ウェブフックURLをコピー」 | `DISCORD_WEBHOOK_URL` | [ ] |

### 🎮 B. Discordサーバー・チャンネルの設定完了

| # | 確認項目 | 完了 |
|---|---|---|
| B-1 | Discordサーバーを新規作成済み | [ ] |
| B-2 | Neura通知用チャンネル（例：`#ai-news`）を作成済み | [ ] |
| B-3 | 対象チャンネルでWebhookを作成済み（A-2で取得） | [ ] |

> ⚠️ **B-3のWebhook作成が未完了だと、Discord通知（FR-03）が一切動作しない。**

### ☁️ C. GitHubリポジトリ・GitHub Pages・GitHub Actionsの設定完了

| # | 確認項目 | 完了 |
|---|---|---|
| C-1 | GitHubリポジトリ（`neura`）を新規作成済み | [ ] |
| C-2 | リポジトリの Settings → Pages → Source を「Deploy from a branch」・Branch `main` / `docs` フォルダに設定済み | [ ] |
| C-3 | リポジトリの Settings → Actions → General → Workflow permissions を「Read and write permissions」に設定済み（git pushのため） | [ ] |
| C-4 | `GEMINI_API_KEY` をGitHub Actionsシークレットに登録済み | [ ] |
| C-5 | `DISCORD_WEBHOOK_URL` をGitHub Actionsシークレットに登録済み | [ ] |

> ⚠️ **C-3の「Read and write permissions」が未設定だと、`archive.py` のgit pushが権限エラーで失敗し、アーカイブサイトが更新されない。**

> ⚠️ **C-4・C-5のシークレット未登録だと、GitHub Actions上でAPIキーが空になりGeminiとDiscordの両方が失敗する。**

### 🖥️ D. ローカル開発環境の準備

| # | 確認項目 | 完了 |
|---|---|---|
| D-1 | Python 3.11以上がインストール済み（`python --version` で確認） | [ ] |
| D-2 | リポジトリをクローン済み（`git clone` で確認） | [ ] |
| D-3 | `.env.example` をコピーして `.env` を作成済み | [ ] |
| D-4 | `.env` にA欄の全環境変数（`GEMINI_API_KEY`・`DISCORD_WEBHOOK_URL`）を記載済み | [ ] |
| D-5 | `pip install -r requirements.txt` が完了済み | [ ] |
| D-6 | `python scripts/collect.py` を実行してエラーなく記事リストが出力されることを確認済み | [ ] |

---

### ✅ 着手OKの条件

**上記 A〜D の全項目が完了してから、実装を開始すること。**

---

## 1. Gemini APIキーの取得手順

1. [Google AI Studio](https://aistudio.google.com) にGoogleアカウントでログインする
2. 左メニューの **「Get API key」** をクリックする
3. **「Create API key」** → プロジェクトを選択（または「Create API key in new project」）する
4. 生成されたAPIキーをコピーする → `GEMINI_API_KEY` として保存する

> ⚠️ APIキーはページを閉じると再表示できない場合がある。必ずコピー直後に安全な場所に保存すること。

**無料枠の確認：**
- 無料枠：`gemini-1.5-flash` は1500リクエスト/日・100万トークン/日まで無料
- Neuraは1日1リクエストのみなので無料枠を大幅に下回る

---

## 2. Discordサーバー・Webhook URLの設定手順

### 2-1. サーバーの新規作成

1. Discordを開き、左サイドバーの **「＋」（サーバーを追加）** をクリックする
2. **「オリジナルを作成」** → **「自分と友達のため」** を選択する
3. サーバー名（例：`Neura`）を入力して **「新規作成」** をクリックする

### 2-2. 通知チャンネルの作成

1. 左サイドバーの **「テキストチャンネル」** 横の **「＋」** をクリックする
2. チャンネル名を `ai-news` と入力して **「チャンネルを作成」** をクリックする

### 2-3. Webhook URLの取得

1. `#ai-news` チャンネルを右クリック → **「チャンネルの編集」** をクリックする
2. 左メニューの **「連携サービス」** → **「ウェブフックを作成」** をクリックする
3. Webhookの名前を `Neura Bot` に変更する（任意）
4. **「ウェブフックURLをコピー」** をクリックする → `DISCORD_WEBHOOK_URL` として保存する

---

## 3. GitHubリポジトリ・GitHub Pages・シークレットの設定手順

### 3-1. リポジトリの作成

1. [GitHub](https://github.com/new) で新規リポジトリを作成する
   - Repository name：`neura`
   - Visibility：`Private`（個人利用のため）
   - 「Add a README file」にチェックを入れる
2. **「Create repository」** をクリックする

### 3-2. GitHub Pages の設定

1. リポジトリの **Settings** タブをクリックする
2. 左メニューの **「Pages」** をクリックする
3. **Source** を **「Deploy from a branch」** に設定する
4. **Branch** を **`main`** / フォルダを **`/docs`** に設定する
5. **「Save」** をクリックする

> 設定後、数分でサイトURLが `https://{GitHubユーザー名}.github.io/neura/` として発行される。

### 3-3. Workflow permissions の設定

1. リポジトリの **Settings** → 左メニューの **「Actions」** → **「General」** をクリックする
2. **「Workflow permissions」** セクションで **「Read and write permissions」** を選択する
3. **「Save」** をクリックする

### 3-4. シークレットの登録

1. リポジトリの **Settings** → **「Secrets and variables」** → **「Actions」** をクリックする
2. **「New repository secret」** をクリックして以下を登録する：

| Name | Secret |
|---|---|
| `GEMINI_API_KEY` | 手順1で取得したGemini APIキー |
| `DISCORD_WEBHOOK_URL` | 手順2で取得したDiscord Webhook URL |

### 3-5. GitHub PAT の発行（設定画面用 / FR-06）

設定画面（SCR-04）から収集設定（ジャンル・ソース・キーワード・Geminiプロンプト）を編集・保存するために、GitHub Personal Access Token（PAT）を発行する。**Secretsには登録せず、設定画面で入力してブラウザの localStorage に保存する。**

1. [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) を開く
2. **Tokens (classic)** → **「Generate new token (classic)」** をクリックする
   - Note：`neura-settings`
   - Expiration：**No expiration**（無期限。失効時は再発行する）
   - Select scopes：**`repo`** にチェック（Contents の読み書きに必要）、**`workflow`** にチェック（`.github/workflows/daily.yml` の更新に必要）
3. **「Generate token」** をクリックし、表示された `ghp_...` をコピーする（再表示されないため必ず控える）
4. 公開サイトの設定画面（`https://{ユーザー名}.github.io/neura/?view=settings`）を開き、Owner / Repo / PAT を入力して保存する

> ⚠️ PATはGitHubリポジトリのコード（`index.html` 等）には絶対に書き込まない。設定画面からの入力のみとする。
> ⚠️ 紛失・漏洩時は GitHub の Personal access tokens 画面から該当トークンを **Revoke** して再発行する。

---

## 4. ローカル開発・動作確認手順

```bash
# 1. リポジトリのクローン
git clone https://github.com/<your-account>/neura.git
cd neura

# 2. 依存パッケージのインストール
pip install -r requirements.txt

# 3. 環境変数の設定
cp .env.example .env
# .env をエディタで開き、以下を記入する：
#   GEMINI_API_KEY=<取得したAPIキー>
#   DISCORD_WEBHOOK_URL=<取得したWebhook URL>

# 4. 収集スクリプトの単体確認
python scripts/collect.py
# → [INFO] ログが表示され、/tmp/neura_collected.json が生成されればOK
cat /tmp/neura_collected.json | python -m json.tool | head -40
# → title・url・source・score・published_at・body_text を含む記事リストが確認できればOK

# 5. 要約スクリプトの単体確認（手順4の後に実行）
python scripts/summarize.py
# → [INFO] ログが表示され、/tmp/neura_summarized.json が生成されればOK
cat /tmp/neura_summarized.json | python -m json.tool
# → title_ja・summary_ja・translation_ja・category・importance を含むJSON（最大15件）が確認できればOK

# 6. Discord通知の単体確認（手順5の後に実行）
python scripts/notify.py
# → Discordの #ai-news チャンネルに「🧠 Neura Daily」メッセージが届けばOK

# 7. アーカイブの単体確認（手順5の後に実行）
python scripts/archive.py
# → docs/data/{today}.json と docs/data/index.json が生成されればOK
ls docs/data/

# 8. GitHub Actions の手動実行テスト
# GitHubリポジトリ → Actions タブ → 「Neura Daily Digest」→「Run workflow」
# → 全ステップがグリーンになればOK（Notify Discordがyellow/スキップでもarchiveが緑ならOK）
```

### 動作確認チェック

| # | 対応FR | 確認内容 | 期待結果 |
|---|---|---|---|
| 1 | FR-01 | `python scripts/collect.py` を実行する | `[INFO]` ログが出力され、`/tmp/neura_collected.json` が生成される。各記事に `title`・`url`・`source`・`score`・`published_at`・`body_text` が含まれる |
| 2 | FR-01（異常系） | ネットワークを切断した状態で `python scripts/collect.py` を実行する | `[WARN] {ソース名} timeout` のログが出力され、取得できたソースの記事のみで処理が続行される |
| 3 | FR-01（異常系） | 全ソースがタイムアウトする状況を再現する（ネットワーク完全遮断） | `[ERROR]` ログが出力されてスクリプトが終了する |
| 4 | FR-02 | `python scripts/summarize.py` を実行する（FR-01の出力が存在する状態） | `[INFO]` ログが出力され、`/tmp/neura_summarized.json` が生成される。各記事に `title_ja`・`summary_ja`・`translation_ja`・`category`・`importance` が含まれる |
| 5 | FR-02（異常系） | `GEMINI_API_KEY` を空にして `python scripts/summarize.py` を実行する | `[ERROR] GEMINI_API_KEY is not set` がログ出力されてスクリプトが終了する |
| 6 | FR-03 | `python scripts/notify.py` を実行する（FR-02の出力が存在する状態） | Discordの `#ai-news` チャンネルに `🧠 Neura Daily — {今日の日付}（{件数}件）` のメッセージが届く。各記事にカテゴリバッジ・タイトル・要約・URLリンクが含まれる |
| 7 | FR-03（異常系） | `DISCORD_WEBHOOK_URL` を空にして `python scripts/notify.py` を実行する | `[ERROR] DISCORD_WEBHOOK_URL is not set` がログ出力されてスクリプトが終了する |
| 8 | FR-04 | `python scripts/archive.py` を実行する（FR-02の出力が存在する状態） | `docs/data/{today}.json` が新規作成され、`docs/data/index.json` に今日の日付が追加される |
| 9 | FR-05（正常系） | `docs/index.html` をブラウザで開く（またはGitHub Pages URLにアクセスする） | ホーム画面（SCR-01）に日付カード一覧が表示される |
| 10 | FR-05（正常系） | SCR-01の日付カードをクリックする | 日次詳細画面（SCR-02）に切り替わり、その日の記事一覧がカード形式で表示される |
| 11 | FR-05（異常系） | URLパラメータに存在しない日付（例：`?date=2000-01-01`）を指定してアクセスする | 「指定した日付のデータが見つかりません。」と表示される |
| 12 | GitHub Actions | GitHubリポジトリ → Actions → 「Neura Daily Digest」→「Run workflow」で手動実行する | 全ステップがグリーンになり、Discordに通知が届き、`docs/data/` に新しいJSONファイルがコミットされる |
