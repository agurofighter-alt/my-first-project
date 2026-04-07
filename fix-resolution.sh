#!/bin/bash
# fix-resolution.sh
# MacBook Pro 13インチの画面共有後、iPad Pro 13インチでJump Desktop接続時に
# 解像度がおかしくなる問題を修正するスクリプト
#
# 症状: 解像度が低くなる、アスペクト比がおかしい、画面が小さく表示される
# 原因: macOS画面共有がディスプレイ解像度を変更し、Jump Desktopが正しく復元できない
#
# 使い方:
#   ./fix-resolution.sh          # MacBook Pro 13" のデフォルト解像度に戻す
#   ./fix-resolution.sh --list   # 利用可能な解像度を一覧表示
#   ./fix-resolution.sh WxH      # カスタム解像度を指定 (例: 2560x1600)

set -e

# MacBook Pro 13インチのネイティブ解像度
DEFAULT_RES="2560x1600"

show_usage() {
    echo "使い方: $0 [--list | WxH]"
    echo ""
    echo "オプション:"
    echo "  (なし)    MacBook Pro 13\" のデフォルト解像度 (${DEFAULT_RES}) に戻す"
    echo "  --list    現在のディスプレイ情報と利用可能な解像度を表示"
    echo "  WxH       カスタム解像度を指定 (例: 2560x1600, 1440x900)"
    echo ""
    echo "推奨解像度:"
    echo "  2560x1600  - ネイティブ (Retinaスケーリング)"
    echo "  1440x900   - デフォルトスケーリング"
    echo "  1680x1050  - スペースを拡大"
}

show_display_info() {
    echo "=== 現在のディスプレイ情報 ==="
    system_profiler SPDisplaysDataType 2>/dev/null | grep -A 10 "Resolution\|Display Type\|Main Display" || true
    echo ""
    if command -v displayplacer &> /dev/null; then
        echo "=== displayplacer の情報 ==="
        displayplacer list
    fi
}

reset_resolution() {
    local res=$1

    echo "=== Jump Desktop 解像度修正 ==="
    echo "対象: MacBook Pro 13\" + iPad Pro 13\""
    echo ""

    # Step 1: 現在の状態を確認
    echo "[1/4] 現在のディスプレイ設定を確認中..."
    current_res=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Resolution" | head -1 | sed 's/.*: //' || echo "取得できません")
    echo "  現在の解像度: ${current_res}"
    echo "  目標の解像度: ${res}"
    echo ""

    # Step 2: 画面共有プロセスを確認・停止
    echo "[2/4] 画面共有の状態を確認中..."
    if pgrep -x "screensharingd" > /dev/null 2>&1; then
        echo "  画面共有が実行中です。停止を推奨します。"
        echo "  停止コマンド: sudo launchctl unload /System/Library/LaunchDaemons/com.apple.screensharing.plist"
    else
        echo "  画面共有は実行されていません (OK)"
    fi
    echo ""

    # Step 3: 解像度をリセット
    echo "[3/4] 解像度をリセット中..."
    local width height
    width=$(echo "$res" | cut -dx -f1)
    height=$(echo "$res" | cut -dx -f2)

    if command -v displayplacer &> /dev/null; then
        echo "  displayplacer で ${res} (Retina) に設定..."
        displayplacer "id:1 res:${width}x${height} scaling:on"
        echo "  完了"
    elif command -v screenresolution &> /dev/null; then
        echo "  screenresolution で ${res} に設定..."
        screenresolution set "${width}x${height}x32"
        echo "  完了"
    else
        echo "  [エラー] 解像度変更ツールが見つかりません"
        echo ""
        echo "  インストール方法:"
        echo "    brew install displayplacer   (推奨)"
        echo "    brew install screenresolution"
        echo ""
        echo "  手動で変更する場合:"
        echo "    システム設定 > ディスプレイ > 解像度 > 「デフォルト」を選択"
        return 1
    fi
    echo ""

    # Step 4: Jump Desktop の設定ガイド
    echo "[4/4] Jump Desktop の推奨設定"
    echo ""
    echo "  iPad側 (Jump Desktop アプリ):"
    echo "    1. 接続先の横の「i」ボタンをタップ"
    echo "    2. 「編集」をタップ"
    echo "    3. ディスプレイ > 「解像度を変更」を【無効】にする"
    echo ""
    echo "  Mac側 (Jump Desktop Connect):"
    echo "    1. 接続アイコンを右クリック > 「編集」"
    echo "    2. ディスプレイ > Resolution を「Same as remote computer」に設定"
    echo ""
    echo "=== 修正完了 ==="
}

# メイン処理
case "${1:-}" in
    -h|--help)
        show_usage
        ;;
    --list)
        show_display_info
        ;;
    "")
        reset_resolution "$DEFAULT_RES"
        ;;
    *x*)
        reset_resolution "$1"
        ;;
    *)
        echo "エラー: 不正な引数 '$1'"
        show_usage
        exit 1
        ;;
esac
