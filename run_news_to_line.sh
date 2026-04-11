#!/bin/zsh
# launchd から呼び出すラッパー。PATH を補完して news_to_line.py を実行する。

export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/news_to_line.log"

echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---" >> "$LOG_FILE"
python3 "$SCRIPT_DIR/news_to_line.py" >> "$LOG_FILE" 2>&1
echo "exit=$?" >> "$LOG_FILE"
