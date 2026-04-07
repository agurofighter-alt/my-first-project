# Jump Desktop 解像度トラブルシューティング

## 構成

```
Mac mini M4 (母艦・ヘッドレス)
  ├── iPad Pro 13" (Jump Desktop) ← 優先: 余白なしで使いたい
  └── MacBook Pro 13" (macOS画面共有) ← 余白あってもOK
```

| デバイス | 役割 | 接続方法 | アスペクト比 | 優先度 |
|---------|------|---------|-------------|-------|
| Mac mini M4 | 母艦 | - | - | - |
| iPad Pro 13" | メイン操作 | Jump Desktop (Fluid) | 4:3 | **高（余白なし）** |
| MacBook Pro 13" | サブ操作 | macOS画面共有 | 16:10 | 低（余白OK） |

## 問題

MacBookからmacOS画面共有でMac miniに接続した後、iPadのJump Desktopで解像度がおかしくなる。

## 原因

1. MacBookからmacOS画面共有すると、Mac miniの仮想ディスプレイ解像度がMacBookの**16:10**に変更される
2. 画面共有を切断しても、変更された解像度がMac miniに**そのまま残る**
3. その後iPadからJump Desktopで繋ぐと、16:10の解像度を基準にするため、iPad Pro 13"の**4:3**に正しく合わない

## 解決方法

### 方法1: 修正スクリプトでiPad向け解像度に戻す

Mac miniで実行:

```bash
# displayplacer をインストール（初回のみ）
brew install displayplacer

# iPad Pro 13" 向け 4:3 解像度 (2048x1536) に設定
./fix-resolution.sh

# 現在のディスプレイ情報を確認
./fix-resolution.sh --list

# 別の4:3解像度を指定する場合
./fix-resolution.sh 1920x1440
```

### 方法2: Jump Desktop の設定を変更する

**iPad側 (Jump Desktop アプリ):**
1. 接続先の横にある「i」ボタンをタップ
2. 「編集」をタップ
3. ディスプレイ → **「解像度を変更」を有効にする**
4. iPad Pro 13" の4:3に自動調整させる

> ※ ただし画面共有後に解像度が変わっている場合、これだけでは直らないことがある

### 方法3: BetterDisplay で4:3仮想ディスプレイを固定する（根本的解決）

Mac miniにBetterDisplayをインストールして、iPad用の4:3仮想ディスプレイを常設する:

1. [BetterDisplay](https://github.com/waydabber/BetterDisplay) をインストール
2. 4:3の仮想ディスプレイを作成（例: 2048x1536）
3. Jump Desktop でその仮想ディスプレイに接続
4. MacBookの画面共有が解像度を変えても、仮想ディスプレイは影響を受けない

### 方法4: 手動でシステム設定から変更

Mac mini にVNCまたはJump Desktopで接続して:
1. **システム設定** > **ディスプレイ** を開く
2. 4:3の解像度を手動で選択する

## 予防策

- MacBookの画面共有を使った後は、`./fix-resolution.sh` を実行して解像度を戻す
- BetterDisplay で仮想ディスプレイを固定すれば、画面共有の影響を受けなくなる（最も確実）
- 可能であればMacBookからもJump Desktopで接続する（画面共有を使わない）

## 参考リンク

- [How do I prevent Jump from changing my screen resolution? - Jump Desktop Support](https://support.jumpdesktop.com/hc/en-us/articles/360036955511)
- [Fluid: Black bars on the side of the screen - Jump Desktop Support](https://support.jumpdesktop.com/hc/en-us/articles/360041534252)
- [Poor support for 4:3 remote screen such as iPad Pro 13" - Jump Desktop Community](https://support.jumpdesktop.com/hc/en-us/community/posts/41339235469837)
- [Full resolution Jump Desktop on iPad Pro using SwitchResX](https://storck.io/posts/jump-desktop-ipad-pro-11-inch-full-screen/)
