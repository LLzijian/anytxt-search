#!/usr/bin/env python3
"""批量关键词检索：按一组关键词跨盘全文检索并生成汇总报告

白名单目录（含子目录）中的命中不计入结果。关键词与白名单目录在项目根目录
`config.toml` 的 [batch_search] 节中维护（参考 config.example.toml），
搜索范围缺省沿用 [search] default_drives。

运行方式（项目根目录下）：

    python scripts/batch_search.py                     # 按配置检索
    python scripts/batch_search.py --no-whitelist      # 忽略白名单（全量对照）
    python scripts/batch_search.py -o report.txt       # 指定输出文件

命中仅表示文件内容或名称包含关键词，需人工复核确认。
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anytxt import AnytxtClient, AnytxtError, load_config
from anytxt.cli import _default_drives
from anytxt.models import FileRecord

DEFAULT_MULTI_HIT_THRESHOLD = 3


def _normalize_dir(path: str) -> str:
    """统一目录写法：正斜杠转反斜杠，去除首尾空白和结尾分隔符"""
    return str(path).strip().replace("/", "\\").rstrip("\\")


def _under(path: str, directory: str) -> bool:
    """判断 path 是否位于 directory 之内（按目录边界匹配，忽略大小写）"""
    p = path.lower()
    d = directory.lower()
    return p == d or p.startswith(d + "\\")


def _load_whitelist(raw_entries) -> list:
    """解析白名单目录列表，规范化并去重（保持顺序）"""
    entries = []
    for item in raw_entries or []:
        normalized = _normalize_dir(item)
        if normalized and normalized not in entries:
            entries.append(normalized)
    return entries


def _is_whitelisted(path: str, whitelist: list) -> bool:
    """路径命中任一白名单目录（含子目录）"""
    return any(_under(path, d) for d in whitelist)


def _human_size(n: int) -> str:
    """文件大小的可读表示"""
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{int(x)}B" if unit == "B" else f"{x:.1f}{unit}"
        x /= 1024


def _format_record(rec: FileRecord, hit_keywords=None) -> str:
    """渲染单条文件记录：路径 | 修改时间 | 大小 [| 命中关键词] | FID"""
    modify = rec.modify_time.strftime("%Y-%m-%d %H:%M") if rec.modify_time else "?"
    parts = [rec.path, modify, _human_size(rec.size)]
    if hit_keywords is not None:
        parts.append("+".join(hit_keywords))
    parts.append(f"FID={rec.fid}")
    return " | ".join(parts)


def _search(client: AnytxtClient, keywords: list, drives: list,
            whitelist: list, quiet: bool):
    """跨盘搜索全部关键词

    返回 (per_kw, dropped)：均为 关键词 -> {路径: FileRecord} 字典，
    per_kw 为白名单外的命中，dropped 为白名单内被剔除的命中。
    """
    per_kw = {kw: {} for kw in keywords}
    dropped = {kw: {} for kw in keywords}
    for drive in drives:
        for kw in keywords:
            if not quiet:
                print(f"正在搜索 {drive} 关键词 {kw} ...")
            for rec in client.iter_result_all(kw, drive):
                bucket = dropped if _is_whitelisted(rec.path, whitelist) else per_kw
                if rec.path not in bucket[kw]:
                    bucket[kw][rec.path] = rec
    return per_kw, dropped


def _build_report(keywords: list, drives: list, whitelist: list,
                  per_kw: dict, dropped: dict, threshold: int,
                  now: datetime):
    """生成检索报告文本，返回 (报告内容, 统计信息字典)"""
    union = {}
    for kw in keywords:
        for path, rec in per_kw[kw].items():
            entry = union.setdefault(path, {"rec": rec, "kws": []})
            entry["kws"].append(kw)

    dropped_union = set()
    for kw in keywords:
        dropped_union.update(dropped[kw])

    multi = [(len(v["kws"]), p, v) for p, v in union.items() if len(v["kws"]) >= threshold]
    multi.sort(key=lambda x: (-x[0], x[1]))

    lines = [
        "Anytxt 批量关键词检索报告",
        f"生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"搜索范围: {', '.join(drives)}",
        f"关键词: {'、'.join(keywords)}",
        (f"白名单目录: {len(whitelist)} 个（命中已剔除，见第四节统计）"
         if whitelist else "白名单: 未启用"),
        "说明: 命中仅表示文件内容或名称包含关键词，需人工复核确认。",
        "=" * 100,
        "",
        "一、汇总（白名单外）",
        "-" * 100,
        "关键词\t命中文件数\t白名单内剔除",
    ]
    for kw in keywords:
        lines.append(f"{kw}\t{len(per_kw[kw])}\t{len(dropped[kw])}")
    lines.append(f"合计（去重）\t{len(union)}\t{len(dropped_union)}")

    lines += ["", "盘符分布（白名单外）:",
              "关键词\t" + "\t".join(_normalize_dir(d) for d in drives)]
    for kw in keywords:
        counts = [sum(1 for p in per_kw[kw] if _under(p, _normalize_dir(d))) for d in drives]
        lines.append(f"{kw}\t" + "\t".join(str(c) for c in counts))

    lines += ["",
              f"二、同时命中 {threshold} 个及以上关键词的文件（白名单外，优先复核）",
              "-" * 100]
    if multi:
        for _, _, v in multi:
            lines.append(_format_record(v["rec"], hit_keywords=v["kws"]))
        lines.append(f"（共 {len(multi)} 个）")
    else:
        lines.append("（无）")

    lines += ["", "三、各关键词明细（白名单外）"]
    for kw in keywords:
        lines += ["-" * 100, f"【{kw}】 {len(per_kw[kw])} 个文件"]
        if per_kw[kw]:
            lines.extend(_format_record(per_kw[kw][p]) for p in sorted(per_kw[kw]))
        else:
            lines.append("（无）")

    lines += ["", "四、白名单剔除统计", "-" * 100]
    if whitelist:
        dropped_by_dir = {}
        assigned = set()
        for kw in keywords:
            for path in dropped[kw]:
                if path in assigned:
                    continue
                assigned.add(path)
                for d in whitelist:
                    if _under(path, d):
                        dropped_by_dir[d] = dropped_by_dir.get(d, 0) + 1
                        break
        for d in whitelist:
            lines.append(f"{dropped_by_dir.get(d, 0)}\t{d}")
        lines.append(f"合计（去重）\t{len(dropped_union)}")
    else:
        lines.append("（未启用白名单）")

    content = "\n".join(lines) + "\n"
    stats = {"union": len(union), "multi": len(multi), "dropped_union": len(dropped_union)}
    return content, stats


def main(argv=None) -> int:
    """CLI 入口；返回进程退出码"""
    parser = argparse.ArgumentParser(
        description="Anytxt 批量关键词检索（白名单目录中的命中不计入，配置见 config.toml [batch_search]）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出文件 (默认: results_batch_YYYYMMDD_HHMMSS.txt)")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，不打印进度")
    parser.add_argument("--no-whitelist", action="store_true",
                        help="忽略白名单，输出全量命中（对照用）")
    args = parser.parse_args(argv)

    batch = load_config().get("batch_search", {})
    keywords = list(dict.fromkeys(batch.get("keywords") or []))
    whitelist = [] if args.no_whitelist else _load_whitelist(batch.get("whitelist_dirs"))
    drives = [_normalize_dir(d) for d in (batch.get("drives") or _default_drives())]
    threshold = int(batch.get("multi_hit_threshold") or DEFAULT_MULTI_HIT_THRESHOLD)

    if not keywords:
        print("错误: 请在 config.toml 的 [batch_search] 节配置 keywords（参考 config.example.toml）")
        return 1

    client = AnytxtClient()
    now = datetime.now()
    output = args.output or now.strftime("results_batch_%Y%m%d_%H%M%S.txt")

    try:
        per_kw, dropped = _search(client, keywords, drives, whitelist, args.quiet)
    except AnytxtError as e:
        print(f"错误: {e}")
        return 1

    content, stats = _build_report(keywords, drives, whitelist, per_kw, dropped,
                                   threshold, now)
    with open(output, "w", encoding="utf-8") as f:
        f.write(content)

    if not args.quiet:
        print()
        print("===== 检索汇总（白名单外） =====")
        for kw in keywords:
            print(f"{kw}: {len(per_kw[kw])}（白名单内剔除 {len(dropped[kw])}）")
        print(f"合计（去重）: {stats['union']}")
        print(f"同时命中>={threshold}个关键词: {stats['multi']}")
        print(f"报告已保存: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
