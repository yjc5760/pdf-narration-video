#!/usr/bin/env bash
# 給 macOS/Linux 使用者(bash/zsh)用的等效版本。讀取同資料夾 .env,設定環境變數,
# 執行 pipeline.py --engine azure。Windows cmd 使用者請用 run_azure.bat。
set -a
source .env
set +a
python3 pipeline.py --engine azure "$@"
