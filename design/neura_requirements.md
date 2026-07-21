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
- リアルタイム更新（バッチ処理のみ）：cron-job.org + GitHub Actions `workflow_dispatch` による定時実行（任意の時刻変更は可能）
- 全文検索：静的サイトのためサーバー側検索は未実装。クライアント側JS検索（SCR-03）で代替
- 複数端末間の既読状態の同期：既読管理はブラウザの `localStorage` のみで行うため、別端末・別ブラウザでは既読状態が共有されない
- 実際に開封したかどうかを判定した上でのリマインド送信：サーバー側（GitHub Actions）は `localStorage` の既読状態を一切参照できないため、FR-08の未読リマインドは「その日の配信有無」のみを条件とする無条件送信となる
- ホーム画面（SCR-01）での既読件数・既読率の表示：既読情報はSCR-02/SCR-03の記事カード単位でのみ表示する

### 前提条件の欠如による除外
- 有料APIの利用：月額費用ゼロ制約のため

---

## 機能要件

### FR-01：AIニュース収集

#### 概要（1行）
Hacker News API・Reddit/はてブ/各種RSSフィードからAI関連記事を並列取得する（Reddit・はてブはBotブロック/API非提供のためRSSを使用）。

#### 対応するインターフェース
cron-job.org が `workflow_dispatch` 経由で GitHub Actions を起動（`notify_schedules` の `enabled: true` なスロット数分のジョブが cron-job.org に登録される。1日最大3回まで設定可能）

#### 入力
- トリガー：cron-job.org から送信される `workflow_dispatch` イベント（`notify_schedules` の有効スロット数分の cron-job.org ジョブが登録される）
- 入力データなし（パラメータは固定）

#### 収集対象ソース

**🌍 海外ソース**

| ソース | 取得方法 | 取得件数上限 | 認証 |
|---|---|---|---|
| Hacker News | `https://hacker-news.firebaseio.com/v0/topstories.json` → 上位100件取得後フィルタ | 上位100件をフィルタ対象 | 不要 |
| Reddit `/r/artificial` | RSS `https://www.reddit.com/r/artificial/top/.rss?t=day` | feedparserが返す全エントリ（通常25件前後。フィード側に依存） | 不要（User-Agent設定必須。`.json` はBotブロックされるためRSSを使用） |
| Reddit `/r/MachineLearning` | RSS `https://www.reddit.com/r/MachineLearning/top/.rss?t=day` | feedparserが返す全エントリ（通常25件前後。フィード側に依存） | 不要（同上） |
| RSS（TechCrunch AI） | `https://techcrunch.com/category/artificial-intelligence/feed/` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要 |
| RSS（MIT Technology Review AI） | `https://www.technologyreview.com/topic/artificial-intelligence/feed` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要 |
| RSS（VentureBeat AI） | `https://venturebeat.com/category/ai/feed/` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要 |

**🇯🇵 日本語ソース**

| ソース | 取得方法 | 取得件数上限 | 認証 |
|---|---|---|---|
| Zenn（`ai` タグ） | RSS `https://zenn.dev/topics/ai/feed` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要 |
| Qiita AI | RSS `https://qiita.com/tags/ai/feed` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要（`zenn` typeと同じパーサ使用。AIタグフィードのためキーワードフィルタ不要） |
| ITmedia AI+ | RSS `https://rss.itmedia.co.jp/rss/2.0/aiplus.xml` | feedparserが返す全エントリ（通常20件前後。フィード側に依存） | 不要 |
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
5. スコア系ソース（HN・はてブ）はスコア降順にソートして上位14件を選定し、日付系ソース（Reddit・RSS・Zenn）は公開日時降順にソートして上位6件を選定する（RedditはRSS化によりスコア無しのため日付系）
6. 上位合計20件（スコア系14件・日付系6件）をマージして次の処理に渡す
7. 上位20件の各記事URLに対してHTTPリクエストを送信し、`trafilatura` ライブラリで本文テキストを抽出する
   - 取得成功：`body_text` フィールドに本文テキスト（最大5000文字）を格納する
   - タイムアウト（10秒）またはアクセスブロック（403等）：`body_text: null` として続行する（このソースをスキップしない）
8. `body_text` 付きの記事リストを次のFR-02に渡す

#### 出力（正常系）
```python
# 記事オブジェクトのリスト（最大20件）
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

#### 出力（ステータスファイル）
- 収集完了後（成功・失敗ソース問わず）に `/tmp/neura_collect_status.json` を書き出す（詳細設計書 §1-4 参照）
- `archive.py` がこのファイルを `docs/data/collect_status.json` にコピーしてgitコミットに含める
- 設定画面（SCR-04）が GitHub Contents API でこのファイルを読み、各ソース行に「⚠ 取得失敗」バッジを表示する

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
GitHub Actions ワークフロー（FR-01の直後に実行）

#### 入力
- FR-01の出力（記事リスト、最大20件。各記事に `body_text` フィールドあり）

#### 処理フロー（2段階 Gemini 呼び出し＋不足時の補充）

**0. スロット判定**
1. JST現在時刻と一致する `enabled: true` のスロットを `config.notify_schedules` から探す（一致しない場合は最初の有効スロットを使う）
2. スロットの `genres`（ジャンルON/OFF）・`max_articles`（1〜10。以下 `slot_max`）を以降の処理で使用する

**Stage 1: 記事選定**
3. Stage 1で選ぶ件数 `select_n` を `min(10, slot_max + 5)` で算出する（後工程のジャンル誤判定・重複除去の余裕分として+5、上限10件）
4. 全記事のタイトル・冒頭700文字・有効ジャンル一覧を `SELECTION_PROMPT` に含め、Gemini Flash API に送信する。プロンプトは「該当ジャンルの記事のみを選ぶこと」をハード制約として明記する
5. Gemini が初心者向けに面白い記事を最大 `select_n` 件選び、URLのみをJSON配列で返す
6. 返却されたURLで元記事リストをフィルタし、選定記事を確定する
   - パース失敗・選定0件時：全件を Stage 2 へフォールバック
   - 選定件数が `select_n` を超過した場合：先頭から `select_n` 件に切り詰める（Gemini応答の途中切れ防止）

**Stage 2: 翻訳・要約**
7. 選定記事のタイトル・本文（最大5000文字）を `config.gemini_prompt` テンプレートに含め、Gemini Flash API（`gemini-2.5-flash`、レスポンススキーマ指定）に送信する
8. プロンプトの内容（`config.gemini_prompt` テンプレート）：
   - url: 元記事のURLをそのまま返す（変更禁止）
   - title_ja: 日本語タイトル（30文字以内）
   - summary_ja: 日本語要約（150文字以内）。何がわかる・なぜ面白いかを初心者向けに
   - key_points: この記事が伝えたいことを最大3つ、日本語の配列で返す（各項目40文字以内。内容が薄い記事は1〜2件でも可。本文取得不可の場合は空配列 `[]`）
   - translation_ja: 全文日本語翻訳（markdown形式）
   - category: "ニュース" | "研究" | "活用事例" | "ツール"（レスポンススキーマのenumで強制）
   - importance: 1〜5（初心者が面白い・試してみたいと感じるかで判断）
9. Gemini APIのレスポンスをJSONとしてパースする（リトライ仕様はNF-01参照）
10. パース成功時、以下の後処理を行う
    - Geminiが返す過剰エスケープされた `\n`（リテラル文字列）を実改行に補正する（`title_ja`・`summary_ja`・`translation_ja`・`key_points`各項目）
    - `category` をGeminiの表記ゆれ（英語・日本語バリエーション）から正規4値へマッピングする（未知の値はそのまま返し、後段のジャンルフィルタで除外される）
    - Gemini が同じ URL を重複返却した場合は URL 正規化後に先着1件を残して重複除去する
11. 無効カテゴリ（`genres` がfalseのカテゴリ）を除外してから `importance` 降順でソートし、`slot_max` 件を選択する

**補充（不足時のみ）**
12. 選択件数が `slot_max` に満たない場合、Stage 1で未選定だった残り記事から不足分＋5件（残り件数が上限）を対象に、Stage 1・Stage 2と同じ手順で1回だけ追加選定・翻訳を行い、結果をマージしてから再度ソート・選定する（2回目の補充は行わない）
13. 補充後もなお0件の場合：異常系として終了する

14. 元の記事URLと対応付けて、最終記事オブジェクトに `source`・`published_at` を復元する

#### 出力（正常系）
```python
# 最終記事オブジェクトのリスト（スロットのmax_articles設定による 1〜10件）
[
  {
    "title_ja": "OpenAI、GPT-5を正式リリース",
    "summary_ja": "OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...",
    "key_points": ["推論能力が大幅に向上", "コンテキスト長が200万トークンに拡大", "SWE-benchで85%を達成"],
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
    "key_points": [],
    "translation_ja": null,  // body_textがnullだった場合
    ...
  }
]
```

#### 出力（異常系）
```
[ERROR] Gemini API failed after all retries
（NF-01のリトライを尽くしても失敗した場合。GitHub Actionsのワークフロー失敗として記録される）

[ERROR] summarize: 有効カテゴリの記事が0件（genres設定を確認）
（補充後もなお該当カテゴリの記事が1件も選出できなかった場合）
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
1. トップレベルの `content`（プレーンテキスト）を構築する：`🧠 Neura Daily — {YYYY/MM/DD}（{件数}件）` の1行目に続けて、全記事タイトルを `{連番}. {title_ja}` の箇条書きで列挙する（Discordのプッシュ通知プレビューは `embeds` 内のテキストを表示しないため、通知バナーに記事タイトルを表示する目的で付与する）
2. Discord Embed形式のメッセージを構築する
   - ヘッダー：`🧠 Neura Daily — {YYYY/MM/DD}（{件数}件）`
   - 各記事をEmbed fieldとして追加：`[カテゴリバッジ] タイトル` + 要約 + `key_points`（箇条書き、最大3件） + URLリンク
   - カテゴリバッジ：`ニュース`→🗞️、`研究`→🔬、`活用事例`→💡、`ツール`→🛠️
   - フッター：`Neura by GitHub Actions`
3. 構築したメッセージの全embed合計文字数（title・description・field name・field value・footer・author nameの総和）を計算する
   - 6,000字以内：そのまま4へ進む
   - 6,000字超過：`importance` 昇順（低い記事から）に、その記事の `key_points` 箇条書きをEmbedから除去する。1件除去するごとに再計算し、6,000字以内に収まった時点で打ち切る
   - 全記事の `key_points` を除去してもなお6,000字を超過する場合：`importance` 昇順に `summary_ja` を100文字で切り詰め末尾に `…` を付与する（発生頻度は極めて低い想定のフォールバック）
4. `content` と `embeds` を1つのペイロードにまとめ、`DISCORD_WEBHOOK_URL` に対してPOSTリクエストを送信する（`requests` ライブラリ使用）
5. HTTPステータス `204` を正常とする
   - `204` 以外の場合：ログに `[ERROR] Discord webhook failed: {status_code}` を記録して終了（リトライなし）

#### 出力（正常系）
```
Discordチャンネルに以下が投稿される（プッシュ通知バナーには冒頭のcontentテキストが表示される）：

[content]
🧠 Neura Daily — 2026/06/18（7件）
1. OpenAI、GPT-5を正式リリース
2. ZennでClaude APIを使った業務自動化ツールを作った
3. Transformerの新アーキテクチャ、推論速度3倍に

[embeds]
🧠 Neura Daily — 2026/06/18（7件）

🗞️ OpenAI、GPT-5を正式リリース
OpenAIが次世代モデルGPT-5を発表。推論能力が大幅に向上し...
・推論能力が大幅に向上
・コンテキスト長が200万トークンに拡大
・SWE-benchで85%を達成
[HackerNews] → https://example.com/article

💡 ZennでClaude APIを使った業務自動化ツールを作った
請求書処理をAIで自動化した実装例。コスト削減効果も検証...
・請求書のOCR読み取り精度が95%に到達
・月間処理コストを70%削減
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
1. JST基準の本日日付・時刻から日次JSONファイルを生成する（1配信スロット＝1ファイル。1日に最大3スロット配信されるため、日付のみでは一意にならない）
   - ファイルキー：`{YYYY-MM-DD}_{HH}`（`HH`はJST時刻2桁。例：`2026-06-18_13`）
   - ファイルパス：`docs/data/{ファイルキー}.json`
   - JSONの構造：
     ```json
     {
       "date": "2026-06-18",
       "time": "13:00",
       "generated_at": "2026-06-18T04:00:00Z",
       "articles": [ ...FR-02の出力... ]
     }
     ```
2. インデックスファイル `docs/data/index.json` を更新する
   - 形式：`{ "digests": [{ "date": "2026-06-18", "time": "13:00", "file": "2026-06-18_13", "count": 7, "categories": {"ニュース":3,...}, "titles": [{"t": "...", "c": "..."}, ...] }, ...] }`（`digests` キーに各配信のメタ情報を降順配列で持つ。最新100件まで保持）
   - 各エントリは日次データから記事件数（`count`）・カテゴリ別件数（`categories`）・先頭10件のタイトル略称（`titles`）を集計して生成する
   - 同一 `(date, time)` の既存エントリは除去してから先頭に追加する（再実行時の重複防止）
3. `git add docs/data/ && git commit -m "chore: add daily digest {YYYY-MM-DD}" && git push` を実行する
   - GitHub Actionsの `GITHUB_TOKEN` を使用する
   - push が non-fast-forward で失敗した場合（設定画面からの直接コミットと競合等）：`git pull --rebase` 後に1回だけ再試行する
   - コミット失敗時：ログに `[ERROR] Git commit failed` を記録する（Discordへの通知はしない）

#### 出力（正常系）
```
docs/data/2026-06-18_13.json（新規作成）
docs/data/index.json（更新）
docs/data/collect_status.json（更新：FR-01のソース別収集結果）
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
4. 「▼ 全文翻訳を見る」ボタンをクリックするとモーダルが開き、タイトル直下に `key_points`（最大3件の箇条書き）→ `translation_ja` のmarkdownレンダリングの順で表示する
   - `key_points` が空配列の場合はブロックごと非表示にする（後方互換：フィールド自体が無い過去データも同様に非表示）
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
4. `notify_schedules` が変更されていた場合、cron-job.org API で各スロットのジョブ時刻を更新する（`cronJobOrgUpdate()`）
   - `enabled: true` かつ `cron_job_id` が設定されているスロットを対象とする
   - `localStorage` の `neura_cronjob_apikey`（cron-job.org APIキー）を Authorization ヘッダーに付与する
   - cron-job.org API（`PATCH https://api.cron-job.org/jobs/{cron_job_id}`）で `schedule.hours` を新しい JST 時刻に更新する
   - 失敗時：ERR-14 を表示する（config.json の保存は成功済みのため別エラーとして扱う）
5. 全て成功時：「設定を保存しました」トーストを表示する
6. 失敗時：エラー内容に応じたメッセージを表示する（ERR-08〜ERR-12・ERR-14参照。ERR-13は使用しない。詳細はNF-02参照）

#### 出力（正常系）
- `config/config.json` がリポジトリに1コミット追加される
- `notify_schedules` が変更された場合は cron-job.org のジョブ時刻が即座に更新される
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
    { "hour": 13, "enabled": true,  "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true}, "cron_job_id": "1234567" },
    { "hour": 20, "enabled": false, "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true}, "cron_job_id": null },
    { "hour":  8, "enabled": false, "max_articles": 10, "genres": {"ニュース": true, "研究": true, "活用事例": true, "ツール": true}, "cron_job_id": null }
  ]
}
```

> **`sources[].type` の許容値**：`"hackernews"` / `"reddit"` / `"rss"` / `"zenn"` / `"hatena"`。collect.py がこの値でパーサを振り分ける（FR-01参照）。設定画面からユーザーが追加できるソースは `type: "rss"`（汎用RSS/Atom）のみとする。`"zenn"` type は Qiita AI も含む（AIタグフィードのためキーワードフィルタをスキップする）。
> **`gemini_prompt` の `{articles}` プレースホルダー**：summarize.py が記事一覧テキストに置換する。このプレースホルダーは必須。プロンプトは設定UIには非公開で config.json 直接編集で変更する。`{articles}` 不在時は summarize.py がデフォルトプロンプトにフォールバックする（`[WARN]` ログ）。
> **`notify_schedules`**：通知スケジュールの配列（最大3件）。各エントリは `{ "hour": 0〜23（JST）, "enabled": true/false, "max_articles": 1〜10, "genres": {カテゴリ: bool}, "cron_job_id": string|null }` の形式。`enabled: true` のスロットは cron-job.org 側に個別のジョブとして登録され、cron-job.org がそのジョブから `daily.yml` へ `workflow_dispatch` を送る（`daily.yml` 自体に `enabled` スロットに対応する cron 式は存在しない。architecture.md参照）。少なくとも1件は `enabled: true` でなければならない（保存時にクライアント側でチェックし、`"少なくとも1つのスケジュールを有効にしてください。"` をスケジュールセクション直下にインライン表示する。専用のエラーIDは割り当てない）。
> **`notify_schedules[].max_articles`**：そのスロットで選出する記事の上限件数（1〜10の整数）。スロットごとに異なる件数を設定できる。デフォルトは10。
> **`notify_schedules[].genres`**：そのスロットで通知するカテゴリのON/OFFマップ。スロットごとに異なるジャンルフィルタを設定できる。
> **`notify_schedules[].cron_job_id`**：このスロットに対応する cron-job.org のジョブID（文字列）。Pythonスクリプトからは参照されず、設定画面（`docs/index.html`）が cron-job.org API連携（`cronJobOrgUpdate()`）にのみ使用する。未連携のスロットは `null`。
> **グローバルの `genres` / `max_articles` は廃止**：旧設定（`run_hour_jst`・グローバル `genres`・グローバル `max_articles`）が残っている場合は `config_loader.py` が自動マイグレーションしてスロット内に移行する。
> **GitHub接続情報（owner / repo / PAT / cron-job.org APIキー）は config.json に含めない**：config.json 自体をGitHub APIで取得するために owner/repo/PATが先に必要となる（鶏卵問題）ため、これらはブラウザの `localStorage` にのみ保存する（FR-06 セキュリティ・SCR-04参照）。

#### config.json が存在しない場合（フォールバック）
- collect.py / summarize.py は `config/config.json` が存在しない、またはパースに失敗した場合、上記のデフォルト値で動作する（`[WARN] config.json not found, using defaults` をログ出力）。
- リポジトリには初期状態で上記デフォルト値を持つ `config/config.json` を同梱する。

#### 依存関係
- このFRに依存するFR：FR-01（`sources`・`keywords` を読み込む）、FR-02（`gemini_prompt`・`genres` を読み込む）
- このFRが依存するFR：なし（独立して動作する）

---

### FR-07：既読管理

#### 概要（1行）
「[+ 全文翻訳]」ボタンを押して全文翻訳モーダルを開いた時点でブラウザの `localStorage` に既読フラグを記録し、SCR-02・SCR-03の記事カードに既読状態を視覚的に表示する。

#### 対応する画面
- `SCR-02`：日次詳細
- `SCR-03`：検索結果

#### 入力
- ユーザーの「[+ 全文翻訳]」ボタンクリック操作（`toggleTranslation()` / `toggleTranslationById()` 呼び出し時点。カードの表示・一覧のスクロールのみでは発火しない）
- 記事の一意キー：記事の `url`（正規化済み。FR-01の重複URL排除と同じ正規化ルールを使用する）

#### 処理フロー
1. `localStorage` から `neura_read_articles`（既読URLの配列、JSON文字列）を読み込む。存在しない場合は空配列として扱う
2. ユーザーが「[+ 全文翻訳]」ボタンを押して全文翻訳モーダルを開いた時点で、その記事の `url` が配列に存在するか確認する
   - 存在しない場合：配列に追加して `localStorage.setItem('neura_read_articles', JSON.stringify(配列))` で保存する
   - 存在する場合：何もしない（既に既読）
3. SCR-02・SCR-03のページ描画時（記事一覧のfetch完了後）、各記事の `url` が `neura_read_articles` に含まれるか判定し、含まれる記事のカードに既読表示を適用する
   - カード左上に `✓ 既読` バッジを表示する
   - カード全体の不透明度を70%にする（`opacity: 0.7`）

#### 出力（正常系）
```
SCR-02（日次詳細）:
  ┌─────────────────────────┐
  │ ✓ 既読                  │  ← 既読記事は薄く表示
  │ 🗞️ OpenAI、GPT-5を...   │
  └─────────────────────────┘
  ┌─────────────────────────┐
  │ 🔬 Transformerの新...   │  ← 未読は通常表示
  └─────────────────────────┘
```

#### 出力（異常系）
- `localStorage` が利用不可（プライベートブラウジング等でアクセス拒否）：`try-catch` で例外を捕捉し、既読機能全体を無効化する（全記事を未読表示のまま、エラーメッセージは表示しない。閲覧機能自体は継続する）
- `localStorage` の値がJSONとしてパース不可：空配列として扱い、`neura_read_articles` を初期化し直す

#### 依存関係
- このFRに依存するFR：なし
- このFRが依存するFR：FR-05（記事一覧の描画完了後に既読判定を行う）

---

### FR-08：未読リマインド通知

#### 概要（1行）
その日の最終定時配信の翌朝9時（JST）に、前日のダイジェストへの再訪問を促す簡易リマインドをDiscordへ1回だけ送信する。

#### 対応するインターフェース
cron-job.org が固定時刻（9:00 JST）で `workflow_dispatch` 経由の専用GitHub Actionsワークフロー（`remind.yml`）を起動する（`notify_schedules` とは独立した固定ジョブ。設定画面での編集対象外）

#### 入力
- トリガー：cron-job.org からの `workflow_dispatch` イベント（毎日9:00 JST固定）
- `docs/data/index.json`（`digests` 配列。日付ごとに複数スロット分のエントリを持つ。FR-04参照）

#### 処理フロー
1. JST基準で前日の日付（`YYYY-MM-DD`）を算出する
2. `docs/data/index.json` を読み込み、`digests` 配列に `date` が前日の日付と一致するエントリが1件でも存在するか確認する
   - 一致するエントリが0件（前日に配信が1回もなかった・収集失敗した等）：何もせず終了する（Discordへは何も送信しない）
   - 1件以上存在する：3へ進む
3. Discordへ簡易メッセージを送信する（Embedなし、プレーンテキスト1通）
   - 文面：`🌙 昨日のAIニュースダイジェスト、まだご覧になっていない方はこちら → {サイトURL}`
   - `{サイトURL}` は `https://{username}.github.io/{repo}/`（architecture.mdのホスティング設定を参照）
4. `DISCORD_WEBHOOK_URL` に対してPOSTリクエストを送信する
5. HTTPステータス `204` を正常とする
   - `204` 以外の場合：ログに `[ERROR] Discord webhook failed: {status_code}` を記録して終了（リトライなし）

#### 出力（正常系）
```
Discordチャンネルに以下が投稿される：

🌙 昨日のAIニュースダイジェスト、まだご覧になっていない方はこちら → https://example.github.io/neura/
```

#### 出力（異常系）
- 前日データが存在しない：送信せず終了（ログに `[INFO] No digest for {前日日付}, skip reminder` を記録）
- `index.json` が存在しない・パース失敗：送信せず終了（ログに `[WARN] index.json not found or invalid, skip reminder` を記録）
- Webhook URLが未設定：`[ERROR] DISCORD_WEBHOOK_URL is not set` をログ出力して終了
- HTTPステータスが204以外：`[ERROR] Discord webhook failed: {status_code}` をログ出力して終了

#### 依存関係
- このFRに依存するFR：なし
- このFRが依存するFR：FR-04（前日データの存在確認に `docs/data/index.json` の `digests` を使用する）

---

### FR-09：週次ダイジェスト配信

#### 概要（1行）
毎週土曜12:00（JST）に、直近7日分のアーカイブ記事を集計し、件数サマリーと重要記事トップ5をDiscordへ配信する。

#### 対応するインターフェース
cron-job.org が固定時刻（毎週土曜12:00 JST）で `workflow_dispatch` 経由の専用GitHub Actionsワークフロー（`weekly.yml`）を起動する

#### 入力
- トリガー：cron-job.org からの `workflow_dispatch` イベント（毎週土曜12:00 JST固定）
- `docs/data/index.json`（`digests` 配列）、および該当する `docs/data/{file}.json`

#### 処理フロー
1. JST基準で当日（土曜）から直近7日分の日付（`YYYY-MM-DD`）を算出する
2. `docs/data/index.json` を読み込み、`digests` 配列から `date` が該当7日以内のエントリを全て抽出する
   - 該当エントリが0件の場合：何もせず終了する（Discordへは何も送信しない）
3. 抽出した各エントリの `file` キー（例：`"2026-06-18_13"`）を使って `docs/data/{file}.json` を順にfetchし、`articles` を全てメモリに集約する
4. 集約した記事から以下を集計する
   - 合計記事件数
   - カテゴリ別件数（`ニュース`・`研究`・`活用事例`・`ツール`）
   - `importance` 降順で上位5件（同率の場合は日付降順を優先）
5. Discord Embed形式のメッセージを構築する
   - ヘッダー：`📅 Neura Weekly — {対象期間開始日}〜{対象期間終了日}（計{合計件数}件）`
   - カテゴリ内訳フィールド：`🗞️ ニュース {n}件 / 🔬 研究 {n}件 / 💡 活用事例 {n}件 / 🛠️ ツール {n}件`
   - 注目記事トップ5フィールド：各記事を `[カテゴリバッジ] タイトル → URL` の箇条書きで列挙する
   - フッター：`Neura Weekly Digest`
6. `DISCORD_WEBHOOK_URL` に対してPOSTリクエストを送信する
7. HTTPステータス `204` を正常とする
   - `204` 以外の場合：ログに `[ERROR] Discord webhook failed: {status_code}` を記録して終了（リトライなし）

#### 出力（正常系）
```
Discordチャンネルに以下が投稿される：

📅 Neura Weekly — 2026/06/13〜2026/06/19（計42件）

🗞️ ニュース 18件 / 🔬 研究 9件 / 💡 活用事例 10件 / 🛠️ ツール 5件

今週の注目記事：
🗞️ OpenAI、GPT-5を正式リリース → https://example.com/article
🔬 Transformerの新アーキテクチャ、推論速度3倍に → https://example.com/article2
...
```

#### 出力（異常系）
- 該当期間のデータが1件も存在しない：送信せず終了（ログに `[INFO] No data for the past week, skip weekly digest` を記録）
- Webhook URLが未設定：`[ERROR] DISCORD_WEBHOOK_URL is not set` をログ出力して終了
- HTTPステータスが204以外：`[ERROR] Discord webhook failed: {status_code}` をログ出力して終了

#### 依存関係
- このFRに依存するFR：なし
- このFRが依存するFR：FR-04（`docs/data/` の日次JSONを集計元として使用する）

---

## 非機能要件

### NF-01：処理時間
- GitHub Actions の1回あたりの実行時間は、リトライが発生しない通常時は5分以内を目標とする
- 各ソースへのHTTPリクエストのタイムアウトは10秒とする
- Gemini APIへの個々のリクエストのタイムアウトは30秒とする
- Gemini API呼び出し（`summarize.py`）はAPI例外（タイムアウト・レート制限等）発生時に最大5回・60秒間隔でリトライする。Stage 2はJSONパース失敗時にも最大3回・30秒間隔で呼び出しごとリトライする（両者は多重にネストしうるため、リトライが連続した場合は実行時間が5分を超えることがある。GitHub Actionsのデフォルトジョブタイムアウト（6時間）・無料枠2000分/月の範囲内であれば許容する）

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
- Gemini APIのレスポンスはJSONとしてパースを試みる。パース失敗時はNF-01のリトライ仕様に従って再試行し、全リトライを使い切った場合のみ `[ERROR] Gemini API failed after all retries` をログに記録して終了する（GitHub Actionsのワークフロー失敗通知で検知する）
- 各記事のURLは `http://` または `https://` で始まることを確認する。それ以外はスキップする

### NF-04：エラーハンドリング・ログ
- 外部APIエラー時の挙動：

  | エラー | 挙動 |
  |---|---|
  | 収集ソースのタイムアウト | そのソースをスキップして続行（FR-01参照） |
  | 全収集ソース失敗 | `[ERROR]` をログ出力してexit(1)。GitHub Actionsのワークフロー失敗通知で検知する |
  | Gemini API失敗 | NF-01のリトライ仕様に従って再試行。全リトライ失敗時のみ `[ERROR]` をログ出力してexit(1)。GitHub Actionsのワークフロー失敗通知で検知する |
  | Discord Webhook失敗 | `[ERROR]` をログ出力してexit(1)。後続のarchive.pyは `continue-on-error: true` により実行される |
  | Gitコミット失敗 | `[ERROR]` をログ出力してexit(1) |
  | リマインド送信失敗（FR-08） | `[ERROR]` をログ出力してexit(1)。daily.ymlとは独立したワークフローのため他処理に影響しない |
  | 週次ダイジェスト送信失敗（FR-09） | `[ERROR]` をログ出力してexit(1)。daily.ymlとは独立したワークフローのため他処理に影響しない |

- リトライ：Gemini API呼び出し（NF-01参照）のみリトライあり。それ以外の全エラーはリトライなし（次回の定時実行で再試行されるため）
- ログ出力：GitHub Actions のステップログに以下を記録する
  - `[INFO]` 各ステップの開始・完了・件数
  - `[WARN]` ソースのスキップ
  - `[ERROR]` 致命的エラー

### NF-05：データ保持
- JSONファイルは `docs/data/` に無期限保存する（GitHubの容量制限内）
- `index.json` は最新100件の日付のみ保持する（100件を超えた場合は古いものから削除）
- GitHub Pagesのキャッシュ：ブラウザキャッシュは `index.json` に対してのみ無効化を推奨（実装は任意）
- 既読データ（`neura_read_articles`）：ブラウザの `localStorage` に無期限保存する。サーバー側では保持しない（FR-07参照）。件数上限は設けない
