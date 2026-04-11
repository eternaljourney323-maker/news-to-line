# news-to-line

RSSフィードのニュースを取得し、LINE Messaging API で送信するスクリプトです。

## セットアップ手順

### 1. ライブラリをインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルを作成

`news_config.json.example` を `~/Documents/news_config.json` にコピーして編集します。

```bash
cp news_config.json.example ~/Documents/news_config.json
```

`~/Documents/news_config.json` を開き、以下を入力してください：

| 項目 | 説明 |
|------|------|
| `line_channel_access_token` | LINE Developers で取得した Channel Access Token |
| `line_user_id` | 送信先ユーザーの LINE User ID |
| `feeds` | 取得する RSS フィードの一覧 |

#### LINE の設定値の取得方法

1. [LINE Developers Console](https://developers.line.biz/console/) にログイン
2. Messaging API チャンネルを開く
3. **Messaging API 設定** タブ → **Channel access token** をコピー
4. User ID は **チャンネル基本設定** タブ → **あなたのユーザーID**

### 3. 動作確認（手動実行）

```bash
cd "/Users/kt/Cursor/仕事/スクリプト・一時作業/news-to-line"
python3 news_to_line.py
```

ターミナルにニュース一覧が表示され、LINE にメッセージが届けば成功です。

---

## 自動実行（launchd）のセットアップ

### 4. plist を設置

```bash
PROJECT_ROOT="/Users/kt/Cursor/仕事/スクリプト・一時作業/news-to-line"

sed "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
  launchers/com.news.line-notify.plist.example \
  > ~/Library/LaunchAgents/com.news.line-notify.plist
```

### 5. シェルラッパーに実行権限を付与

```bash
chmod +x run_news_to_line.sh
```

### 6. launchd に読み込む

```bash
launchctl load ~/Library/LaunchAgents/com.news.line-notify.plist
```

毎日 7:00 に自動実行されます（`com.news.line-notify.plist.example` の `Hour` を変更すると時間を調整できます）。

### 確認・停止

```bash
# 状態確認
launchctl list | grep com.news

# 手動トリガー（テスト）
launchctl start com.news.line-notify

# 停止・削除
launchctl unload ~/Library/LaunchAgents/com.news.line-notify.plist
```

---

## ログ

- **`news_to_line.log`** — スクリプトの実行ログ（追記式）
- **`launchd_stdout.log` / `launchd_stderr.log`** — launchd 経由の実行ログ
