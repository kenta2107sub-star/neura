# Neura Codex Cloudセットアップ

## 状態

| 項目 | 状態 |
|---|---|
| セットアップ手順 | 作成済み |
| CodexとGitHubの接続 | 未確認 |
| Cloud environment | 未作成・未確認 |
| Cloud上のテスト | 未実行 |

このファイルはCloud environmentへ自動適用される設定ファイルではない。
以下の内容をCodexのEnvironment settingsへ手動で反映する。

## 対象

| 項目 | 値 |
|---|---|
| Repository | `kenta2107sub-star/neura` |
| Default branch | `main` |
| Cloud作業ブランチ | `codex/{日付}-{短いタスク名}` |
| 前提 | このファイルを含むコミットがGitHubへPush済みであること |

mainへの直接Push、PRのマージ、本番デプロイはCloud taskへ含めない。

## ランタイム

| Runtime | 設定 | 根拠 |
|---|---|---|
| Python | `3.11`へ固定 | `.github/workflows/*.yml`と設計書がPython 3.11を指定 |
| Node.js | リポジトリで未固定 | JavaScriptテストは組み込み`node:test`だけを使用 |

Environment settingsの「Set package versions」でPython 3.11を選択する。
Node.jsは初回taskで`node --version`とテスト成功を確認する。
失敗した場合は、Cloud側で利用可能なNode.jsを固定して再実行する。

## Setup方式

Manual setup scriptを使用する。

理由：Python依存は`requirements.txt`で導入できるが、
テストに必要な`pytest`が製品依存へ含まれていないため。

Environment settingsのSetup scriptへ次を貼り付ける。

```bash
set -euo pipefail

python -m pip install -r requirements.txt
python -m pip install pytest
```

このスクリプトは非対話で再実行できる。
`.env`作成、production DB操作、外部サービス呼び出しは行わない。

## Maintenance script

キャッシュ再開時に依存関係を同期するため、次を設定する。

```bash
set -euo pipefail

python -m pip install -r requirements.txt
python -m pip install pytest
```

## 環境変数とSecrets

通常のCloud開発と単体テストでは、環境変数とSecretsは登録しない。

| 名前 | 分類 | Cloudでの扱い |
|---|---|---|
| `GEMINI_API_KEY` | 本番資格情報 | 登録しない。単体テストではmockを使用 |
| `DISCORD_WEBHOOK_URL` | 本番資格情報 | 登録しない。単体テストではmockを使用 |
| `GITHUB_TOKEN` | GitHub Actions用 | 登録しない |
| GitHub PAT | ブラウザ設定画面用 | 登録しない |
| `GITHUB_REPOSITORY` | 実行環境情報 | 通常の単体テストでは不要 |

Codex CloudのSecretsはsetup scriptでだけ利用でき、
agent phase開始前に取り除かれる。
本番資格情報をagent phase用の環境変数として登録しない。

## Agent internet access

初期設定は`Off`とする。

依存導入中のsetup scriptにはインターネットアクセスがある。
標準テストは外部APIをmockするため、agent phaseのインターネットアクセスは不要。

実際のRSS取得を調査するtaskだけは、作業範囲を確認したうえで
必要な取得先domainへ限定して一時的に許可する。
Gemini API、Discord Webhook、cron-job.org、本番GitHub Actionsを呼ぶテストは行わない。

## 初回smoke task

Cloudで次のpromptを送る。

```text
AGENTS.md、progress.md、.codex/cloud-setup.mdを読んでください。
ファイルは変更せず、PythonとNode.jsのバージョンを確認し、
python -m pytest -q と
node --test tests/test_settings_schedule_sync.mjs を実行してください。
外部APIや本番サービスは呼ばず、結果だけを報告してください。
```

期待結果：

- Pythonテスト：`81 passed`
- Node.jsテスト：`8 passed`
- 合計：`89 passed / 0 failed`
- Git差分：なし

## Cloud UIチェックリスト

1. Codexへサインインする
2. GitHubを接続し、`kenta2107sub-star/neura`へのアクセスを許可する
3. Neura用のCloud environmentを作成する
4. Python 3.11を選択する
5. Setup scriptとMaintenance scriptを登録する
6. 環境変数とSecretsを空のままにする
7. Agent internet accessを`Off`にする
8. `main`を選択し、初回smoke taskを実行する
9. `89 passed / 0 failed`とGit差分なしを確認する
10. 実開発は`codex/*`ブランチで開始する

## 未確認事項と切り分け

| 症状 | 確認箇所 |
|---|---|
| Repositoryを選択できない | CodexとGitHubの接続、リポジトリアクセス許可 |
| Python依存導入に失敗 | Python 3.11の設定、`requirements.txt`、Setup log |
| `pytest`が見つからない | Setup scriptの`python -m pip install pytest`実行結果 |
| Node.jsテストが起動しない | `node --version`、CloudのNode.js runtime設定 |
| テストが外部接続を要求する | 本番資格情報を追加せず、mock漏れを修正 |
| 古い依存状態が残る | Environment settingsからcacheをresetして再実行 |

ローカルではPython 3.11の依存環境で81件、
Node.jsで8件のテスト成功を確認済み。
Cloud environment自体は未実行なので、初回smoke taskが成功するまでは
`Cloud検証済み`とは扱わない。

## 公式資料

- [Codex Cloud](https://learn.chatgpt.com/docs/cloud)
- [Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environment)
