#!/usr/bin/env python3
"""
Anytxt API Client - 本地文件内容全文搜索

兼容入口：实际实现位于 anytxt 包，推荐直接使用 `python -m anytxt ...`。
保留本文件是为了兼容既有用法 `python anytxt_client.py ...`。
"""

import sys

from anytxt.cli import main

if __name__ == "__main__":
    sys.exit(main())
