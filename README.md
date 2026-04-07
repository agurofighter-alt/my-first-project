# Kindle自動キャプチャ

Kindleアプリのページを自動キャプチャし、OCR（日本語+英語）とPDF生成を行うツール。

## セットアップ（Mac mini）

```bash
./setup.sh
```

## 実行

```bash
source venv/bin/activate

# 基本実行（全ページ）
python3 kindle_capture.py

# ページ数指定
python3 kindle_capture.py --pages 50

# 既存スクリーンショットにOCRのみ実行
python3 kindle_capture.py --ocr-only <フォルダ>

# 既存スクリーンショットからPDFのみ生成
python3 kindle_capture.py --pdf-only <フォルダ>
```

## 設計

- **ページ送り**: 右矢印キー。送信前にKindle最前面か確認、失敗時はactivate→ダメなら停止
- **ループ**: スクショ → 同一ページ検知 → OCR → ページ確定 → ページ送り
- **終了検知**: OCRで「amazonでこの本をレビュー」/ 同一画像3連続 / Ctrl+C
- **フォーカス保全**: 50ページごとに再activate。`screencapture -x -o -R`はフォーカス非奪取
- **ウィンドウ**: fullscreen不可（`window 1`が消える）。`set size {9999,9999}`で最大化。bounds下限400x300でダイアログ排除
- **プロセス排他**: PIDロック（アトミック作成、stale自動回収）
- **PDF生成**: 25ページずつチャンク→Swift PDFKitで結合
- **OCR結果**: 逐次ファイル追記。`--ocr-only`はtmpに書いてatomic replace
- **OCR読み順**: Y→Xソート。単一カラム前提
