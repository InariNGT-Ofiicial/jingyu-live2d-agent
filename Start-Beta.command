#!/bin/sh
# Double-click launcher for macOS (the counterpart of Start-Beta.cmd).
# The model directory is remembered in .local/model-path.txt after the first run.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3。请安装 Python 3.10 或更新版本（brew install python@3.12）后重试。"
  exit 1
fi
python3 launch.py "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo
  echo "启动失败（退出码 $status）。请检查 logs/server-error.log。"
fi
exit "$status"