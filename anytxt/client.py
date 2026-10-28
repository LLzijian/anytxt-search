"""Anytxt RPC 客户端

通过 HTTP JSON-RPC 2.0 调用 Anytxt 桌面程序（ATGUI.exe）提供的接口。
"""

from typing import Any, Dict, Iterator, List, Optional, Set

import requests

from .config import load_config
from .exceptions import AnytxtConnectionError, AnytxtRPCError
from .models import (
    FileRecord,
    FragmentOptions,
    GetResultOptions,
    OCROptions,
    SearchOptions,
    SyncIndexOptions,
)

DEFAULT_BASE_URL = "http://127.0.0.1:9920"
DEFAULT_TIMEOUT = 30
PAGE_SIZE = 1000


class AnytxtClient:
    """Anytxt API 客户端"""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        server_config = load_config().get("server", {})
        base_url = base_url or server_config.get("base_url") or DEFAULT_BASE_URL
        if "://" not in base_url:
            base_url = f"http://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout if timeout is not None else int(server_config.get("timeout", DEFAULT_TIMEOUT))
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _rpc_call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送 JSONRPC 请求"""
        payload = {
            "id": 123,
            "jsonrpc": "2.0",
            "method": method,
            "params": {
                "input": params
            }
        }

        try:
            response = self._session.post(self.base_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise AnytxtConnectionError(
                f"无法连接到 Anytxt 服务 ({self.base_url})，请确保 Anytxt 正在运行且 HTTP 服务已启用"
            ) from e
        except requests.exceptions.Timeout as e:
            raise AnytxtConnectionError(f"请求 Anytxt 服务超时（{self.timeout} 秒）") from e
        except requests.exceptions.RequestException as e:
            raise AnytxtConnectionError(f"请求 Anytxt 服务失败: {e}") from e

        try:
            result = response.json()
        except ValueError as e:
            raise AnytxtRPCError(f"Anytxt 服务返回了非 JSON 响应: {response.text[:200]}") from e

        if "error" in result and result["error"]:
            raise AnytxtRPCError(f"RPC Error: {result['error']}")

        return result.get("result", {})

    @staticmethod
    def _output(result: Dict[str, Any]) -> Dict[str, Any]:
        """提取 result.data.output"""
        return result.get("data", {}).get("output", {})

    @staticmethod
    def _normalize_dir(filter_dir: str) -> str:
        """将 filterDir 中的正斜杠统一为反斜杠

        Anytxt 索引内的路径使用反斜杠，filterDir 按前缀匹配；
        正斜杠的子目录会匹配不到任何记录（盘符根目录除外）。
        """
        return filter_dir.replace("/", "\\")

    def ping(self) -> bool:
        """检测 Anytxt 服务是否可用"""
        try:
            self.search(SearchOptions(pattern="", filterDir="C:\\"))
            return True
        except (AnytxtConnectionError, AnytxtRPCError):
            return False

    def search(self, options: SearchOptions) -> int:
        """搜索: 获取匹配关键词的文件数量"""
        params = {
            "pattern": options.pattern,
            "filterDir": self._normalize_dir(options.filterDir),
            "filterExt": options.filterExt,
            "lastModifyBegin": options.lastModifyBegin,
            "lastModifyEnd": options.lastModifyEnd
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.Search", params)
        return self._output(result).get("count", 0)

    def get_result(self, options: GetResultOptions) -> List[FileRecord]:
        """GetResult: 获取匹配关键词的文件列表及基本信息"""
        params = {
            "pattern": options.pattern,
            "filterDir": self._normalize_dir(options.filterDir),
            "filterExt": options.filterExt,
            "lastModifyBegin": options.lastModifyBegin,
            "lastModifyEnd": options.lastModifyEnd,
            "limit": str(options.limit),
            "offset": options.offset,
            "order": options.order.value
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.GetResult", params)
        raw_files = self._output(result).get("files", [])
        records = (FileRecord.from_raw(f) for f in raw_files)
        return [r for r in records if r is not None]

    def iter_result_all(
        self,
        pattern: str,
        filterDir: str,
        filterExt: str = "*",
        page_size: int = PAGE_SIZE,
    ) -> Iterator[FileRecord]:
        """迭代所有匹配的文件记录（自动翻页，按路径去重）

        注意 Anytxt 服务端会将每页记录数截断到其内部上限（约 300 条，
        小于请求的分页大小），因此翻页以实际返回条数推进 offset，
        并在整页无新增路径时终止。
        """
        seen: Set[str] = set()
        offset = 0

        while True:
            options = GetResultOptions(
                pattern=pattern,
                filterDir=filterDir,
                filterExt=filterExt,
                limit=page_size,
                offset=offset,
            )
            records = self.get_result(options)
            if not records:
                break

            new_count = 0
            for record in records:
                if record.path not in seen:
                    seen.add(record.path)
                    new_count += 1
                    yield record

            if new_count == 0:
                break
            offset += len(records)

    def get_result_all(self, pattern: str, filterDir: str, filterExt: str = "*") -> Set[str]:
        """获取所有匹配的文件路径集合（自动翻页）"""
        return {r.path for r in self.iter_result_all(pattern, filterDir, filterExt)}

    def get_fragment(self, options: FragmentOptions) -> List[str]:
        """GetFragment: 获取单个关键词匹配的片段文本"""
        params = {
            "fid": options.fid,
            "pattern": options.pattern
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.GetFragment", params)
        return self._output(result).get("text", [])

    def get_fragment_all(self, options: FragmentOptions) -> List[str]:
        """GetFragmentAll: 获取所有关键词匹配的片段文本"""
        params = {
            "fid": options.fid,
            "pattern": options.pattern
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.GetFragmentAll", params)
        return self._output(result).get("text", [])

    def sync_index(self, options: SyncIndexOptions) -> bool:
        """SyncIndex: 同步文件夹到索引"""
        params = {
            "folder": options.folder
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.SyncIndex", params)
        return result.get("data", {}).get("errno", -1) == 0

    def ocr(self, options: OCROptions) -> str:
        """OCR: 获取图片中的文本"""
        params = {
            "file": options.file
        }

        result = self._rpc_call("ATRpcServer.Searcher.V1.OCR", params)
        return self._output(result).get("text", "")
