"""异常体系"""


class AnytxtError(Exception):
    """Anytxt 客户端错误的基类"""


class AnytxtConnectionError(AnytxtError):
    """无法连接 Anytxt 服务或请求超时"""


class AnytxtRPCError(AnytxtError):
    """Anytxt 服务返回了 RPC 错误"""
