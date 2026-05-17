# Camera Viewer

USBカメラの映像をプレビューし、JPEG画像として保存できるPython/Tkinter製の簡易ビューアです。

## 機能

- USBカメラの接続、切断
- ライブプレビュー
- カメラ番号、解像度、FPSの設定
- 指定枚数または無制限での画像保存
- プレビュー画像のズーム、ドラッグ移動
- 表示中画像の右クリック保存

## 動作環境

- Windows
- Python 3.10以降を想定
- USBカメラ

## セットアップ

必要なPythonパッケージをインストールします。

```powershell
pip install opencv-python pillow numpy
```

## 起動方法

以下のどちらかで起動できます。

```powershell
python main.py
```

または、Windowsで `main.bat` を実行します。

```powershell
.\main.bat
```

## 使い方

1. USBカメラをPCに接続します。
2. 必要に応じてメニューの `Settings` からカメラ番号、解像度、FPSを設定します。
3. `Open Camera` でカメラを開きます。
4. `Start Preview` でプレビューを開始します。
5. 画像を保存する場合は `Save Count` を指定して `Start Save` を押します。
6. 終了する場合は `Stop`、`Close Camera`、または `File > Exit` を使用します。

### Save Count

- `0`: 無制限に保存します。
- `1` 以上: 指定した枚数を保存すると自動で保存を停止します。

## 保存先

保存画像は `images` フォルダ配下に、保存開始時刻のフォルダ名で出力されます。

```text
images/
  YYYYMMDD_HHMMSS/
    0000.jpg
    0001.jpg
    ...
```

## プレビュー操作

- マウスホイール: ズーム
- 左ドラッグ: 表示位置の移動
- 右クリック: 表示中画像の保存、表示リセット

## 設定変更時の注意

- カメラ番号を変更する場合は、先にカメラを閉じてください。
- 解像度やFPSを変更する場合は、プレビューと保存を停止してから `Apply` してください。
- 指定した解像度がカメラ側でサポートされない場合、実際の解像度に調整されることがあります。

## トラブルシュート

### カメラが開けない

- 他のアプリがカメラを使用していないか確認してください。
- `Settings` の `Camera No` を `0`, `1`, `2` などに変更して試してください。
- カメラを抜き差ししてから再起動してください。

### 保存されない

- `Start Preview` 後に `Start Save` を押しているか確認してください。
- `images` フォルダに書き込み権限があるか確認してください。
- `Save Count` が期待した値になっているか確認してください。

## ファイル構成

```text
.
├── main.py                 # GUI本体
├── main.bat                # Windows用起動バッチ
├── src/
│   ├── camera_capture.py   # キャプチャスレッドと保存処理
│   ├── canvas.py           # プレビュー表示、ズーム、パン、右クリックメニュー
│   ├── image_info.py       # 画像変換と表示サイズ調整
│   └── usb_camera.py       # OpenCVによるUSBカメラ制御
└── images/                 # 保存画像の出力先
```
