# 要件定義書

> **プロジェクト名**：Neura
> **対象フェーズ**：Phase 1（MVP）のみ
> **このドキュメントの用途**：Claude Codeでの実装・basic_design.md作成に使用する。機能要件・非機能要件のみを記載している。
> **関連ドキュメント**：
> - `neura_architecture.md`（技術スタック・システム構成・ディレクトリ構成・環境変数）
> - `neura_setup.md`（開発着手前チェックリスト・各種設定手順）
> - `neura_basic_design.md`（画面仕様・モック実装指示 ※このファイルの後に作成）

---

## サービス概要

設定した時刻（JST・1日最大3回）にAIニュース・活用事例を自動収集・要約し、Discordへ通知するとともに、GitHub Pages上のWebサイトにアーカイブとして蓄積・閲覧できるシステム。月額費用ゼロで運用する。

---

## 作らないこと（Phase 1）

> このセクションに記載された機能・仕様はPhase 1では**実装しない**。
> Claude Codeはこのリストにある内容をコードに含めないこと。
> → basic_design.md Section 0「モックで実装しないこと」にも転記すること。

### 後フェーズに延期
- X（Twitter）検索：Twitter API v2の有料化のため除外。Phase 2以降で検討
- YouTube動画要約：実装コスト高。Phase 2以降で検討
- カテゴリフィルタ・タグ検索：Phase 2で実装予定
- メール通知：Phase 2以降で検討

### 意図的に永久除外
- ユーザー認証・ログイン機能：個人利用のためURLを知っていれば閲覧可能とする
- 記事への手動コメント・編集機能：自動収集のみとする

### 技術的制約による除外
- リアルタイム更新（1日1回バッチのみ）：GitHub Actionsのcronスケジュールによる制約
- 全文検索：静的サイトのためサーバー側検索は未実装。クライアント側JS検索（SCR-03）で代替

### 前提条件の欠如による除外
- 有料APIの利用：月額費用ゼロ制約のため

---

## 機能要件

### FR-01：AIニュース収集

#### 概要（1行）
Hacker News API・Reddit/はてブ/各種RSSフィードからAI関連記事を並列取得する（Reddit・はてブはBotブロック/API非提供のためRSSを使用）。

#### 対応するインターフェース
GitHub Actions のcronジョブ（`notify_schedules` の `enabled: true` なスロットが実行時刻になったときに起動。1日最大3回まで設定可能）

#### 入力
- トリガー：GitHub Actions の `schedule` イベント（`notify_schedules` の有効スロット数分の cron エントリが生成される。例：`'0 4 * * *'` で13:00 JST）
- 入力データなし（パラメータは固定）

#### 収集対象ソース

**🌍 海外ソース**

| ソース | 取得方法 | 取得件数上限 | 認証 |
|---|---|---|---|
| Hacker News | `https://hacker-news.firebaseio.com/v0/topstories.json` → 上位100件取得後フィルタ | 上位100件をフィルタ対象 | 不要 |
| Reddit `/r/artificial` | RSS `https://www.reddit.com/r/artificial/top/.rss?t=day` | 最新25件 | 不要（User-Agent設定必須。`.json` はBotブロックされるためRSSを使用） |
| Reddit `/r/MachineLearning` | RSS `https://www.reddit.com/r/MachineLearning/top/.rss?t=day` | 最新25件 | 不要（同上） |
| RSS（TechCrunch AI） | `https://techcrunch.com/category/artificial-intelligence/feed/` | 最新20件 | 不要 |
| RSS（MIT Technology Review AI） | `https://www.technologyreview.com/topic/artificial-intelligence/feed` | 最新20件 | 不要 |
| RSS（VentureBeat AI） | `https://venturebeat.com/category/ai/feed/` | 最新20件 | 不要 |

**🇯🇵 日本語ソース**

| ソース | 取得方法 | 取得件数上限 | 認証 |
|---|---|---|---|
| Zenn（`ai` タグ） | RSS `https://zenn.dev/topics/ai/feed` | 最新20件 | 不要 |
| Qiita AI | RSS `https://qiita.com/tags/ai/feed` | 最新20件 | 不要（`zenn` typeと同じパーサ使用。AIタグフィードのためキーワードフィルタ不要） |
| ITmedia AI+ | RSS `https://rss.itmedia.co.jp/rss/2.0/aiplus.xml` | 最新20件 | 不要 |
| はてなブックマーク（テクノロジー） | RSS `https://b.hatena.ne.jp/hotentry/it.rss` → AIキーワードフィルタ（`.json` は存在せず302のためRSSを使用。`hatena:bookmarkcount` でブクマ数取得） | 上位30件をフィルタ対象 | 不要 |

#### 処理フロー
1. 全ソースに対して並列でHTTPリクエストを送信する（`asyncio` + `aiohttp` を使用）
2. 各ソースのレスポンスをパースし、記事リストを生成する
   - HN：`title`・`url`・`score`・`time` を取得。`url` が `None`（Ask HN等）の場合はスキップ
   - Reddit：RSS（Atom）を feedparser で解析。`title`・`link`・`published` を取得（スコアは取得不可のため0扱い・日付系ランキング）
   - RSS（TechCrunch等・Zenn）：`title`・`link`・`published` を取得
   - はてなブックマーク：RSS（RDF）を feedparser で解析。`title`・`link`・`hatena:bookmarkcount`・`published` を取得
3. 全記事に対してAIキーワードフィルタリングを行う
   - 海外ソース通過条件：`title` に以下のいずれかを含む（大文字小文字無視）
     - キーワード：`ai`, `llm`, `gpt`, `claude`, `gemini`, `openai`, `anthropic`, `machine learning`, `deep learning`, `neural`, `chatbot`, `agent`, `generative`
   - Zennは `ai` タグフィード自体がAI記事のみなのでフィルタ不要
   - はてなブックマーク通過条件：`title` に以下のいずれかを含む（日英両対応）
     - キーワード：`AI`, `LLM`, `GPT`, `Claude`, `Gemini`, `OpenAI`, `Anthropic`, `機械学習`, `生成AI`, `チャットボット`, `エージェント`
     - かつ `hatena:bookmarkcount >= 20`（低品質記事を除外。collect.py の fetch_hatena 内で適用）
4. 重複URL排除（URLの末尾スラッシュ・クエリパラメータを除去して正規化した上で、同一URLの初出のみ残す）
5. スコア系ソース（HN・はてブ）はスコア降順にソートして上位20件を選定し、日付系ソース（Reddit・RSS・Zenn）は公開日時降順にソートして上位10件を選定する（RedditはRSS化によりスコア無しのため日付系）
6. 上位合計30件（海外20件・日本語10件の目安）をマージして次の処理に渡す
7. 上位30件の各記事URLに対してHTTPリクエストを送信し、`trafilatura` ライブラリで本文テキストを抽出する
   - 取得成功：`body_text` フィールドに本文テキスト（最大5000文字）を格納する
   - タイムアウト（10秒）またはアクセスブロック（403等）：`body_text: null` として続行する（このソースをスキップしない）
8. `body_text` 付きの記事リストを次のFR-02に渡す

#### 出力（正常系）
```python
# 記事オブジェクトのリスト（最大30件）
[
  {
    "title": "OpenAI releases GPT-5",
    "url": "https://example.com/article",
    "source": "HackerNews",  # "HackerNews" | "Reddit" | "RSS" | "Zenn" | "HatenaBookmark"
    "score": 1523,           # HN/Redditはスコア、RSSは0固定
    "published_at": "2026-06-18T04:00:00Z",  # ISO 8601 UTC
    "body_text": "Full article body text..."  # 本文テキスト。取得失敗時はnull
  },
  ...
]
```

#### 出力（異常系）
- 特定ソースがタイムアウト（10秒）した場合：そのソースをスキップしてログに `[WARN] {ソース名} timeout` を記録し、他ソースで処理を続行する
- 全ソースが失敗した場合：`[ERROR] All sources failed` をログに記録して処理を終了する（GitHub Actionsのワークフロー失敗通知で検知する）

#### 依存関係
- このFRに依存するFR：FR-02（収集結果を入力として使用）
- このFRが依存するFR：FR-06（`config.json` の `sources`・`keywords` を読み込む。未設定時はデフォルト値で動作する）

---

### FR-02：AI要約・分類

#### 概要（1行）
FR-01で収集した記事をGemini Flash API（`gemini-2.5-flash`）で日本語要約し、実行スロットの `max_articles`（1〜10件、デフォルト10）に厳選・カテゴリ付けする。

#### 対応するインターフェース
GitHub Actions のcronジョブ（FR-01の直後に実行）

#### 入力
- FR-01の出力（記事リスト、最大30件。各記事に `body_text` フィールドあり）

#### 処理フロー
1. 記事リスト全件のタイトル・本文（`body_text`）をプロンプトに含め、Gemini Flash API（`gemini-1.5-flash`）に1回のリクエストで送信する
2. プロンプト内容：
   ```
   以下のAI関連記事から、最も重要・興味深い最大15件を選び、
   各記事について以下の形式でJSON配列を返してください：
   - url: 元記事のURLをそのまま返す（変更禁止。後工程のURL照合に使用する）
   - title_ja: 日本語タイトル（30文字以内。元が日本語の場合はそのまま使用）
   - summary_ja: 日本語要約（150文字以内）
   - translation_ja: 記事本文の全文日本語翻訳（markdown形式）
                     - コードブロックは ```言語名 で囲んでそのまま保持（翻訳しない）
                     - インラインコード（関数名・変数名・ライブラリ名）は `backtick` で囲んでそのまま保持
                     - 見出しは ## / ### で構造を維持する
                     - 箇条書きは - で保持する
                     - 重要ワードは **太字** で保持する
                     - URLリンクは除去してプレーンテキストにする
                     - body_textがnullの場合はnullを返す
   - category: "ニュース" | "研究" | "活用事例" | "ツール" のいずれか
   - importance: 1〜5の整数（5が最重要）
   海外・日本語の両ソースからバランスよく選んでください。
   記事一覧: {タイトル・URL・ソース名・body_textのリスト}
   ```
3. Gemini APIのレスポンスをJSONとしてパースする
   - パース失敗時：リトライなし。`[ERROR] Failed to parse Gemini response` をログに記録して終了する（GitHub Actionsのワークフロー失敗通知で検知する）
4. パース成功時：Gemini が同じ URL を重複返却した場合は URL 正規化後に先着1件を残して重複除去する
5. `importance` 降順でソートし、実行スロットの `max_articles` 件（スロット未設定時は10）を選択する
5. 元の記事URLと対応付けて最終記事オブジェクトを生成する

#### 出力（正常系）
```python
# 最終記事オブジェクトのリスト（スロットのmax_articles設定による 1〜10件）
[
  {
    "title_ja": "OpenAI、GPT-5を正式リリース",
    "summary_ja": "OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...",
    "translation_ja": "## OpenAI、GPT-5を正式リリース\n\nOpenAIは本日...\n\n```python\nclient.chat...\n```",
    "category": "ニュース",
    "importance": 5,
    "url": "https://example.com/article",
    "source": "HackerNews",
    "published_at": "2026-06-18T04:00:00Z"
  },
  {
    "title_ja": "Gemini Flash、画像理解が向上",
    "summary_ja": "...",
    "translation_ja": null,  // body_textがnullだった場合
    ...
  }
]
```

#### 出力（異常系）
```
[ERROR] Failed to parse Gemini response
（GitHub Actionsのワークフロー失敗として記録される）
```

#### 依存関係
- このFRに依存するFR：FR-03、FR-04
- このFRが依存するFR：FR-01、FR-06（`config.json` の `gemini_prompt`・実行スロットの `genres`・`max_articles` を読み込む。未設定時はデフォルト値で動作する）

---

### FR-03：Discord通知

#### 概要（1行）
FR-02の要約結果をDiscord Webhookでフォーマットして送信する。

#### 対応するインターフェース
Discord Webhook URL（環境変数 `DISCORD_WEBHOOK_URL`）

#### 入力
- FR-02の出力（最終記事オブジェクトのリスト）

#### 処理フロー
1. Discord Embed形式のメッセージを構築する
   - ヘッダー：`🧠 Neura Daily — {YYYY/MM/DD}（{件数}件）`
   - 各記事をEmbed fieldとして追加：`[カテゴリバッジ] タイトル` + 要約 + URLリンク
   - カテゴリバッジ：`ニュース`→🗞️、`研究`→🔬、`活用事例`→💡、`ツール`→🛠️
   - フッター：`Neura by GitHub Actions`
2. `DISCORD_WEBHOOK_URL` に対してPOSTリクエストを送信する（`requests` ライブラリ使用）
3. HTTPステータス `204` を正常とする
   - `204` 以外の場合：ログに `[ERROR] Discord webhook failed: {status_code}` を記録して終了（リトライなし）

#### 出力（正常系）
```
Discordチャンネルに以下が投稿される：

🧠 Neura Daily — 2026/06/18（7件）

🗞️ OpenAI、GPT-5を正式リリース
OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...
[HackerNews] → https://example.com/article

💡 ZennでClaude APIを使った業務自動化ツールを作った
請求書処理をAIで自動化した実装例。コスト削減効果も検証...
[Zenn 🇯🇵] → https://zenn.dev/example

🔬 Transformerの新アーキテクチャ、推論速度3倍に
...
```

#### 出力（異常系）
- Webhook URLが未設定（`DISCORD_WEBHOOK_URL` が空）：`[ERROR] DISCORD_WEBHOOK_URL is not set` をログ出力して終了
- HTTPステータスが204以外：`[ERROR] Discord webhook failed: {status_code}` をログ出力して終了

#### 依存関係
- このFRに依存するFR：なし
- このFRが依存するFR：FR-02

---

### FR-04：JSONアーカイブ保存

#### 概要（1行）
FR-02の要約結果をJSON形式でGitHubリポジトリにコミットし、Webサイト用のデータとして蓄積する。

#### 対応するインターフェース
GitHub Actions（`GITHUB_TOKEN` を使用してリポジトリにコミット）

#### 入力
- FR-02の出力（最終記事オブジェクトのリスト）

#### 処理フロー
1. 本日付のJSONファイルを生成する
   - ファイルパス：`docs/data/{YYYY-MM-DD}.json`
   - JSONの構造：
     ```json
     {
       "date": "2026-06-18",
       "generated_at": "2026-06-18T04:00:00Z",
       "articles": [ ...FR-02の出力... ]
     }
     ```
2. インデックスファイル `docs/data/index.json` を更新する
   - 形式：`{ "digests": [{ "date": "2026-06-18", "count": 7, "categories": {"ニュース":3,...} }, ...] }`（`digests` キーに各日付のメタ情報を降順配列で持つ。最新100件まで保持）
   - 各エントリは日次データから記事件数（`count`）とカテゴリ別件数（`categories`）を集計して生成する
   - 同一日付の既存エントリは除去してから先頭に追加する（再実行時の重複防止）
3. `git add docs/data/ && git commit -m "chore: add daily digest {YYYY-MM-DD}" && git push` を実行する
   - GitHub Actionsの `GITHUB_TOKEN` を使用する
   - コミット失敗時：ログに `[ERROR] Git commit failed` を記録する（Discordへの通知はしない）

#### 出力（正常系）
```
docs/data/2026-06-18.json（新規作成）
docs/data/index.json（更新）
がGitHubリポジトリにコミットされる
```

#### 出力（異常系）
```
[ERROR] Git commit failed: {エラー内容}
```

#### 依存関係
- このFRに依存するFR：FR-05（保存したJSONをサイトが読み込む）
- このFRが依存するFR：FR-02

---

### FR-05：Webサイト閲覧（アーカイブ）

#### 概要（1行）
GitHub Pages上の静的サイトでFR-04が保存したJSONを読み込み、過去の日次ダイジェストを一覧・詳細表示する。

#### 対応する画面
- `SCR-01`：ホーム（日付一覧）
- `SCR-02`：日次詳細（選択した日の記事一覧）
- `SCR-03`：検索結果（キーワードで全日付をまたいで検索）

#### 入力
- ユーザーのブラウザアクセス（認証なし）
- `docs/data/index.json`（日付一覧）
- `docs/data/{YYYY-MM-DD}.json`（日次記事データ）

#### 処理フロー（SCR-01：ホーム）
1. ページロード時に `docs/data/index.json` をfetchする
2. `digests` を月別にグループ化し、月ヘッダー＋日付カード形式で表示する（最新月を自動展開）
3. 各カードに日付・曜日・記事件数（`count`）・カテゴリ分布バー（`categories`）を表示する（index.json 1回のfetchで完結）
4. カードクリックで `?date={YYYY-MM-DD}` のURLパラメータを付けて同ページ内でSCR-02に切り替える

#### 処理フロー（SCR-02：日次詳細）
1. URLパラメータ `date` の値で `docs/data/{date}.json` をfetchする
2. 記事を `importance` 降順で表示する
3. 各記事カードに以下を表示する：カテゴリバッジ・重要度ドット・日本語タイトル・日本語要約・ソース名・全文翻訳ボタン・元記事リンク
4. 「▼ 全文翻訳を見る」ボタンをクリックするとカード内に `translation_ja` をmarkdownレンダリングして展開する
   - `translation_ja` が `null` の場合は「⚠️ この記事の翻訳を取得できませんでした」を表示する
   - コードブロックはシンタックスハイライト付きで表示する
5. 「← 一覧に戻る」ボタンでSCR-01に戻る

#### 処理フロー（SCR-03：検索結果）
1. SCR-01の検索入力欄にキーワードを入力してEnterを押すと `?q=キーワード` のURLパラメータで遷移する
2. `docs/data/index.json` の `digests[].date` を列挙し、すべての日次JSONファイルをfetchして全記事をメモリに読み込む
3. キーワードで `title_ja`・`summary_ja`・`category`・`source` を対象に部分一致検索する（スペース区切りでAND検索）
4. 結果を日付降順で表示する。各記事カードに日付ラベルを付与する
5. 一致したキーワード箇所をハイライト（紫色）表示する
6. 全文翻訳ボタンはSCR-02と同様に動作する
7. 「← 一覧に戻る」ボタンでSCR-01に戻る

#### 表示例（正常系）
```
SCR-01（ホーム）:
  ┌─────────────────────────┐
  │ 🧠 Neura                │
  │ AI Daily Digest         │
  ├─────────────────────────┤
  │ 2026/06/18（水）7件     │
  │ 2026/06/17（火）8件     │
  │ 2026/06/16（月）5件     │
  └─────────────────────────┘

SCR-02（日次詳細）:
  ← 一覧に戻る
  2026/06/18（水）のAIニュース

  🗞️ ニュース
  OpenAI、GPT-5を正式リリース
  OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上...
  [HackerNews] → 元記事を読む
```

#### 表示例（異常系）
- `index.json` の取得失敗：`データの読み込みに失敗しました。しばらく後に再試行してください。` を表示
- 存在しない日付（`?date=` が不正）：`指定した日付のデータが見つかりません。` を表示
- 当日13時前（まだJSONが生成されていない）：上記と同じエラーメッセージを表示

#### 実装方針
- バニラHTML + CSS + JavaScript（フレームワークなし）で実装する
- `docs/index.html` 1ファイルで完結させる
- GitHub Pages の `docs/` フォルダをソースとして設定する

#### 依存関係
- このFRに依存するFR：なし
- このFRが依存するFR：FR-04

---

### FR-06：設定管理

#### 概要（1行）
ブラウザの設定画面からニュース収集設定（ジャンル・ソース・Geminiプロンプト・キーワードフィルタ・通知スケジュール×最大3件・通知件数上限）を編集し、GitHub Contents API 経由で `config/config.json` および `.github/workflows/daily.yml` をリポジトリに直接コミットする。

#### 対応する画面
- `SCR-04`：設定画面

#### 入力
- ユーザーが設定画面で入力した設定値
- `localStorage` に保存されたGitHub PAT（`neura_github_pat`）
- `config/config.json`（現在の設定値を画面初期表示時に読み込む）

#### 処理フロー

**初回セットアップ（PAT未設定時）**
1. 設定画面を開くと「GitHub PAT が未設定です」の警告バナーを表示する
2. PAT入力欄（`type="password"`）に入力して「保存」を押すと `localStorage.setItem('neura_github_pat', value)` で保存する
3. 保存後、GitHub Contents API で `config/config.json` を取得して設定値を各フォームに反映する

**設定の読み込み（PAT設定済み時）**
1. 設定画面を開くと `GET https://api.github.com/repos/{owner}/{repo}/contents/config/config.json` を fetch する
   - Authorization ヘッダーに `Bearer {PAT}` を付与する
2. レスポンスの `content`（Base64）をデコードしてJSONパースする
3. 各フォームに値を反映する

**設定の保存**
1. 「保存」ボタンを押すと `config/config.json` の現在の `sha` を取得する
2. 編集後の設定値をJSON文字列化してBase64エンコードする
3. `PUT https://api.github.com/repos/{owner}/{repo}/contents/config/config.json` を fetch する
   - リクエストボディ：`{ message: "chore: update config", content: {Base64}, sha: {現在のsha} }`
   - Authorization ヘッダーに `Bearer {PAT}` を付与する
4. `notify_schedules` が変更されていた場合、続けて `.github/workflows/daily.yml` の `on.schedule` ブロックを書き換える
   - `GET https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/daily.yml` で現在の内容と `sha` を取得する
   - `notify_schedules` の `enabled: true` なエントリのみを抽出し（1〜3件）、各エントリの `hour`（JST）を UTC に変換する（UTC = JST - 9、負の場合は +24）
   - ファイル内の `on:\n  schedule:\n` 以降のエントリ行を、有効なスケジュール数分の cron 行に置換する
     ```yaml
     # 例：13時・20時の2件が有効な場合
     on:
       schedule:
         - cron: '0 4 * * *'    # 13:00 JST
         - cron: '0 11 * * *'   # 20:00 JST
       workflow_dispatch:
     ```
   - `PUT` で更新する（コミットメッセージ：`chore: update notify schedules`）
   - 失敗時：ERR-13 を表示する（config.json の保存は成功済みのため別エラーとして扱う）
5. 全て成功時：「設定を保存しました」トーストを表示する
6. 失敗時：エラー内容に応じたメッセージを表示する（ERR-08〜ERR-13参照）

#### 出力（正常系）
- `config/config.json` がリポジトリに1コミット追加される
- `notify_schedules` が変更された場合は `.github/workflows/daily.yml` にも1コミット追加される（cronスケジュールが即座に変わる）
- 次回の定時実行から新しい設定が適用される

#### `config/config.json` の構造
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
  "gemini_prompt": "以下のAI関連記事から...\n{articles}\nJSON配列のみ返してください。",
  "notify_schedules": [
    { "hour": 13, "enabled": true,  "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true} },
    { "hour": 20, "enabled": false, "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true} },
    { "hour":  8, "enabled": false, "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true} }
  ]
}
```

> **`sources[].type` の許容値**：`"hackernews"` / `"reddit"` / `"rss"` / `"zenn"` / `"hatena"`。collect.py がこの値でパーサを振り分ける（FR-01参照）。設定画面からユーザーが追加できるソースは `type: "rss"`（汎用RSS/Atom）のみとする。`"zenn"` type は Qiita AI も含む（AIタグフィードのためキーワードフィルタをスキップする）。
> **`gemini_prompt` の `{articles}` プレースホルダー**：summarize.py が記事一覧テキストに置換する。このプレースホルダーは必須。プロンプトは設定UIには非公開で config.json 直接編集で変更する。`{articles}` 不在時は summarize.py がデフォルトプロンプトにフォールバックする（`[WARN]` ログ）。
> **`notify_schedules`**：通知スケジュールの配列（最大3件）。各エントリは `{ "hour": 0〜23（JST）, "enabled": true/false, "max_articles": 1〜10, "genres": {カテゴリ: bool} }` の形式。`enabled: true` のエントリが `.github/workflows/daily.yml` の cron エントリに対応する。少なくとも1件は `enabled: true` でなければならない（バリデーション：ERR-13参照）。
> **`notify_schedules[].max_articles`**：そのスロットで選出する記事の上限件数（1〜10の整数）。スロットごとに異なる件数を設定できる。デフォルトは10。
> **`notify_schedules[].genres`**：そのスロットで通知するカテゴリのON/OFFマップ。スロットごとに異なるジャンルフィルタを設定できる。
> **グローバルの `genres` / `max_articles` は廃止**：旧設定（`run_hour_jst`・グローバル `genres`・グローバル `max_articles`）が残っている場合は `config_loader.py` が自動マイグレーションしてスロット内に移行する。
> **GitHub接続情報（owner / repo / PAT）は config.json に含めない**：config.json 自体をGitHub APIで取得するために owner/repo/PAT が先に必要となる（鶏卵問題）ため、これらはブラウザの `localStorage` にのみ保存する（FR-06 セキュリティ・SCR-04参照）。

#### config.json が存在しない場合（フォールバック）
- collect.py / summarize.py は `config/config.json` が存在しない、またはパースに失敗した場合、上記のデフォルト値で動作する（`[WARN] config.json not found, using defaults` をログ出力）。
- リポジトリには初期状態で上記デフォルト値を持つ `config/config.json` を同梱する。

#### 依存関係
- このFRに依存するFR：FR-01（`sources`・`keywords` を読み込む）、FR-02（`gemini_prompt`・`genres` を読み込む）
- このFRが依存するFR：なし（独立して動作する）

---

## 非機能要件

### NF-01：処理時間
- GitHub Actions の1回あたりの実行時間は5分以内を目標とする
- 各ソースへのHTTPリクエストのタイムアウトは10秒とする
- Gemini APIへのリクエストのタイムアウトは30秒とする

### NF-02：セキュリティ・認証
- 認証方式：なし（個人利用のため）
- 環境変数として管理する情報（GitHub Actionsのシークレット）：
  - `GEMINI_API_KEY`（Gemini Flash API認証）→ architecture.mdの環境変数セクションに転記
  - `DISCORD_WEBHOOK_URL`（Discord Webhook URL）→ architecture.mdの環境変数セクションに転記
  - `GITHUB_TOKEN`（GitHub Actions自動提供、明示的な設定不要）
- ソースコードにAPIキー・Webhook URLをハードコードしない
- **FR-06（設定管理）固有のセキュリティ：**
  - GitHub PAT（Personal Access Token）はユーザーがブラウザの `localStorage` に保存する
  - PATは同一オリジン（`https://{username}.github.io`）のJSのみ読み取り可能であり、第三者サーバーには送信しない
  - PATをHTML/JSソースにハードコードしない
  - PATの入力欄は `type="password"` でマスク表示する
  - PATに付与する権限スコープは `repo`（Contents の読み書き）と `workflow`（`.github/workflows/` の更新）の2つを推奨

### NF-03：入力バリデーション
- Gemini APIのレスポンスはJSONとしてパースを試みる。パース失敗時はリトライせず、`[ERROR]` をログに記録して終了する（GitHub Actionsのワークフロー失敗通知で検知する）
- 各記事のURLは `http://` または `https://` で始まることを確認する。それ以外はスキップする

### NF-04：エラーハンドリング・ログ
- 外部APIエラー時の挙動：

  | エラー | 挙動 |
  |---|---|
  | 収集ソースのタイムアウト | そのソースをスキップして続行（FR-01参照） |
  | 全収集ソース失敗 | `[ERROR]` をログ出力してexit(1)。GitHub Actionsのワークフロー失敗通知で検知する |
  | Gemini API失敗 | `[ERROR]` をログ出力してexit(1)。GitHub Actionsのワークフロー失敗通知で検知する |
  | Discord Webhook失敗 | `[ERROR]` をログ出力してexit(1)。後続のarchive.pyは `continue-on-error: true` により実行される |
  | Gitコミット失敗 | `[ERROR]` をログ出力してexit(1) |

- リトライ：全エラーでリトライなし（翌日のcronで再実行されるため）
- ログ出力：GitHub Actions のステップログに以下を記録する
  - `[INFO]` 各ステップの開始・完了・件数
  - `[WARN]` ソースのスキップ
  - `[ERROR]` 致命的エラー

### NF-05：データ保持
- JSONファイルは `docs/data/` に無期限保存する（GitHubの容量制限内）
- `index.json` は最新100件の日付のみ保持する（100件を超えた場合は古いものから削除）
- GitHub Pagesのキャッシュ：ブラウザキャッシュは `index.json` に対してのみ無効化を推奨（実装は任意）
