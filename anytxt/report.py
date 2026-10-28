"""结果报告渲染：txt / csv / json"""

import csv
import io
import json
from typing import Dict, List, Optional

from .models import FileRecord

FRAGMENT_PREVIEW_COUNT = 2
FRAGMENT_PREVIEW_LENGTH = 200


def _mtime_str(record: FileRecord) -> str:
    mt = record.modify_time
    return mt.strftime('%Y-%m-%d %H:%M:%S') if mt else str(record.last_modify)


def _truncate(text: str, limit: int = FRAGMENT_PREVIEW_LENGTH) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def format_records(
    records: List[FileRecord],
    fmt: str = "txt",
    fragments: Optional[Dict[str, List[str]]] = None,
) -> str:
    """将文件记录渲染为指定格式的报告正文（不含报告头）"""
    fragments = fragments or {}
    if fmt == "json":
        return _format_json(records, fragments)
    if fmt == "csv":
        return _format_csv(records, fragments)
    return _format_txt(records, fragments)


def _format_txt(records: List[FileRecord], fragments: Dict[str, List[str]]) -> str:
    lines: List[str] = []
    for i, record in enumerate(records, 1):
        lines.append(f"\n[{i}] {record.path}")
        lines.append(f"    FID: {record.fid}")
        lines.append(f"    大小: {record.size} bytes")
        lines.append(f"    修改时间: {_mtime_str(record)}")
        frags = fragments.get(record.path)
        if frags:
            for frag in frags[:FRAGMENT_PREVIEW_COUNT]:
                lines.append(f"    片段: {_truncate(frag)}")
            if len(frags) > FRAGMENT_PREVIEW_COUNT:
                lines.append(f"    片段: ... 共 {len(frags)} 条")
    return '\n'.join(lines)


def _format_csv(records: List[FileRecord], fragments: Dict[str, List[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["path", "fid", "size", "mtime", "fragments"])
    for record in records:
        frags = " | ".join(_truncate(f) for f in fragments.get(record.path, []))
        writer.writerow([record.path, record.fid, record.size, _mtime_str(record), frags])
    return buf.getvalue().rstrip("\r\n")


def _format_json(records: List[FileRecord], fragments: Dict[str, List[str]]) -> str:
    data = [
        {
            "path": record.path,
            "fid": record.fid,
            "size": record.size,
            "mtime": _mtime_str(record),
            "fragments": fragments.get(record.path, []),
        }
        for record in records
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)
