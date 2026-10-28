"""数据模型：搜索选项、文件记录与排序枚举"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional


class OrderType(Enum):
    """排序类型"""
    DEFAULT = 0
    LAST_MODIFY_ASC = 1
    LAST_MODIFY_DESC = 2
    FILTER_DIR_ASC = 3
    FILTER_DIR_DESC = 4


@dataclass
class SearchOptions:
    """搜索选项"""
    pattern: str
    filterDir: str = "C:\\"
    filterExt: str = "*"
    lastModifyBegin: int = 0
    lastModifyEnd: int = 2147483647


@dataclass
class GetResultOptions(SearchOptions):
    """获取结果选项"""
    limit: int = 300
    offset: int = 0
    order: OrderType = OrderType.DEFAULT


@dataclass
class FragmentOptions:
    """获取片段选项"""
    fid: str
    pattern: str


@dataclass
class SyncIndexOptions:
    """同步索引选项"""
    folder: str


@dataclass
class OCROptions:
    """OCR选项"""
    file: str


@dataclass
class FileRecord:
    """匹配文件记录

    Anytxt 返回的原始记录是位置列表 [fid, lastModify, size, path]，
    位置索引的解析约定集中封装在 from_raw() 中（路径为索引 3）。
    """
    fid: str
    last_modify: int
    size: int
    path: str

    @classmethod
    def from_raw(cls, record: List[Any]) -> Optional["FileRecord"]:
        """从原始位置列表构造记录；短记录返回 None"""
        if not isinstance(record, (list, tuple)) or len(record) < 4:
            return None
        fid, last_modify, size, path = record[0], record[1], record[2], record[3]
        try:
            last_modify = int(last_modify)
        except (TypeError, ValueError):
            last_modify = 0
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 0
        return cls(fid=str(fid), last_modify=last_modify, size=size, path=str(path))

    @property
    def modify_time(self) -> Optional[datetime]:
        """最后修改时间；时间戳非法时返回 None"""
        try:
            return datetime.fromtimestamp(self.last_modify)
        except (OSError, OverflowError, ValueError):
            return None
