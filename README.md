# Anytxt 全文搜索工具集

基于 [Anytxt Searcher](https://anytxt.net/) 桌面程序（`ATGUI.exe`）HTTP JSON-RPC 2.0 接口的本地文件全文搜索工具集。提供命令行工具和可复用的 Python 客户端库，支持关键词搜索、多关键词交集、正文片段提取、索引同步和 OCR 文字识别。

> 本工具不建立或维护索引，全部搜索能力依赖本机正在运行的 Anytxt。

## 功能

| 命令 | 功能 |
| --- | --- |
| `search` | 查询匹配关键词的文件数量 |
| `results` | 获取匹配文件列表（路径、FID、大小、修改时间），支持分页 |
| `intersect` | 查找同时包含全部关键词的文件（默认跨盘搜索，可配置） |
| `fragment` | 按 FID 提取文件中关键词命中的正文片段 |
| `sync` | 通知 Anytxt 同步指定文件夹的索引 |
| `ocr` | 调用 Anytxt OCR 识别图片中的文字 |

另有 `scripts/combo_search.py` 组合关键词搜索脚本：`目标关键词 AND (备选关键词1 OR 备选关键词2 OR ...)`，适合批量筛查场景。

## 环境要求

- Windows + 已安装并运行 Anytxt Searcher（启用 HTTP 服务，默认端口 9920）
- Python ≥ 3.11（使用标准库 `tomllib`）
- 依赖：`requests`

```bash
pip install -r requirements.txt
```

## 配置方法

复制配置模板并按需修改：

```bash
cp config.example.toml config.toml
```

`config.toml` 内容说明：

```toml
[server]
base_url = "http://127.0.0.1:9920"   # Anytxt HTTP 服务地址
timeout = 30                          # 请求超时秒数

[search]
default_drives = ["C:/", "D:/"]       # intersect 默认搜索范围

[combo_search]                        # scripts/combo_search.py 专用
target_keyword = "关键词A"
or_keywords = ["关键词B1", "关键词B2"]
drives = ["C:/", "D:/"]
output_file = "combo_search_result.txt"
```

- 配置文件缺省时全部使用内置默认值，不配置也能用。
- 可用环境变量 `ANYTXT_CONFIG` 指定其他位置的配置文件。
- `config.toml` 已在 `.gitignore` 中排除，个人关键词和路径不会提交。
- 优先级：命令行 `--url` / `--timeout` > `config.toml` > 内置默认值。

## 使用方法

```bash
python -m anytxt --help        # 推荐入口
python anytxt_client.py --help # 兼容入口，等价
```

常用示例：

```bash
# 查询匹配文件数量
python -m anytxt -o results.txt search "关键字" -d "C:\"

# 获取文件列表（前 100 条）
python -m anytxt -o results.txt results "关键字" -d "C:\" -l 100

# 多关键词交集搜索（不显式指定 -d 时按配置跨盘搜索）
python -m anytxt -o results.txt intersect "关键词1" "关键词2"

# 提取文件中的关键词命中片段（FID 来自 results 输出）
python -m anytxt -o fragments.txt fragment -f "文件FID" "关键字" --all

# 同步文件夹索引
python -m anytxt sync -f "D:\Documents"

# OCR 识别图片文字
python -m anytxt ocr -i "D:\image.png"
```

注意事项：

- 全局参数（`-o`、`-q`、`--url`、`--timeout`）放在子命令**之前**。
- 未指定 `-o` 时，结果写入当前目录 `results_YYYYMMDD_HHMMSS.txt`（UTF-8 覆盖写入）。
- 成功退出码 0，失败退出码 1（连接失败、超时、RPC 错误），可用于脚本流程判断。

### 组合关键词搜索脚本

在 `config.toml` 的 `[combo_search]` 节配置好关键词后：

```bash
python scripts/combo_search.py
```

### 作为 Python 库使用

```python
from anytxt import AnytxtClient, SearchOptions

client = AnytxtClient()  # 自动读取 config.toml

if client.ping():
    count = client.search(SearchOptions(pattern="关键字", filterDir="C:\\"))
    paths = client.get_result_all("关键字", "C:\\")  # 自动翻页 + 去重
```

## 项目结构

```
├── anytxt/                # 核心包
│   ├── models.py          #   数据模型（Options、FileRecord、OrderType）
│   ├── exceptions.py      #   异常体系
│   ├── config.py          #   配置加载（config.toml）
│   ├── client.py          #   AnytxtClient（RPC 封装、自动翻页）
│   ├── cli.py             #   命令行入口
│   └── __main__.py        #   支持 python -m anytxt
├── anytxt_client.py       # 兼容入口（转发到 anytxt.cli）
├── scripts/
│   └── combo_search.py    # 组合关键词搜索脚本（配置驱动）
├── config.example.toml    # 配置模板
├── requirements.txt
└── AGENTS.md              # 面向 AI 协作的项目说明
```

## 安全提示

搜索结果可能包含本地绝对路径、私人文件名、正文片段等敏感信息，请妥善保管输出文件；Anytxt HTTP 服务无认证和 TLS，请勿将端口暴露到本机以外。

## License

MIT
