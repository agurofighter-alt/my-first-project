# Jump Desktop 解像度トラブルシューティング

## 環境

| デバイス | モデル | ネイティブ解像度 | アスペクト比 |
|---------|--------|----------------|-------------|
| MacBook Pro 13" | M1/M2 | 2560x1600 | 16:10 |
| iPad Pro 13" | M1/M2/M4 | 2732x2048 | 4:3 |

## 問題

MacBookの画面共有（Screen Sharing）を使用した後、iPadからJump Desktopで接続すると:
- 解像度が低くなる
- アスペクト比がおかしい（黒帯が出る、引き伸ばされる）
- 画面が小さく表示される（余白が多い）

## 原因

1. macOSの画面共有が接続元デバイスに合わせて解像度を変更する
2. 画面共有を切断しても、変更された解像度がそのまま残る
3. Jump DesktopのFluidプロトコルがiPad Pro 13"の4:3に合わせようとするが、既に変更された解像度を基準にするため正しく調整できない
4. MacBook Pro 13"（16:10）とiPad Pro 13"（4:3）のアスペクト比の違いが問題を悪化させる

## 解決方法

### 方法1: Jump Desktop の設定を変更する（最も簡単・推奨）

**iPad側:**
1. Jump Desktop アプリを開く
2. 接続先の横にある「i」ボタンをタップ
3. 「編集」をタップ
4. ディスプレイセクション → **「解像度を変更」を無効にする**

**Mac側 (Jump Desktop Connect):**
1. 接続アイコンを右クリック → 「編集」
2. ディスプレイセクション → **Resolution を「Same as remote computer」に設定**

### 方法2: 修正スクリプトを使う

```bash
# displayplacer をインストール（初回のみ）
brew install displayplacer

# デフォルト解像度 (2560x1600) に戻す
./fix-resolution.sh

# 現在のディスプレイ情報を確認
./fix-resolution.sh --list

# カスタム解像度を指定
./fix-resolution.sh 1440x900
```

### 方法3: 手動でシステム設定から変更する

1. **システム設定** > **ディスプレイ** を開く
2. 解像度で「デフォルト」を選択、または適切な解像度を手動で選ぶ

### 方法4: BetterDisplay で仮想ディスプレイを作成する

iPad Pro 13"の4:3比率に最適化したい場合:
1. [BetterDisplay](https://github.com/waydabber/BetterDisplay) をインストール
2. 仮想ディスプレイを作成（例: 1920x1440 = 4:3）
3. Jump Desktop でその仮想ディスプレイに接続

## 予防策

- **画面共有前にJump Desktopの「解像度を変更」を無効にしておく**
- 画面共有終了後はシステム設定でディスプレイの解像度を確認する
- 可能であれば、画面共有の代わりにJump Desktopだけを使用する

## 参考リンク

- [How do I prevent Jump from changing my screen resolution? - Jump Desktop Support](https://support.jumpdesktop.com/hc/en-us/articles/360036955511)
- [Fluid: Black bars on the side of the screen - Jump Desktop Support](https://support.jumpdesktop.com/hc/en-us/articles/360041534252)
- [Full resolution Jump Desktop on iPad Pro using SwitchResX](https://storck.io/posts/jump-desktop-ipad-pro-11-inch-full-screen/)
- [Poor support for 4:3 remote screen such as iPad Pro 13" - Jump Desktop Community](https://support.jumpdesktop.com/hc/en-us/community/posts/41339235469837)
