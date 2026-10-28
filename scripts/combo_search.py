#!/usr/bin/env python3
"""组合关键词搜索：查找包含目标关键词、且同时包含任一备选关键词的文件

即匹配条件为: target_keyword AND (or_keywords[0] OR or_keywords[1] OR ...)

所有个人化配置（关键词、盘符、输出文件）均在项目根目录 `config.toml` 的
[combo_search] 节中维护，请参考 config.example.toml。运行方式（项目根目录下）：

    python scripts/combo_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anytxt import AnytxtClient, AnytxtError, load_config


def main() -> int:
    combo = load_config().get("combo_search", {})

    target_keyword = combo.get("target_keyword")
    or_keywords = combo.get("or_keywords") or []
    drives = combo.get("drives") or ["C:/"]
    output_file = combo.get("output_file", "combo_search_result.txt")

    if not target_keyword or not or_keywords:
        print("错误: 请先在 config.toml 的 [combo_search] 节配置 "
              "target_keyword 和 or_keywords（参考 config.example.toml）")
        return 1

    client = AnytxtClient()
    all_results = {}

    try:
        for drive in drives:
            target_files = client.get_result_all(target_keyword, drive)

            or_files = set()
            for kw in or_keywords:
                or_files |= client.get_result_all(kw, drive)

            all_results[drive] = sorted(target_files & or_files)
    except AnytxtError as e:
        print(f"错误: {e}")
        return 1

    total = sum(len(v) for v in all_results.values())

    lines = [
        '关键词: (' + '|'.join(or_keywords) + ') AND ' + target_keyword,
        '搜索范围: ' + ', '.join(drives),
        '同时包含所有关键词的文件总数: ' + str(total),
        '=' * 80,
        ''
    ]

    for drive, files in all_results.items():
        if files:
            lines.append(f'--- {drive} ({len(files)} 个文件) ---')
            lines.extend(files)
            lines.append('')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'结果已保存到: {output_file}')
    print(f'总计: {total} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
