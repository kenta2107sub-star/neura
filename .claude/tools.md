# スキル・プラグイン一覧（.claude/tools.md）

---

## スキル一覧

スキルは `~/.claude/skills/` に配置されている。

| スキル名 | 用途 | 使うフェーズ |
|---|---|---|
| requirements-writer | 要件定義書の作成 | Phase 2 |
| architecture-writer | アーキテクチャ設計書の作成 | Phase 2 |
| setup-writer | セットアップガイドの作成 | Phase 2 |
| business-writer | ビジネス・運用ドキュメントの作成 | Phase 2 |
| basic-design-writer | 基本設計書の作成 | Phase 2 |
| detailed-design-writer | 詳細設計書の作成 | Phase 4 |
| mock-frontend-design | UIモックの実装 | Phase 3 |
| implementation-runner | 本実装の実施 | Phase 5・6 Step A |
| testing-runner | 総合テストの実施 | Phase 5・6 Step B |
| debug-runner | バグの特定・修正 | Phase 5・6 Step C / 随時 |
| deployment-runner | 本番環境へのデプロイ | Phase 7 |
| code-reviewer | コード品質のレビュー（独立エージェント） | Phase 5・6 Step D |
| refactoring-runner | コード構造の改善 | 随時 |
| readme-writer | README.mdの生成 | デプロイ前 |

### 補助スキル（状況に応じて使用）

| スキル名 | 用途 | 使うタイミング |
|---|---|---|
| `incremental-implementation` | 段階的な実装（小さく確実に進める） | Phase 5 Step A：実装が大きく複雑な場合 |
| `doubt-driven-development` | 不確実性を明示しながら実装 | Phase 5 Step A：不慣れなコード・高リスクな箇所 |
| `source-driven-development` | ドキュメントに基づいた実装 | Phase 5 Step A：外部ライブラリを多用する場合 |
| `context-engineering` | コンテキストの構造化・最適化 | Phase 4・5：複雑な仕様を扱う前 |
| `api-and-interface-design` | APIインターフェース設計 | Phase 4：APIエンドポイント設計時 |
| `frontend-ui-engineering` | UIコンポーネント設計・実装 | Phase 3・5：UI実装時 |
| `browser-testing-with-devtools` | DevToolsを活用したブラウザテスト | Phase 5 Step B：Web UIのテスト時 |
| `code-simplification` | コードの複雑さを削減 | Phase 5 Step C.5：リファクタリング時（refactoring-runnerと併用） |
| `security-and-hardening` | セキュリティ強化・脆弱性対策 | Phase 5 Step D：セキュリティが重要な実装後 |
| `performance-optimization` | パフォーマンス改善 | Phase 5 Step C.5・デプロイ後：速度問題が発生した場合 |
| `git-workflow-and-versioning` | Gitブランチ戦略・コミット管理 | Phase 5・7：Git操作が複雑な場合 |
| `ci-cd-and-automation` | CI/CDパイプライン構築 | Phase 7：自動化が必要な場合 |
| `observability-and-instrumentation` | ログ・メトリクス・アラート設計 | Phase 7：本番運用準備時 |
| `deprecation-and-migration` | 廃止・移行作業 | 既存システムの移行プロジェクト時 |

---

## プラグイン使用タイミング

| プラグイン | 役割 | 使うフェーズ |
|---|---|---|
| `frontend-design` | UI設計・デザイントークン支援 | Phase 3（モック実装） |
| `typescript-lsp` | TypeScript型チェック・補完 | Phase 5（実装）・リファクタリング時 |
| `security-guidance` | セキュリティ脆弱性の検出 | Phase 5（実装）・Phase 6（コードレビュー） |
| `code-review` | 静的解析によるコード品質チェック | Phase 6（コードレビュー・独立エージェント内） |
| `context7` | ライブラリ・フレームワークの最新ドキュメントをリアルタイムで取得 | Phase 2（設計）・Phase 4（詳細設計）・Phase 5（実装） |
