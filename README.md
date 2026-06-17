# Pico E-ink Secretary

Raspberry Pi Pico WH とローカルLLM（Ollama）を組み合わせ、4.2インチ電子ペーパー（E-ink）に毎日の情報（天気・カレンダー・運行情報・ニュース）を配信するスマート秘書システムです。

時間帯（朝・昼・夜）や、ランダムに選ばれる「ペルソナ（プロンプト）」に応じて、AIがユーモアのあるブリーフィングテキストを自動生成します。

## 💡 特徴

- **バッテリーフレンドリー（寝坊対策）**: Picoの内蔵タイマー（LPOSC）がディープスリープ中に狂う問題を、1時間ごとの分割スリープとファイルを用いた「スタンプラリー方式」のロジックで克服。正確なスケジュール更新を実現しています。
- **マルチペルソナ**: `prompts/` 内に配置したテキストファイル（プロンプト）からランダムに人格を選択し、毎回の表示に変化を与えます。
- **高度な2値化処理**: サーバー側（ラズパイ等）でテキストを画像化（BMP）および1bit RAWデータへ厳密に変換。Pico側での描画負荷と通信量を最小限に抑えています。
- **Waveshare 4.2inch Rev2.1 対応**: 画面のかすれ問題を解消する専用ドライバを内蔵。

## 🛠 フォルダ構成

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── config_template.json    # サーバー側設定（Weather, iCal, RSSなど）のひな形
├── secretary.py            # サーバー側メインスクリプト（データ収集、LLM、画像生成）
├── pico/                   # Raspberry Pi Pico WH 側コード
│   ├── main.py             # スリープ・更新制御メインプログラム
│   ├── epaper4in2.py       # Waveshare 4.2" Rev2.1 専用ドライバ
│   └── secrets_template.py # Wi-Fi設定のひな形
└── prompts/                # AIのペルソナプロンプト（.txt）を格納
    └── idle.txt
```

## 🚀 セットアップ手順

### 1. サーバー側（ラズパイやPCなど）の準備

Ollama（ローカルLLM環境）および Python 3 が動作する環境が必要です。

1. **必要なライブラリのインストール:**
   ```bash
   pip install requests ollama feedparser beautifulsoup4 icalevents pillow
   ```
2. **設定ファイルの用意:**
   `config_template.json` を `config.json` にリネームし、お使いの OpenWeatherMap APIキーや iCal（Googleカレンダー等）のURL、使用するOllamaのモデル名を記述します。
3. **プロンプト（ペルソナ）の用意:**
   `prompts/` フォルダ内にお好みのシステムプロンプトを記述したテキストファイルを配置します。
4. **定期実行の空回し:**
   `secretary.py` を cron 等で定期実行（例: 毎時50分など）し、Webサーバーの公開ディレクトリ（例: `/var/www/html/eink/display.raw`）にデータが出力されるように設定します。

### 2. クライアント側（Raspberry Pi Pico WH）の準備

1. `pico/secrets_template.py` を `secrets.py` にリネームし、Wi-FiのSSIDとパスワードを記述します。
2. `pico/main.py` 内の `urequests.get()` のURLを、1で用意したサーバーのIPアドレス（例: `http://192.168.xx.xx:8000/...`）に書き換えます。
3. Thonny等を使用し、`pico/` フォルダ内の以下のファイルを Pico WH のルート直下に書き込みます。
   - `main.py`
   - `epaper4in2.py`
   - `secrets.py`

## ⚙️ ハードウェア構成（参考）

- **マイコン**: Raspberry Pi Pico WH
- **ディスプレイ**: Waveshare 4.2inch e-Paper Module (Rev2.1)
- **ピンアサイン (デフォルト)**:
  - BUSY -> Pin 13
  - RST  -> Pin 12
  - DC   -> Pin 8
  - CS   -> Pin 9
  - SCLK -> Pin 10
  - MOSI -> Pin 11

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は `LICENSE` ファイルを参照してください。
