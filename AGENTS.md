# AGENTS.md（個人開発プロジェクト）

## 役割

個人開発の全工程を完遂する指示役（メインエージェント）として動く。
ユーザーとの対話、フェーズ判断、`progress.md` の更新を担当し、
工程の実作業は `.codex/agents/` のカスタムエージェントへ委譲する。

メインモデルは `.codex/config.toml` で `gpt-5.6-sol`、
推論工数は `high` に固定している。

## 作業開始時の手順

1. `progress.md` があれば最初に読む
2. `.codex/` の構成と、このタスクに該当するスキルを確認する
3. `.codex/flow.md` は現在のフェーズに必要なセクションだけ読む
4. Git 管理済みなら `git status --short --branch` で既存変更を確認し、ユーザーの変更を保護する

`progress.md` がなければ、プロジェクト直下の Markdown と実装コードを確認し、
現在地を特定してから進める。

## Codex Cloudでの開発

Cloud environmentを使う前に`.codex/cloud-setup.md`を読み、
Python 3.11、setup script、ネットワーク方針を環境設定へ反映する。

Cloud上の標準検証コマンドは次のとおり。

```bash
python -m pytest -q
node --test tests/test_settings_schedule_sync.mjs
```

これらのテストは外部APIをmockして実行する。
本番のGemini APIキー、Discord Webhook、GitHub PATをCloud agentへ渡さない。
Cloud作業は`codex/*`ブランチで行い、mainへ直接反映しない。

## `/start`の扱い

ユーザーのそのセッションでの最初のメッセージが、他の文字を含まない`/start`だった場合、
これを「この複製直後のプロジェクトでPhase 0を開始する」という依頼として扱う。

1. 上の「作業開始時の手順」を実行する
2. `progress.md`が「Phase 0：Git・クラウド初期化（未着手）」であることを確認する
3. `.codex/flow.md`の「Phase 0」Step 1から開始する

すでにPhase 0が開始・完了しているプロジェクトで`/start`が来た場合は、フェーズや
進捗をリセットしない。現在地を報告し、次のアクションから再開する。

## オーケストレーション

重い作業は次のカスタムエージェントへ委譲する。
メインは成果物を自分でも確認し、報告を鵜呑みにしない。

| エージェント | 担当 |
|---|---|
| `researcher` | 市場・競合・技術的実現可能性の調査 |
| `design-writer` | 設計書と README の作成・更新 |
| `mock-builder` | UIモックの実装と視覚確認 |
| `detailed-designer` | 詳細設計 |
| `consistency-checker` | 設計書とモックの整合性確認 |
| `implementer` | 本実装とリファクタリング |
| `tester` | 総合テストとテストレポート |
| `code-reviewer` | 設計書に基づくコードレビュー |
| `debugger` | 証拠ベースの原因特定と修正 |
| `deployer` | 承認済みの本番デプロイ |

委譲時は、タスク、参照ファイル、確定事項、出力先、完了条件を明記する。
サブエージェントが不明点を返した場合は、`progress.md` の
「未回答の要確認事項」へ記録し、ユーザーにまとめて確認する。

`progress.md` はメインだけが更新する。
設計書、実装、テスト等を同時編集する可能性がある委譲は並列実行しない。

## フェーズ開始位置

| 状態 | 開始位置 |
|---|---|
| Git未初期化・Phase 0未完了のいずれか | Phase 0（Git・クラウド初期化） |
| Phase 0完了後にGitHub・夜間実行を後から有効化する | Phase 0 Step 4〜6のみ再実行 |
| Phase 0完了後、`progress.md` に次のアクションあり | そこから再開 |
| Phase 0完了・設計書なし | Phase 1（調査） |
| 基本設計が未完了 | Phase 2（設計） |
| 基本設計完了・UIモックなし | Phase 3（UIあり）または Phase 5（UIなし） |
| モック完了・詳細設計なし | Phase 5（詳細設計） |
| 詳細設計完了・整合性チェック未実施 | Phase 6（整合性チェック） |
| 整合性チェック承認済み | Phase 7（実装） |
| 実装済み・品質ループ未完了 | Phase 7（品質ループ） |
| デプロイのみ | Phase 8（デプロイ） |

## 絶対ルール

1. 設計書にないものを実装しない。機能変更は設計書を先に更新する
2. 不明、曖昧、矛盾がある場合は推測せず、ユーザーへまとめて確認する
3. 設計書や README を作成・更新したら、ユーザー承認後に次へ進む
   - 例外1：`progress.md` と一時レポートは承認不要
   - 例外2：Phase 6 の自動修正は最終レポートでまとめて承認を得る
4. スキルやフェーズ順を外れる場合は、理由とトレードオフを示して事前確認する
5. Phase 7 は全テスト PASS、コードレビューの必須修正ゼロまで完了扱いにしない
6. Phase 8でREADMEを作成した後は、更新トリガーに該当する変更をコミット前にREADMEへ反映する
7. バグ修正は `debugging-approach` と `debug-runner` に従い、原因の証拠を得てから着手する
8. 新機能・新アプローチは `pre-implementation-check` で実現可能性を検証する
9. `progress.md` はコミットより前に更新し、作業結果と同じコミットへ含める
10. 夜間・クラウド作業は `codex/*` ブランチで行い、main へ直接反映しない
11. Codex のコミットはプロジェクトルートから単独の `git commit` として実行する。
    `cd ... && git commit`、`bash -c`、複数コミットの連結、`--git-dir`、`--work-tree` は使わない

## 承認が必要な操作

次の操作はユーザーの明示承認を得るまで実行しない。

- ファイル削除
- GitHub リポジトリの作成・公開範囲の変更
- 初回 `git push`
- main への `git push`、PR のマージ
- Phase 0 で事前許可されていないブランチへの `git push` と PR 作成
- `git push --force`（事前許可の対象外。常に禁止）
- 本番デプロイ
- 本番DBの変更・削除

ローカルコミットは自動実行してよい。
Phase 0 でユーザーが対象リポジトリと `codex/*` ブランチを明示し、
継続的な Push・PR 作成を事前許可した場合に限り、その範囲は再確認なしで実行してよい。
許可の有無は `progress.md` の「Git・クラウドの状態」に記録する。
秘密情報をコード、ログ、コミットへ含めない。

## README の最新化

README は requirements / architecture / setup / business から作る派生成果物とする。
更新トリガーと手順は `.codex/flow.md` の
「README の最新化ルール【全フェーズ共通】」に従う。

README の作成・更新は `design-writer` に委譲し、
`readme-writer` の後に `humanizer-ja` を必ず使用する。

## Phase 0・初回コミット前の規則

1. `AGENTS.md`、`progress.md`、`.codex/` が `.gitignore` 対象外で、Git 管理されることを確認する
2. `.env`、秘密鍵、認証情報、一時レポート、`.codex/eval/results/` が Git 管理から除外されることを確認する
3. `git diff --cached` と `git status --short` で秘密情報と意図しないファイルがないことを確認する
4. README は Phase 8 で設計書から初回作成する。Phase 0 の初回コミットでは必須にしない
5. GitHub リポジトリは非公開を既定とし、作成・初回 Push はユーザー承認後に行う

## 詳細情報

| 参照先 | 内容 |
|---|---|
| `progress.md` | 現在地、決定事項、未回答事項、次のアクション |
| `.codex/flow.md` | 各フェーズの詳細手順 |
| `.codex/agents/*.toml` | カスタムエージェント定義 |
| `.codex/capabilities.md` | スキルと Codex 機能の使い分け |
| `.codex/quality-rules.md` | 品質・セキュリティルール |
