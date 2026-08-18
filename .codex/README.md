# Neura Codex 運用ファイル

このディレクトリは、個人開発フローを Codex で実行するためのプロジェクト設定です。

- `config.toml`：モデルとサブエージェントの設定
- `agents/`：工程別カスタムエージェント
- `hooks.json` / `hooks/`：progress.md と README の更新漏れ防止
- `flow.md`：Phase 0〜8 と運用フェーズの手順
- `capabilities.md`：利用するスキルと Codex 機能
- `quality-rules.md`：品質・セキュリティ規則

## Neura での利用開始

1. Codex で Neura のリポジトリルートを開く
2. プロジェクトローカル設定と hooks の信頼確認が表示されたら、内容を読んで承認する
3. `progress.md` で現在地と次のアクションを確認する
4. 改修依頼ごとに設計書、実装、テスト、README の順で整合性を維持する

`/start`はこの運用フローの開始キーワードである。Neura は既存プロジェクトのため、
受け取ったCodexはPhase 0へ戻さず、`progress.md`に記録された現在地から再開する。

プロジェクトを信頼しない場合、`.codex/config.toml`、カスタムエージェント、
プロジェクトローカル hooks は読み込まれません。

## Git・Codex Cloud・worktree

`AGENTS.md`、`progress.md`、`.codex/` は Git 管理する。
Codex Cloud がプロジェクト固有の指示と進捗を読み、worktree でも同じフローを再現するために必要となる。

Neura は既存のGitHubリポジトリへ接続済みである。公開範囲は変更せず、
mainへのPushはユーザー承認後に行う。`.env`、認証情報、秘密鍵、一時レポートは
引き続き`.gitignore`で除外する。

Codex Cloud を選んだ場合は、GitHub の対象リポジトリを接続し、リポジトリ用の環境を作成して使う。
依存関係・実行コマンドが Phase 2 で確定したら、Cloud の setup script と環境変数を設計書に合わせて更新する。

夜間作業は main ではなく `codex/*` ブランチで行い、完了時は PR まで作成して翌朝レビューする。
`codex/*` への Push と PR 作成を無人実行するには、Phase 0 でユーザーの継続許可を得て
`progress.md` に記録しておく。main への Push・マージ・本番デプロイは継続許可の対象外とする。

ローカル Scheduled task を使う場合は、Mac の電源とデスクトップアプリを起動したままにし、
未完了作業との衝突を避けるため専用 worktree を使用する。
