# 開発フロー詳細（.claude/flow.md）

> このフローは **Claude Code CLI** での使用を前提とする（Taskツールによる独立エージェント起動を利用）。

> **【このフローが部分的に適用できないプロジェクトタイプ】**
> 以下の場合は各フェーズで注記を確認し、適用できない手順をスキップまたは代替する：
> - **Chrome Extension（Manifest V3）**：.env 不可・モック構造が異なる・テスト環境が特殊・Chrome ウェブストアへの提出が必要
> - **モバイルアプリ（React Native / Flutter 等）**：モックの実装方法・テスト環境・ストア提出が異なる

---

## Phase 1：調査

```
Step 0：プロジェクトルートの確認と progress.md の初期化

  【ディレクトリ構造】
  このフォルダ（Base Projectを複製してサービス名に変えたもの）がプロジェクトルート。
  設計書・実装コード・ドキュメントはすべてここに置く。

  {サービス名}/              ← プロジェクトルート（このフォルダ）
  ├── CLAUDE.md
  ├── progress.md
  ├── .claude/
  ├── {サービス名}_requirements.md
  ├── {サービス名}_architecture.md
  ├── {サービス名}_setup.md
  ├── {サービス名}_business.md
  ├── {サービス名}_basic_design.md
  ├── {サービス名}_detailed_design.md
  ├── src/ または app/       ← 実装コード（architecture.mdのディレクトリ構成に従う）
  └── README.md

  progress.md の初期化：
  - プロジェクト名・開始日を記入する
  - 現在のフェーズを「Phase 1：調査（進行中）」に更新する
  - 「次のアクション」を「Step 1：アイデアのヒアリング」に設定する

Step 1：アイデアのヒアリング（まとめて質問する）
  - 何を作りたいか / 誰が使うか / ビジネス化するか

Step 2：Web検索で市場・競合調査
  - 同様のサービスの存在 / 差別化ポイント

Step 3：技術的な実現可能性の確認
  - 必要なAPI・外部サービスの存在確認

Step 4：調査結果をユーザーに報告
  - 「設計フェーズに進みますか？」と確認する
```

---

## Phase 2：設計（5ファイルを順番に作成）

```
以下の順序で1ファイルずつ作成する。各ファイル完成後にユーザーに確認を取る。

1. requirements-writer → {サービス名}_requirements.md
2. architecture-writer → {サービス名}_architecture.md
3. setup-writer        → {サービス名}_setup.md
4. business-writer     → {サービス名}_business.md
5. basic-design-writer → {サービス名}_basic_design.md

【context7 プラグインを使用する】
  採用するライブラリ・フレームワークのバージョンやAPIを正確に確認する際に使用する。
  特に技術スタック選定・環境変数の仕様確認時に積極的に参照する。

ファイル間の連結ルール：
  requirements.md の各FRの異常系       → basic_design.md Section 7 に引き継ぐ
  requirements.md の各FRの対応画面/インターフェース → basic_design.md の画面・レスポンス仕様に引き継ぐ
  architecture.md の技術スタック       → basic_design.md Section 0 に転記する
  architecture.md の環境変数           → setup.md チェックリストA に転記する
```

---

## Phase 3：モック実装

> **【事前確認】** Web UI が存在しないプロジェクト（Slack Bot / REST API のみ）は
> Phase 3・3.5 をスキップして Phase 4 へ進む。

```
mock-frontend-design スキルを使用する。
参照ファイル：requirements.md / architecture.md / basic_design.md

【外部リダイレクト操作の扱い】
  Stripe Checkout・OAuth 等の外部サービスへのリダイレクトがコア操作の場合、
  モック内では「→ 外部サービスへ遷移（モックのため実装なし）」ボタンとして表現する。
  実際の遷移先画面はモックの対象外とする。

【frontend-design プラグインを使用する】
  コンポーネント設計・デザイントークンの決定時に使用する。

実装完了後、セルフレビューレポートをユーザーに提示する。
```

---

## Phase 3.5：モックレビュー・修正サイクル

> **【対象】** Web UI ありのプロジェクトのみ。Phase 3 をスキップした場合はこのフェーズも不要。

```
原則：コードを直接修正しない。設計書を先に更新してから再生成する。

変更カテゴリ：
  A（表示・レイアウト）  → basic_design.md のみ更新
  B（データ・操作フロー）→ basic_design.md（複数セクション）を更新
  C（機能追加・変更）   → requirements.md → basic_design.md の順に更新
  D（大幅変更）         → ユーザーに確認してから設計を見直す

完成条件（全項目満たしたら Phase 4 へ）：
  □ 全SCR-IDの画面が実装されている
  □ 全操作・空状態・エラー状態が動作する
  □ 375pxモバイルでレイアウトが崩れていない
  □ 未解決のカテゴリC・D変更がない
```

---

## Phase 4：詳細設計

```
detailed-design-writer スキルを使用する。
インプット：requirements.md / architecture.md / basic_design.md
           ／モックコード（Phase 3 を実施した場合のみ）

【context7 プラグインを使用する】
  DBスキーマ・APIエンドポイント・型定義の設計時に
  使用するORMやライブラリの実際の仕様をリアルタイムで参照する。

出力：{サービス名}_detailed_design.md
  Section 1：DBスキーマ（DBなしのプロジェクトはスキップ）
  Section 2：APIエンドポイント定義
  Section 3：コンポーネント構成
  Section 4：型定義・バリデーションスキーマ（TypeScript: zod / Python: Pydantic 等）
```

---

## Phase 5・6：実装→テスト→コードレビュー→修正ループ

ループ終了条件：全テストPASS かつ コードレビュー🔴ゼロ

```
┌──────────────────────────────────────────────────────┐
│  Step A：実装（implementation-runner）                  │
│      ↓                                                │
│  Step B：テスト（testing-runner）← 独立エージェント     │
│      ↓ test_report.md を生成                          │
│  Step C：テスト結果の判定（メインセッション）            │
│      ├─ FAILあり → debug-runner で修正 → Step B へ戻る │
│      └─ 全PASS  → Step C.5 へ                         │
│  Step C.5：リファクタリング（任意）                     │
│      └─ 必要な場合 → refactoring-runner → Step B へ戻る│
│  Step D：コードレビュー（code-reviewer）← 独立エージェント
│      ↓ code_review_report.md を生成                   │
│  Step E：レビュー結果の判定（メインセッション）          │
│      ├─ 🔴あり → 修正 → Step B へ戻る                 │
│      ├─ 🟡あり → ユーザーに提示 → 判断に応じて Step B へ
│      └─ 🔴ゼロ・🟡確認済み → ループ終了               │
└──────────────────────────────────────────────────────┘
```

### Step A：実装

```
implementation-runner スキルを使用する。
参照ファイル：requirements.md / architecture.md / detailed_design.md

【context7 プラグインを使用する】
  外部ライブラリを使った実装時・エラーが出てドキュメントを確認したい時に使用する。
  学習データのカットオフ以降にアップデートされたAPIの仕様確認に特に有効。

【typescript-lsp プラグイン（TypeScriptの場合）】
  型定義・型エラー対応・リファクタリング時に使用する。

【security-guidance プラグイン】
  認証・バリデーション・環境変数を扱うコードで必ず使用する。

【CLI ツール / パッケージの場合の動作確認】
  Web サーバーの起動確認（uvicorn / npm run dev 等）は不要。
  代わりに以下を確認する：
  - `python {entry}.py --help` または `{コマンド名} --help` が表示されるか
  - 主要コマンドを1つ手動実行してエラーなく動作するか

修正時（2回目以降）：
  test_report.md または code_review_report.md の内容を読んで
  修正が必要な箇所のみを実装し直す。
```

### Step B：テスト（独立エージェント）

```
【テスト環境の確認（初回のみ）】
  E2Eテスト・統合テストを実施する前に、以下を確認する。

  外部サービス連携があるプロジェクトの場合：
    - テスト用アカウント・トークンが準備済みか確認する
    例：Slack Bot → テスト用 Workspace・テスト用 Bot Token
        外部API連携 → サンドボックス環境・テスト用 APIキー
    未準備の場合は setup.md のチェックリストを確認してセットアップしてから実施する。

  Webhook を持つプロジェクトの場合：
    - ローカルでの Webhook 受信ツールが準備済みか確認する
    （例：Stripe → Stripe CLI `stripe listen` / その他 → ngrok 等）

  外部 LLM API（OpenAI・Anthropic 等）を使うプロジェクトの場合：
    - テスト時は実 API を叩かず jest.mock / unittest.mock 等でモック化する
    - モックが困難な E2E テストのみ実 API を使用し、最安モデル（例：gpt-4o-mini）を指定する
    - テスト用の API キーに使用上限を設定しておくことを推奨する

  DBを使うプロジェクトの場合：
    - テスト用 DATABASE_URL が .env.test または .env.local に設定されているか確認する
    - テスト実行前にテスト用DBをリセットする
      ORM 使用時の例：
        Prisma → `npx prisma migrate reset --force`
        Alembic → `alembic downgrade base && alembic upgrade head`
      ファイルDB（SQLite）の場合：
        `rm test.db` でファイルを削除してから再作成する

Taskツールでサブエージェントを起動して実行する：

「testing-runnerスキルを使って総合テストを実施してください。
 結果を test_report.md に書き出してください。
 FAILがある場合は原因の詳細も含めてください。」
```

### Step C：テスト結果の判定

```
cat test_report.md で結果を確認する。

全PASS → progress.md のテスト結果を更新 → Step C.5 へ
FAILあり → debug-runner で修正 → progress.md のブロッカーを更新 → Step B へ戻る

【無限ループ防止】
progress.md のループ回数を確認する。
同じFAILが3ループ連続で解決しない場合はユーザーに報告して中断する。
```

### Step C.5：リファクタリング（任意）

```
テストが全件PASSした後、コードレビューの前に必要と判断した場合に実施する。

判断基準（以下のいずれかに該当する場合に検討する）：
  ・コードの重複が目立つ
  ・Route Handler にビジネスロジックが漏れている
  ・関数が長すぎて責務が分かりにくい

実施する場合：
  refactoring-runner スキルを使用する。
  リファクタリング完了後は必ず Step B（テスト）に戻り、動作が変わっていないことを確認する。

不要と判断した場合：
  このステップをスキップして Step D へ進む。
```

### Step D：コードレビュー（独立エージェント）

```
Taskツールでサブエージェントを起動して実行する：

「code-reviewerスキルを使って実装コードをレビューしてください。
 参照ファイル：requirements.md / architecture.md / detailed_design.md
 レビュー対象：src/ または app/ 以下の全実装ファイル
 結果を code_review_report.md に書き出してください。

 【使用するプラグイン】
 - code-review プラグイン：静的解析によるコード品質チェック
 - security-guidance プラグイン：セキュリティ脆弱性の検出
 両プラグインの検出結果もレポートに含めること。」
```

### Step E：コードレビュー結果の判定

```
cat code_review_report.md で結果を確認する。
progress.md のループ回数・レビュー結果を更新する。

🔴あり → 修正 → Step B へ戻る
🟡あり → ユーザーに提示 → YES なら修正して Step B へ / NO なら次へ
🔴ゼロ → ループ終了 → progress.md の現在のフェーズを「Phase 7」に更新 → Phase 7 へ
```

---

## Phase 7：デプロイ

```
【README作成（必要な場合）】
  初回デプロイ時・大きな機能追加時は readme-writer スキルで README.md を生成する。
  参照ファイル：requirements.md / architecture.md / setup.md / business.md

architecture.md のホスティングセクションからデプロイ形態を確認して実施する。

【デプロイ前の互換性チェック】
  以下の組み合わせは非互換のため、architecture-writer の段階で代替を検討する：
  - SQLite（ファイルDB）× Vercel / Railway 等の PaaS
    → PaaS はエフェメラルなファイルシステムのため、デプロイのたびにデータが消える
    → PostgreSQL / MySQL 等のマネージドDBに切り替えることを推奨する

【サーバーデプロイ（Vercel / Railway / GCP 等）の場合】
  deployment-runner スキルを使用する。

  デプロイ前：
    □ 全テストPASS
    □ ローカルビルド成功
    □ 環境変数の棚卸し完了
    □ DBを使うプロジェクトの場合：本番DBのマイグレーション実施
        （例：Prisma → `npx prisma migrate deploy` / Alembic → `alembic upgrade head`）

  デプロイ後：
    □ setup.md の動作確認チェックを本番URLで実施
    □ 外部サービスの Webhook URL を本番 URL に更新
    □ OAuth を使うプロジェクトの場合：各プロバイダーの承認済みリダイレクト URI に本番 URL を追加

【パッケージ配布（PyPI / npm 等）の場合】
  deployment-runner スキルは使用しない。以下を手動で実施する。

  公開前：
    □ 全テストPASS
    □ バージョン番号を更新（pyproject.toml / package.json）
    □ CHANGELOG / README を更新
    □ 認証情報（APIトークン）が準備済みか確認

  公開：
    PyPI → `python -m build && twine upload dist/*`
    npm  → `npm publish`

  公開後：
    □ インストールして動作確認（例：`pip install {パッケージ名}` → コマンド実行）

【Chrome Extension（Manifest V3）の場合】
  deployment-runner スキルは使用しない。以下を手動で実施する。

  公開前：
    □ 全テストPASS
    □ manifest.json のバージョン番号を更新
    □ API キー等の機密情報が chrome.storage または options page 経由で設定される設計か確認
       （.env は Chrome Extension では使用不可）
    □ `zip -r extension.zip . --exclude='.git/*' --exclude='node_modules/*'` でパッケージ化

  公開：
    Chrome Developer Dashboard (chrome.google.com/webstore/devconsole) でアップロード・審査提出

  公開後：
    □ Chrome ウェブストアからインストールして動作確認
```
