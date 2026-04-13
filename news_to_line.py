#!/usr/bin/env python3
"""
news_to_line.py
RSSフィード・Google Newsキーワード検索・X(Twitter)トレンドを取得し、
LINE Messaging API でプッシュ送信するスクリプト。

設定の読み込み順:
  1. ~/Documents/news_config.json  （ローカル実行 / launchd）
  2. 環境変数                       （GitHub Actions）
     LINE_CHANNEL_ACCESS_TOKEN
     LINE_USER_ID
     FEEDS_CONFIG_PATH  （任意: feeds_config.json のパスを上書き）

フィードの type:
  "rss"          - 通常の RSS/Atom フィード
  "google_news"  - Google News キーワード検索 RSS（query フィールド必須）
  "x_trends"     - X(Twitter) 日本トレンド（URL 不要）
"""
import json
import os
import sys
import traceback
import urllib.parse
from datetime import datetime
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("[ERROR] feedparser がインストールされていません。\n  pip install feedparser", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] requests がインストールされていません。\n  pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] beautifulsoup4 がインストールされていません。\n  pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

_LOCAL_CONFIG = Path.home() / "Documents" / "news_config.json"
_FEEDS_CONFIG  = Path(__file__).parent / "feeds_config.json"
_BROWSER_UA    = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ─────────────────────────────────────────────
# 設定読み込み
# ─────────────────────────────────────────────

def load_config() -> tuple[str, str, list]:
    """(token, user_id, feeds) を返す。ローカルファイル → 環境変数の順に試みる。"""

    # ① ローカル設定ファイル
    if _LOCAL_CONFIG.exists():
        with open(_LOCAL_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        token   = cfg.get("line_channel_access_token", "").strip()
        user_id = cfg.get("line_user_id", "").strip()
        feeds   = cfg.get("feeds", [])
        if feeds:
            return token, user_id, feeds

    # ② 環境変数（GitHub Actions）
    token   = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()

    feeds_path = Path(os.environ.get("FEEDS_CONFIG_PATH", str(_FEEDS_CONFIG)))
    if feeds_path.exists():
        with open(feeds_path, encoding="utf-8") as f:
            feeds = json.load(f)
    else:
        feeds = []

    if not token:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN が設定されていません。", file=sys.stderr)
        sys.exit(1)
    if not user_id:
        print("[ERROR] LINE_USER_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)
    if not feeds:
        print("[ERROR] feeds が1件も設定されていません。", file=sys.stderr)
        sys.exit(1)

    return token, user_id, feeds


# ─────────────────────────────────────────────
# 取得関数
# ─────────────────────────────────────────────

def fetch_rss(url: str, max_items: int = 5) -> list:
    feed = feedparser.parse(url)
    return [
        {"title": e.get("title", "（タイトルなし）"), "link": e.get("link", "")}
        for e in feed.entries[:max_items]
    ]


def fetch_google_news(query: str, max_items: int = 5) -> list:
    url = (
        "https://news.google.com/rss/search"
        f"?q={urllib.parse.quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    )
    return fetch_rss(url, max_items)


def fetch_x_trends(max_items: int = 10) -> list:
    resp = requests.get(
        "https://trends24.in/japan/",
        headers={"User-Agent": _BROWSER_UA},
        timeout=15,
    )
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    card = soup.find("ol", class_="trend-card__list")
    if not card:
        return []
    return [
        {
            "title": li.get_text(strip=True),
            "link": "https://twitter.com/search?q="
                    + urllib.parse.quote(li.get_text(strip=True)),
        }
        for li in card.find_all("li")[:max_items]
    ]


# ─────────────────────────────────────────────
# メッセージ整形
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# LINE 送信
# ─────────────────────────────────────────────

def send_line(token: str, user_id: str, message: str) -> None:
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"to": user_id, "messages": [{"type": "text", "text": message}]},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"LINE API エラー {resp.status_code}: {resp.text}")


# ─────────────────────────────────────────────
# JSON 保存（ホームページ用アーカイブ）
# ─────────────────────────────────────────────

MAX_HISTORY = 200  # 保持する最大エントリ数（約22日分）


def collect_data(feeds: list, now: datetime) -> dict:
    """各フィードのデータを dict 形式で収集して返す"""
    entry: dict = {"ts": now.strftime("%Y-%m-%dT%H:%M:%S"), "feeds": []}
    for feed_cfg in feeds:
        name      = feed_cfg.get("name", "フィード")
        max_items = int(feed_cfg.get("max_items", 5))
        feed_type = feed_cfg.get("type", "rss")
        section   = {"name": name, "items": []}
        try:
            if feed_type == "google_news":
                items = fetch_google_news(feed_cfg.get("query", name), max_items)
            elif feed_type == "x_trends":
                items = fetch_x_trends(max_items)
            else:
                items = fetch_rss(feed_cfg["url"], max_items)
            section["items"] = items
        except Exception as exc:
            section["error"] = str(exc)
        entry["feeds"].append(section)
    return entry


def save_news_json(entry: dict, path: Path) -> None:
    """news.json にエントリを追記し、MAX_HISTORY 件を超えた古いものを削除する"""
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(entry)
    history = history[-MAX_HISTORY:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON 保存: {path} ({len(history)} 件)")


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────

def main() -> None:
    token, user_id, feeds = load_config()
    now = datetime.now()

    # データ収集（JSON 保存と LINE 送信で共用）
    entry   = collect_data(feeds, now)

    # LINE メッセージ: タイトルのみ（リンクは省略。URL が長く5000字制限に引っかかるため）
    LINE_MAX = 4900
    message = f"📰 {now.strftime('%Y/%m/%d %H:%M')} のニュース"
    for section in entry["feeds"]:
        block = f"\n\n【{section['name']}】"
        if section.get("error"):
            block += f"\n  （取得失敗）"
        elif not section["items"]:
            block += "\n  （記事なし）"
        else:
            for i, item in enumerate(section["items"], 1):
                block += f"\n  {i}. {item['title']}"
        # 5000字を超えそうな場合はそのカテゴリを追加しない
        if len(message) + len(block) > LINE_MAX:
            message += "\n\n（以降は省略 — ウェブサイトで全件閲覧できます）"
            break
        message += block

    print(message)
    print()

    # JSON 保存（NEWS_DATA_PATH が設定されている場合）
    data_path = os.environ.get("NEWS_DATA_PATH", "")
    if data_path:
        save_news_json(entry, Path(data_path))

    # LINE 送信
    send_line(token, user_id, message)
    print(f"[OK] LINE 送信完了 ({now.strftime('%Y-%m-%d %H:%M:%S')})")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
