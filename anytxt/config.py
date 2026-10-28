"""配置加载

从项目根目录的 `config.toml` 读取配置；可用环境变量 `ANYTXT_CONFIG`
指定其他配置文件路径。配置文件不存在时返回空配置，各项使用默认值。
"""

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"
ENV_CONFIG = "ANYTXT_CONFIG"


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件；文件不存在时返回空字典"""
    config_path = Path(path or os.environ.get(ENV_CONFIG) or DEFAULT_CONFIG_PATH)
    if not config_path.is_file():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)
