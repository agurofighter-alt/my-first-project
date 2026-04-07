#!/bin/bash
# fix-resolution.sh
# Mac mini M4 (母艦・ヘッドレス) の仮想ディスプレイ解像度を
# iPad Pro 13インチ (4:3) に最適化された状態に戻すスクリプト
#
# 問題: MacBookからmacOS画面共有すると、Mac miniの仮想ディスプレイ解像度が
#       MacBookの16:10に変更され、その後iPadでJump Desktopの表示がおかしくなる
#
# 使い方:
#   ./fix-resolution.sh          # iPad Pro 13" 向け解像度 (2048x1536) に設定
#   ./fix-resolution.sh --list   # 現在のディスプレイ情報を表示
#   ./fix-resolution.sh WxH      # カスタム解像度を指定 (例: 1920x1440)

set -e

# iPad Pro 13インチに最適な4:3解像度
DEFAULT_RES="2048x1536"

show_usage() {
    echo "使い方: $0 [--list | WxH]"
    echo ""
    echo "  母艦: Mac mini M4 (ヘッドレス)"
    echo "  優先: iPad Pro 13\" (4:3) で余白なし表示"
    echo ""
    echo "オプション:"
    echo "  (なし)    iPad Pro 13\" 向け解像度 (${DEFAULT_RES}, 4:3) に設定"
    echo "  --list    現在のディスプレイ情報を表示"
    echo "  WxH       カスタム解像度を指定"
    echo ""
    echo "推奨解像度 (iPad Pro 13\" 向け, 4:3):"
    echo "  2048x1536  - 高解像度 (推奨)"
    echo "  1920x1440  - やや小さめ"
    echo "  1600x1200  - 文字を大きく表示"
    echo ""
    echo "※ MacBook Pro 13\" (16:10) からの画面共有では余白が出ますが想定通りです"
}

show_display_info() {
    echo "=== Mac mini 現在のディスプレイ情報 ==="
    system_profiler SPDisplaysDataType 2>/dev/null | grep -A 10 "Resolution\|Display Type\|Main Display" || true
    echo ""
    if command -v displayplacer &> /dev/null; then
        echo "=== displayplacer の情報 ==="
        displayplacer list
    fi
}

reset_resolution() {
    local res=$1

    echo "=== Mac mini 解像度修正 (iPad Pro 13\" 優先) ==="
    echo ""

    # Step 1: 現在の状態を確認
    echo "[1/3] 現在のディスプレイ設定を確認中..."
    current_res=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Resolution" | head -1 | sed 's/.*: //' || echo "取得できません")
    echo "  現在の解像度: ${current_res}"
    echo "  目標の解像度: ${res} (4:3, iPad Pro 13\" 向け)"
    echo ""

    # Step 2: 画面共有プロセスを確認
    echo "[2/3] 画面共有の状態を確認中..."
    if pgrep -x "screensharingd" > /dev/null 2>&1; then
        echo "  ⚠ 画面共有が実行中です"
        echo "  MacBookからの画面共有を切断してから実行することを推奨します"
        echo "  続行しますか？ (Ctrl+C で中断)"
        read -r -p "  Enter で続行... " || true
    else
        echo "  画面共有は実行されていません (OK)"
    fi
    echo ""

    # Step 3: 解像度を設定
    echo "[3/3] 解像度を設定中..."
    local width height
    width=$(echo "$res" | cut -dx -f1)
    height=$(echo "$res" | cut -dx -f2)

    if command -v displayplacer &> /dev/null; then
        echo "  displayplacer で ${res} に設定..."
        displayplacer "id:1 res:${width}x${height} scaling:on"
        echo "  完了"
    elif command -v screenresolution &> /dev/null; then
        echo "  screenresolution で ${res} に設定..."
        screenresolution set "${width}x${height}x32"
        echo "  完了"
    else
        echo "  [エラー] 解像度変更ツールが見つかりません"
        echo ""
        echo "  Mac mini にインストールしてください:"
        echo "    brew install displayplacer   (推奨)"
        echo ""
        echo "  手動で変更する場合 (VNC/Jump Desktop経由):"
        echo "    システム設定 > ディスプレイ > 解像度"
        return 1
    fi

    echo ""
    echo "=== 完了 ==="
    echo ""
    echo "iPad Pro 13\" の Jump Desktop で接続を確認してください。"
    echo "余白なしで表示されるはずです。"
    echo ""
    echo "※ MacBook Pro 13\" の画面共有では上下に余白が出ますが、"
    echo "   iPad優先の設定なので想定通りです。"
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
