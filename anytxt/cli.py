"""命令行入口

支持 `python -m anytxt ...` 以及兼容入口 `python anytxt_client.py ...`。
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

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
from .report import format_records

DEFAULT_DRIVES = ["C:/", "D:/", "E:/", "F:/"]
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _default_output() -> str:
    """生成默认输出文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"results_{timestamp}.txt"


def _write_report(filepath: str, content: str, bom: bool = False) -> None:
    """以 UTF-8 覆盖写入结果文件；CSV 导出带 BOM 以便 Excel 直接打开"""
    encoding = 'utf-8-sig' if bom else 'utf-8'
    with open(filepath, 'w', encoding=encoding) as f:
        f.write(content)


def _default_drives() -> List[str]:
    """多盘搜索的默认盘符，可由配置文件 [search] default_drives 覆盖"""
    drives = load_config().get("search", {}).get("default_drives")
    return list(drives) if drives else list(DEFAULT_DRIVES)


def _parse_since(value: str) -> int:
    """解析 --since 时间字符串为 Unix 时间戳"""
    for fmt in TIME_FORMATS:
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except ValueError:
            continue
    raise AnytxtError(f"无法解析时间: {value}（支持格式: YYYY-MM-DD [HH:MM[:SS]]）")


def _resolve_begin(args: argparse.Namespace) -> int:
    """解析起始修改时间：--since 优先，其次 --days，最后 --begin"""
    since = getattr(args, "since", None)
    days = getattr(args, "days", None)
    if since:
        return _parse_since(since)
    if days is not None:
        return int((datetime.now() - timedelta(days=days)).timestamp())
    return args.begin


def _add_time_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--begin", type=int, default=0, help="最后修改时间起始 (Unix时间戳)")
    parser.add_argument("--end", type=int, default=2147483647, help="最后修改时间结束 (Unix时间戳)")
    parser.add_argument("--since", default=None, help="最后修改时间起始，如 2025-01-01 或 '2025-01-01 08:30'（覆盖 --begin）")
    parser.add_argument("--days", type=int, default=None, help="只查最近 N 天修改的文件（覆盖 --begin）")


def _add_scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-d", "--dir", default="C:\\", help="搜索目录 (默认: C:\\，集合运算命令保持默认时按配置跨盘搜索)")
    parser.add_argument("-e", "--ext", default="*", help="文件扩展名过滤 (默认: *)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Anytxt API Client - 本地文件全文搜索工具 (结果保存到文件)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索文件数量（只看最近 30 天修改的）
  python -m anytxt search "关键字" -d "C:\\" --days 30

  # 获取文件列表，导出为 CSV
  python -m anytxt results "关键字" -d "C:\\" -l 100 --format csv

  # 文件列表并附带命中片段预览
  python -m anytxt results "关键字" -d "C:\\" -l 10 --with-fragment

  # 搜索同时包含全部关键词的文件
  python -m anytxt intersect "关键词1" "关键词2"

  # 搜索匹配任一关键词的文件
  python -m anytxt union "关键词1" "关键词2"

  # 搜索包含主关键词但不含排除词的文件
  python -m anytxt exclude "主关键词" "排除词1" "排除词2"

  # 获取指定 FID 的匹配片段；加 --all 获取全部片段
  python -m anytxt fragment -f "文件FID" "关键字"

  # 打开文件 / 在资源管理器中定位
  python -m anytxt open "D:\\path\\file.pdf"
  python -m anytxt open --select "D:\\path\\file.pdf"

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
    _add_scope_args(search_parser)
    _add_time_args(search_parser)

    # Results 命令
    results_parser = subparsers.add_parser("results", help="获取匹配关键词的文件列表")
    results_parser.add_argument("pattern", help="搜索关键词")
    _add_scope_args(results_parser)
    results_parser.add_argument("-l", "--limit", type=int, default=300, help="返回数量限制 (默认: 300，服务端单页上限约 300)")
    results_parser.add_argument("--offset", type=int, default=0, help="偏移量 (默认: 0)")
    results_parser.add_argument("--format", choices=["txt", "csv", "json"], default="txt", help="输出格式 (默认: txt)")
    results_parser.add_argument("--with-fragment", action="store_true", help="附带每个文件的命中片段预览")
    _add_time_args(results_parser)

    # Intersect 命令 - 同时包含全部关键词
    intersect_parser = subparsers.add_parser("intersect", help="搜索同时包含多个关键词的文件")
    intersect_parser.add_argument("patterns", nargs='+', help="多个搜索关键词")
    _add_scope_args(intersect_parser)
    _add_time_args(intersect_parser)

    # Union 命令 - 匹配任一关键词
    union_parser = subparsers.add_parser("union", help="搜索匹配任一关键词的文件")
    union_parser.add_argument("patterns", nargs='+', help="多个搜索关键词")
    _add_scope_args(union_parser)
    _add_time_args(union_parser)

    # Exclude 命令 - 包含主关键词但不含排除词
    exclude_parser = subparsers.add_parser("exclude", help="搜索包含主关键词但不含排除词的文件")
    exclude_parser.add_argument("patterns", nargs='+', help="第一个是主关键词，其余为排除词")
    _add_scope_args(exclude_parser)
    _add_time_args(exclude_parser)

    # Fragment 命令
    fragment_parser = subparsers.add_parser("fragment", help="获取文件的关键词匹配片段")
    fragment_parser.add_argument("-f", "--fid", required=True, help="文件ID")
    fragment_parser.add_argument("pattern", help="搜索关键词")
    fragment_parser.add_argument("--all", action="store_true", help="获取所有匹配片段 (GetFragmentAll)")

    # Open 命令
    open_parser = subparsers.add_parser("open", help="打开文件或在资源管理器中定位")
    open_parser.add_argument("path", help="文件路径")
    open_parser.add_argument("--select", action="store_true", help="在资源管理器中定位而不是打开")

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
        lastModifyBegin=_resolve_begin(args),
        lastModifyEnd=args.end,
    )
    count = client.search(options)
    return f"关键词: {args.pattern}\n目录: {args.dir}\n匹配文件数量: {count}"


def _cmd_results(client: AnytxtClient, args: argparse.Namespace) -> str:
    options = GetResultOptions(
        pattern=args.pattern,
        filterDir=args.dir,
        filterExt=args.ext,
        lastModifyBegin=_resolve_begin(args),
        lastModifyEnd=args.end,
        limit=args.limit,
        offset=args.offset,
    )
    files = client.get_result(options)

    fragments: Dict[str, List[str]] = {}
    if args.with_fragment:
        for record in files:
            fragments[record.path] = client.get_fragment_all(
                FragmentOptions(fid=record.fid, pattern=args.pattern)
            )

    body = format_records(files, fmt=args.format, fragments=fragments)
    if args.format == "txt":
        header = '\n'.join([
            f"关键词: {args.pattern}",
            f"目录: {args.dir}",
            f"找到 {len(files)} 个文件:",
            "=" * 80,
        ])
        return header + body
    return body


def _per_drive_sets(
    client: AnytxtClient,
    patterns: List[str],
    args: argparse.Namespace,
) -> Tuple[List[str], Dict[str, List[Set[str]]]]:
    """按盘符分别获取每个关键词的匹配路径集合，返回 (盘符列表, drive -> 各关键词集合)"""
    drives = [args.dir] if args.dir != "C:\\" else _default_drives()
    begin = _resolve_begin(args)

    per_drive: Dict[str, List[Set[str]]] = {}
    for drive in drives:
        keyword_sets: List[Set[str]] = []
        for p in patterns:
            if not getattr(args, "quiet", False):
                print(f"正在搜索 {drive} 关键词 {p} ...")
            keyword_sets.append(client.get_result_all(p, drive, args.ext))
        per_drive[drive] = keyword_sets
    return drives, per_drive


def _format_set_report(title: str, patterns: List[str], drives: List[str],
                       per_drive: Dict[str, Set[str]]) -> str:
    total_count = sum(len(v) for v in per_drive.values())
    lines = [
        f"关键词: {' + '.join(patterns)}",
        f"搜索范围: {', '.join(drives)}",
        f"{title}: {total_count}",
        "=" * 80,
    ]
    for drive, files in per_drive.items():
        if files:
            lines.append(f"\n--- {drive} ({len(files)} 个文件) ---")
            lines.extend(sorted(files))
    return '\n'.join(lines)


def _cmd_intersect(client: AnytxtClient, args: argparse.Namespace) -> str:
    patterns: List[str] = args.patterns
    drives, per_drive_sets = _per_drive_sets(client, patterns, args)

    result = {}
    for drive, keyword_sets in per_drive_sets.items():
        common = keyword_sets[0] if keyword_sets else set()
        for s in keyword_sets[1:]:
            common &= s
        result[drive] = common

    return _format_set_report("同时包含所有关键词的文件总数", patterns, drives, result)


def _cmd_union(client: AnytxtClient, args: argparse.Namespace) -> str:
    patterns: List[str] = args.patterns
    drives, per_drive_sets = _per_drive_sets(client, patterns, args)

    result = {}
    for drive, keyword_sets in per_drive_sets.items():
        merged: Set[str] = set()
        for s in keyword_sets:
            merged |= s
        result[drive] = merged

    return _format_set_report("匹配任一关键词的文件总数", patterns, drives, result)


def _cmd_exclude(client: AnytxtClient, args: argparse.Namespace) -> str:
    patterns: List[str] = args.patterns
    if len(patterns) < 2:
        raise AnytxtError("exclude 需要一个主关键词和至少一个排除词")
    drives, per_drive_sets = _per_drive_sets(client, patterns, args)

    result = {}
    for drive, keyword_sets in per_drive_sets.items():
        excluded: Set[str] = set()
        for s in keyword_sets[1:]:
            excluded |= s
        result[drive] = keyword_sets[0] - excluded

    return _format_set_report("包含主关键词且不含排除词的文件总数", patterns, drives, result)


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


def _cmd_open(client: AnytxtClient, args: argparse.Namespace) -> str:
    path = args.path
    if not os.path.exists(path):
        raise AnytxtError(f"文件不存在: {path}")
    if args.select:
        # Windows 文件名不允许含双引号，直接包裹是安全的；
        # 经 cmd 中转可避免部分环境下直接 CreateProcess explorer.exe 被拒绝
        subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"',
                         shell=True, stderr=subprocess.DEVNULL)
        return f"已在资源管理器中定位: {path}"
    if not hasattr(os, "startfile"):
        raise AnytxtError("open 命令仅支持 Windows")
    os.startfile(path)
    return f"已打开: {path}"


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
    "union": _cmd_union,
    "exclude": _cmd_exclude,
    "fragment": _cmd_fragment,
    "open": _cmd_open,
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
    except Exception as e:
        error_msg = f"错误: 未预期的异常: {e}"
        _write_report(output_file, error_msg)
        if not args.quiet:
            print(error_msg)
        return 1

    bom = args.command == "results" and getattr(args, "format", "txt") == "csv"
    _write_report(output_file, content, bom=bom)
    if not args.quiet:
        print(f"结果已保存到: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
