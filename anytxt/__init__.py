"""Anytxt 本地文件全文搜索工具集"""

from .client import AnytxtClient, DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from .config import load_config
from .exceptions import AnytxtConnectionError, AnytxtError, AnytxtRPCError
from .report import format_records
from .models import (
    FileRecord,
    FragmentOptions,
    GetResultOptions,
    OCROptions,
    OrderType,
    SearchOptions,
    SyncIndexOptions,
)

__all__ = [
    "AnytxtClient",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "format_records",
    "load_config",
    "AnytxtError",
    "AnytxtConnectionError",
    "AnytxtRPCError",
    "FileRecord",
    "FragmentOptions",
    "GetResultOptions",
    "OCROptions",
    "OrderType",
    "SearchOptions",
    "SyncIndexOptions",
]
