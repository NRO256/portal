# NRO256 portal

NRO / Antigravity が開発・公開している Windows 10 / 11 向けの軽量ポータブル自作ソフトウェアを紹介し、GitHub Releases の最新配布ページへ案内する静的ポータルサイトです。

- 公開 URL: https://nro256.github.io/portal/
- 作成者: NRO / Antigravity
- ライセンス: MIT License

## 1. ディレクトリ構成

- `index.html`: ポータル本体（JavaScript 不使用の完全静的 HTML。`data/apps.json` から同期生成された実寸マニフェスト・カテゴリ別仕様目録を含む）
- `404.html`: 自己完結型スタイルを備えたページ未検出時案内ページ
- `css/style.css`: `@layer` 設計のスタイルシート（生成りの紙面色・墨文字・藍アクセント）
- `data/apps.json`: 掲載ソフトウェア情報の正本データ
- `images/favicon.svg`: サイトアイコン（追加のスクリーンショット画像も本フォルダへ配置）
- `scripts/sync_apps.py`: `data/apps.json` の内容を `index.html` の実寸マニフェスト・合計容量・カテゴリ別仕様目録へ反映・検証する補助スクリプト
- `tests/test_portal.py`: 同期処理・Zero-JS 構成・アクセシビリティ・セキュリティ・ローカル配信の自動テスト
- `.nojekyll`: GitHub Pages の Jekyll 自動処理を無効化するためのマーカーファイル

## 2. ソフトウェアの追加・更新方法

1. `data/apps.json` を編集し、ソフト情報やバージョン・公開URLを追加または更新します。
2. 同期スクリプトを実行して `index.html` を更新します。

```powershell
uv run python scripts/sync_apps.py
```

3. コミット前に差分がないか検証します。

```powershell
uv run python scripts/sync_apps.py --check
```

## 3. ローカル動作確認とテスト実行

`index.html` はビルドおよび JavaScript 実行不要で、ブラウザから直接開くことも、ローカル HTTP サーバーで配信確認することもできます。

```powershell
uv run python -m http.server 8000
```

自動テストおよび静的チェックは以下のコマンドで実行できます。

```powershell
uv run python -m unittest discover -s tests -v
ruff check scripts/sync_apps.py tests/test_portal.py
```

## 4. 掲載ソフトウェア一覧

- P2F (2-Pane Filer) — 2画面ファイルマネージャー
- Robocopy-GUI — Windows 標準 robocopy 安全操作 GUI
- WindowsImageBackup GUI (WIB-GUI) — システムイメージ作成・確認 GUI
- WinGet アプリセンター — WinGet パッケージ管理 GUI
- NetChecker Portable — 5段階ネットワーク診断ツール
- ポータブルCUI Wi-Fiアナライザー (`wifi_analyzer`) — Wi-Fi 電波混雑・チャネル診断ツール
