"""命令行入口

支持 `python -m anytxt ...` 以及兼容入口 `python anytxt_client.py ...`。
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from .client import AnytxtClient, DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from .config import load_config
from .exceptions import AnytxtError
from .models import (
    FragmentOptions,
    GetResultOptions,
    OCROptions,
    SearchOptions,
    SyncIndexOptions,
)

DEFAULT_DRIVES = ["C:/", "D:/", "E:/", "F:/"]


def _default_output() -> str:
    """生成默认输出文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"results_{timestamp}.txt"


def _write_report(filepath: str, content: str) -> None:
    """以 UTF-8 覆盖写入结果文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Anytxt API Client - 本地文件全文搜索工具 (结果保存到文件)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索文件数量
  python -m anytxt search "关键字" -d "C:\\"

  # 获取文件列表
  python -m anytxt results "关键字" -d "C:\\" -l 100

  # 搜索同时包含多个关键词的文件
  python -m anytxt intersect "关键词1" "关键词2"

  # 获取指定 FID 的匹配片段；加 --all 获取全部片段
  python -m anytxt fragment -f "文件FID" "关键字"

  # 同步文件夹索引
  python -m anytxt sync -f "C:\\Documents"

  # OCR识别图片
  python -m anytxt ocr -i "C:\\1.png"
        """
    )

    # 全局参数（需放在子命令之前）
    parser.add_argument("-o", "--output", type=str, default=None, help="输出文件路径 (默认: results_YYYYMMDD_HHMMSS.txt)")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，不打印状态信息")
    parser.add_argument("--url", default=None, help=f"Anytxt 服务地址 (默认: 配置文件或 {DEFAULT_BASE_URL})")
    parser.add_argument("--timeout", type=int, default=None, help=f"请求超时秒数 (默认: 配置文件或 {DEFAULT_TIMEOUT})")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # Search 命令
    search_parser = subparsers.add_parser("search", help="搜索匹配关键词的文件数量")
    search_parser.add_argument("pattern", help="搜索关键词")
    search_parser.add_argument("-d", "--dir", default="C:\\", help="搜索目录 (默认: C:\\)")
    search_parser.add_argument("-e", "--ext", default="*", help="文件扩展名过滤 (默认: *)")
    search_parser.add_argument("--begin", type=int, default=0, help="最后修改时间起始 (Unix时间戳)")
    search_parser.add_argument("--end", type=int, default=2147483647, help="最后修改时间结束 (Unix时间戳)")

    # Results 命令
    results_parser = subparsers.add_parser("results", help="获取匹配关键词的文件列表")
    results_parser.add_argument("pattern", help="搜索关键词")
    results_parser.add_argument("-d", "--dir", default="C:\\", help="搜索目录 (默认: C:\\)")
    results_parser.add_argument("-e", "--ext", default="*", help="文件扩展名过滤 (默认: *)")
    results_parser.add_argument("-l", "--limit", type=int, default=300, help="返回数量限制 (默认: 300)")
    results_parser.add_argument("--offset", type=int, default=0, help="偏移量 (默认: 0)")
    results_parser.add_argument("--begin", type=int, default=0, help="最后修改时间起始 (Unix时间戳)")
    results_parser.add_argument("--end", type=int, default=2147483647, help="最后修改时间结束 (Unix时间戳)")

    # Intersect 命令 - 搜索同时包含多个关键词的文件
    intersect_parser = subparsers.add_parser("intersect", help="搜索同时包含多个关键词的文件")
    intersect_parser.add_argument("patterns", nargs='+', help="多个搜索关键词")
    intersect_parser.add_argument("-d", "--dir", default="C:\\", help="搜索目录 (默认: C:\\，保持默认时依次搜索 C/D/E/F 盘)")
    intersect_parser.add_argument("-e", "--ext", default="*", help="文件扩展名过滤 (默认: *)")

    # Fragment 命令
    fragment_parser = subparsers.add_parser("fragment", help="获取文件的关键词匹配片段")
    fragment_parser.add_argument("-f", "--fid", required=True, help="文件ID")
    fragment_parser.add_argument("pattern", help="搜索关键词")
    fragment_parser.add_argument("--all", action="store_true", help="获取所有匹配片段 (GetFragmentAll)")

    # Sync 命令
    sync_parser = subparsers.add_parser("sync", help="同步文件夹到索引")
    sync_parser.add_argument("-f", "--folder", required=True, help="要同步的文件夹路径")

    # OCR 命令
    ocr_parser = subparsers.add_parser("ocr", help="OCR识别图片中的文本")
    ocr_parser.add_argument("-i", "--image", required=True, help="图片文件路径")

    return parser


def _cmd_search(client: AnytxtClient, args: argparse.Namespace) -> str:
    options = SearchOptions(
        pattern=args.pattern,
        filterDir=args.dir,
        filterExt=args.ext,
        lastModifyBegin=args.begin,
        lastModifyEnd=args.end,
    )
    count = client.search(options)
    return f"关键词: {args.pattern}\n目录: {args.dir}\n匹配文件数量: {count}"


def _cmd_results(client: AnytxtClient, args: argparse.Namespace) -> str:
    options = GetResultOptions(
        pattern=args.pattern,
        filterDir=args.dir,
        filterExt=args.ext,
        lastModifyBegin=args.begin,
        lastModifyEnd=args.end,
        limit=args.limit,
        offset=args.offset,
    )
    files = client.get_result(options)

    lines = [
        f"关键词: {args.pattern}",
        f"目录: {args.dir}",
        f"找到 {len(files)} 个文件:",
        "=" * 80,
    ]

    for i, record in enumerate(files, 1):
        modify_time = record.modify_time
        modify_str = modify_time.strftime('%Y-%m-%d %H:%M:%S') if modify_time else str(record.last_modify)
        lines.append(f"\n[{i}] {record.path}")
        lines.append(f"    FID: {record.fid}")
        lines.append(f"    大小: {record.size} bytes")
        lines.append(f"    修改时间: {modify_str}")

    return '\n'.join(lines)


def _default_drives() -> List[str]:
    """intersect 的默认搜索盘符，可由配置文件 [search] default_drives 覆盖"""
    drives = load_config().get("search", {}).get("default_drives")
    return list(drives) if drives else list(DEFAULT_DRIVES)


def _cmd_intersect(client: AnytxtClient, args: argparse.Namespace) -> str:
    patterns: List[str] = args.patterns
    drives = [args.dir] if args.dir != "C:\\" else _default_drives()

    all_results = {}  # drive -> set of paths

    for drive in drives:
        keyword_files = [client.get_result_all(p, drive, args.ext) for p in patterns]
        common = keyword_files[0] if keyword_files else set()
        for files in keyword_files[1:]:
            common &= files
        all_results[drive] = common

    total_count = sum(len(v) for v in all_results.values())
    lines = [
        f"关键词: {' + '.join(patterns)}",
        f"搜索范围: {', '.join(drives)}",
        f"同时包含所有关键词的文件总数: {total_count}",
        "=" * 80,
    ]

    for drive, files in all_results.items():
        if files:
            lines.append(f"\n--- {drive} ({len(files)} 个文件) ---")
            lines.extend(sorted(files))

    return '\n'.join(lines)


def _cmd_fragment(client: AnytxtClient, args: argparse.Namespace) -> str:
    options = FragmentOptions(fid=args.fid, pattern=args.pattern)
    if args.all:
        fragments = client.get_fragment_all(options)
    else:
        fragments = client.get_fragment(options)

    lines = [
        f"FID: {args.fid}",
        f"关键词: {args.pattern}",
        f"找到 {len(fragments)} 个片段:",
        "=" * 80,
    ]

    for i, frag in enumerate(fragments, 1):
        lines.append(f"\n[{i}] {frag}")

    return '\n'.join(lines)


def _cmd_sync(client: AnytxtClient, args: argparse.Namespace) -> str:
    success = client.sync_index(SyncIndexOptions(folder=args.folder))
    return f"同步文件夹: {args.folder}\n结果: {'成功' if success else '失败'}"


def _cmd_ocr(client: AnytxtClient, args: argparse.Namespace) -> str:
    text = client.ocr(OCROptions(file=args.image))
    return '\n'.join([
        f"图片文件: {args.image}",
        "=" * 80,
        "识别结果:",
        "=" * 80,
        text,
    ])


_COMMANDS = {
    "search": _cmd_search,
    "results": _cmd_results,
    "intersect": _cmd_intersect,
    "fragment": _cmd_fragment,
    "sync": _cmd_sync,
    "ocr": _cmd_ocr,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口；返回进程退出码"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    client = AnytxtClient(base_url=args.url, timeout=args.timeout)
    output_file = args.output or _default_output()

    try:
        content = _COMMANDS[args.command](client, args)
    except AnytxtError as e:
        error_msg = f"错误: {e}"
        _write_report(output_file, error_msg)
        if not args.quiet:
            print(error_msg)
        return 1

    _write_report(output_file, content)
    if not args.quiet:
        print(f"结果已保存到: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
