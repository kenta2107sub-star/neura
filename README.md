# Neura — AI Daily Digest

毎日定刻に AI ニュースを自動収集・要約して Discord に通知し、GitHub Pages でアーカイブするシステム。

## 機能

| 機能 | 詳細 |
|---|---|
| ニュース収集 | Hacker News / Reddit / RSS（8ソース）から並列取得 |
| AI 要約・分類 | Gemini Flash API で日本語要約・カテゴリ分類 |
| Discord 通知 | Webhook で毎日ダイジェストを配信 |
| アーカイブ | GitHub Pages で過去ダイジェストを閲覧可能 |
| 設定管理 | ブラウザ上で収集設定・実行スケジュールを変更 |

## アーキテクチャ

```
GitHub Actions（定時実行）
  → collect.py    # 記事収集（HN / Reddit / RSS）
  → summarize.py  # Gemini Flash で要約・分類
  → notify.py     # Discord Webhook で通知
  → archive.py    # docs/data/ に保存 → git push
```

GitHub Pages（`docs/`）でアーカイブを公開。設定画面から GitHub Contents API 経由で `config/config.json` と実行スケジュール（`daily.yml`）を更新可能。

## セットアップ

[`design/neura_setup.md`](design/neura_setup.md) を参照。

## 技術スタック

- **Python 3.11** — asyncio / aiohttp / feedparser / trafilatura
- **GitHub Actions** — 毎日定刻実行（cron 式は設定画面で変更可能）
- **Gemini Flash API** — 無料枠（1500 req/日）
- **GitHub Pages** — バニラ HTML/CSS/JS（フレームワークなし）
