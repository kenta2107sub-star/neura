# 作業進捗

> このファイルはClaude Codeが自動的に更新する。
> セッション開始時にClaude Codeが最初に読み込むことで、前回の状態を把握できる。

---

## 現在のフェーズ

```
Phase 5・6：実装完了（ローカル検証済み）／GitHub Actions 実行テスト待ち
最終更新：2026-06-22
```

---

## 設計書の状態

- [x] `neura_requirements.md`（完了）
- [x] `neura_architecture.md`（完了）
- [x] `neura_setup.md`（完了）
- [x] `neura_business.md`（完了）
- [x] `neura_basic_design.md`（完了）
- [x] `neura_detailed_design.md`（完了）

---

## 直近の決定事項

| 日付 | 内容 |
|---|---|
| 2026-06-18 | サービス名：Neura |
| 2026-06-18 | 通知：Discord Webhook + GitHub Pages アーカイブの併用 |
| 2026-06-18 | 毎日13時（JST）= GitHub Actions cron `0 4 * * *` |
| 2026-06-18 | 情報源：HN API・Reddit JSON API・RSSフィード（Xは除外） |
| 2026-06-18 | AI要約：Gemini Flash API（無料枠） |
| 2026-06-18 | フロントエンド：バニラHTML+CSS+JS（フレームワークなし） |
| 2026-06-18 | 配信件数：5〜10件/日 |
| 2026-06-18 | 認証：なし（URL直接アクセス） |
| 2026-06-22 | FR-06（設定管理 / SCR-04）を追加。GitHub Contents APIで `config/config.json` を編集（PATはlocalStorage保存） |
| 2026-06-22 | 設定保存方式：GitHub API直接コミット（C案）／PAT無期限 |
| 2026-06-22 | 共通型定義ファイルを `types.py` → `schemas.py` に変更（標準ライブラリ衝突回避） |
| 2026-06-22 | 全設計書のFR-06連結・整合性確認を実施し不整合を解消（エラーID衝突・ソース定義不一致・config読込機構など） |
| 2026-06-24 | FR-06 拡張：実行時刻（run_hour_jst）を設定画面から変更可能に。A案（daily.yml を GitHub Contents API で書き換え）で実装。PAT に workflow スコープ追加 |

---

## ブロッカー

なし

---

## 実装済み（ローカル検証完了）

- [x] `scripts/schemas.py`・`config_loader.py`（FR-06）
- [x] `config/config.json`（デフォルト同梱）
- [x] `scripts/collect.py`（FR-01）… 実データ実行で30件取得・本文21件確認。Reddit/はてブは `.json` 不可のためRSSに変更
- [x] `scripts/summarize.py`（FR-02）… build_prompt / select_articles 単体テスト済（実API実行はActions待ち）
- [x] `scripts/notify.py`（FR-03）… payload単体テスト済（実Webhookは設定後）
- [x] `scripts/archive.py`（FR-04）… index更新ロジック単体テスト済（git pushはActions）
- [x] `.github/workflows/daily.yml`
- [x] `docs/index.html`：FR-05（fetch化）・FR-06（SCR-04設定画面・GitHub API連携）
- [x] `requirements.txt`（trafilatura 1.12.2）/ `.env.example` / `.gitignore`
- [x] `tests/`（pytest 22件 全PASS）

## 次のアクション

1. `neura_setup.md` に沿って環境準備（GitHubリポジトリ作成・Secrets登録・Pages有効化・PAT発行 §3-5）
2. `git init` → 初回コミット → push
3. GitHub Actions `workflow_dispatch` で手動実行テスト（実API: Gemini要約・Discord通知・archive push）
4. デプロイ後、設定画面（`?view=settings`）でPAT入力 → config保存の疎通確認

## 未決事項（ユーザー判断）

- `docs/data/` のサンプルデータ（example.com のダミー）：デプロイ前に削除するか、初期表示用に残すか
- `docs/index.html` の demo-bar（normal/loading/empty/error 切替）：開発用UI。本番で残すか除去するか
