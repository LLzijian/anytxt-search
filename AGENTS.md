# 项目说明

## 项目概览

本项目是一个面向 Windows 本地环境的 Anytxt 全文搜索工具集，通过 HTTP JSON-RPC 2.0 调用 Anytxt 桌面程序（`ATGUI.exe`）提供的接口。项目本身不建立或维护搜索引擎服务，也不直接解析文档；搜索、片段提取、索引同步和 OCR 均依赖本机正在运行的 Anytxt。

项目结构为：核心包 `anytxt/`（客户端、数据模型、异常、配置、CLI）+ 兼容入口 `anytxt_client.py` + 配置驱动的专用脚本 `scripts/combo_search.py`。个人化配置（服务地址、盘符、关键词）全部放在 `config.toml`（不入库），仓库中只提交 `config.example.toml` 模板。

## 目录与模块

- `anytxt/`：核心包。
  - `models.py`：数据模型。`SearchOptions`、`GetResultOptions`、`FragmentOptions`、`SyncIndexOptions`、`OCROptions` 各 RPC 参数数据类；`OrderType` 排序枚举；`FileRecord` 文件记录（封装原始位置列表 `[fid, lastModify, size, path]` 的解析，路径索引 3 的约定集中在 `FileRecord.from_raw()`）。
  - `exceptions.py`：异常体系。`AnytxtError`（基类）、`AnytxtConnectionError`（连接失败/超时）、`AnytxtRPCError`（响应含 error）。
  - `config.py`：`load_config()`，用标准库 `tomllib` 读取项目根目录 `config.toml`；环境变量 `ANYTXT_CONFIG` 可指定其他路径；文件缺失返回空字典。
  - `client.py`：`AnytxtClient`。使用 `requests.Session` 复用连接；`base_url` 自动补 `http://` 前缀；base_url/timeout 的解析优先级为：构造参数 > `config.toml [server]` > 内置默认值（`http://127.0.0.1:9920`、30 秒）。方法：`ping()`、`search()`、`get_result()`（返回 `List[FileRecord]`）、`iter_result_all()`（每页 1000 自动翻页、按路径去重的生成器）、`get_result_all()`（返回路径集合）、`get_fragment()` / `get_fragment_all()`（返回片段文本列表 `List[str]`）、`sync_index()`、`ocr()`。
  - `cli.py`：命令行入口 `main()`，实现 `search`、`results`、`intersect`、`fragment`、`sync`、`ocr` 六个子命令。`intersect` 默认盘符来自 `[search] default_drives`。
  - `__main__.py`：支持 `python -m anytxt ...`。
- `anytxt_client.py`：兼容入口薄封装，转发到 `anytxt.cli.main()`，兼容既有用法 `python anytxt_client.py ...`。
- `scripts/combo_search.py`：组合关键词搜索脚本（`目标关键词 AND (任一备选关键词)`），关键词、盘符、输出名全部来自 `config.toml` 的 `[combo_search]` 节；有 `main()` 函数和 `if __name__ == "__main__"` 保护，可安全导入。
- `config.example.toml`：配置模板（入库）；`config.toml`：本地个人配置（gitignore）。
- `requirements.txt`：唯一依赖声明，仅包含 `requests>=2.28.0`。

项目使用 Git 管理并托管于 GitHub（私有仓库）；没有 `pyproject.toml`、`setup.py`、锁文件、测试目录或 CI 配置。

## 技术栈与运行架构

- 语言：Python ≥ 3.11（配置解析依赖标准库 `tomllib`），另用标准库 `argparse`、`dataclasses`、`enum`、`datetime` 等模块。
- 第三方依赖：`requests`，通过 HTTP POST 发送 JSON-RPC 请求。
- 外部运行时：Anytxt 桌面程序及其 HTTP 服务。客户端不会启动或安装 Anytxt。
- 数据流：CLI 参数或 Python 数据类 → `AnytxtClient._rpc_call()` → `params.input` 中的 RPC 参数 → 本机 Anytxt → `result.data.output` 中的响应数据 → UTF-8 文本报告。
- `_rpc_call()` 使用固定请求 ID `123` 和可配置超时（默认 30 秒），调用 `raise_for_status()`，连接/超时错误抛 `AnytxtConnectionError`，响应含 `error` 抛 `AnytxtRPCError`。
- 文件记录由 `FileRecord.from_raw()` 按 `[fid, lastModify, size, path]` 的位置解析，路径索引为 3，短记录返回 `None` 并被过滤。
- 片段接口（GetFragment/GetFragmentAll）的响应字段是 `output.text`（字符串列表），不是 `fragments`。
- Anytxt 的 `filterDir` 按路径前缀匹配且索引内为反斜杠路径；客户端在 `search()`/`get_result()` 中通过 `_normalize_dir()` 将正斜杠统一为反斜杠，两种写法均可传入。
- Anytxt 服务端会把每页结果截断到内部上限（约 300 条，小于请求的分页大小）；`iter_result_all()` 因此按实际返回条数推进 offset，并在整页无新增路径时终止。

## 安装与运行

本项目无需构建，直接运行脚本。Python 统一使用 Miniconda 的 base 环境（Python 3.12.9），解释器路径为 `C:\ProgramData\miniconda3\python.exe`（Git Bash 中为 `/c/ProgramData/miniconda3/python.exe`）。注意当前 shell 的 PATH 中 `python` 指向 WindowsApps 的占位程序而非该环境，运行时应使用上述完整路径；该环境已安装 `requests`。如需在新环境安装依赖：

```bash
python -m pip install -r requirements.txt
```

首次使用复制配置模板（可选，缺省也能运行）：

```bash
cp config.example.toml config.toml
```

确保 Anytxt 已运行且 HTTP 服务已启用，然后执行：

```bash
python -m anytxt --help        # 推荐方式
python anytxt_client.py --help # 兼容入口，等价
```

常用命令示例：

```bash
# 查询匹配文件数量
python -m anytxt -o results.txt search "关键字" -d "C:\\"

# 获取文件列表
python -m anytxt -o results.txt results "关键字" -d "C:\\" -l 100

# 查询同时包含全部关键词的文件
python -m anytxt -o results.txt intersect "关键词1" "关键词2" -d "D:\\"

# 获取指定 FID 的匹配片段；加 --all 获取全部片段
python -m anytxt -o fragments.txt fragment -f "文件FID" "关键字"

# 同步文件夹索引
python -m anytxt -o sync_result.txt sync -f "D:\\Documents"

# OCR 识别图片
python -m anytxt -o ocr_result.txt ocr -i "D:\\image.png"
```

参数和输出注意事项：

- 全局参数 `-o/--output`、`-q/--quiet`、`--url`、`--timeout` 应放在子命令之前。`results` 子命令的分页偏移参数为 `--offset`。
- 未指定输出文件时，所有子命令都会使用当前目录下的 `results_YYYYMMDD_HHMMSS.txt`。
- 正常结果以 UTF-8 覆盖写入；`--quiet` 只抑制状态输出，不改变文件写入行为。
- `intersect` 在目录保持默认值 `C:\` 时按 `[search] default_drives`（默认 C/D/E/F 盘）依次搜索；显式指定其他目录时只搜索该目录。
- CLI 捕获连接、超时及 RPC 错误，将错误写入输出文件并**以退出码 1 结束**；成功时退出码为 0。可依赖进程退出码判断搜索是否成功。
- `scripts/combo_search.py` 用 `python scripts/combo_search.py` 运行（在项目根目录下执行），复用 `get_result_all()` 自动翻页，不受单次 limit 截断影响；未配置 `[combo_search]` 时退出码 1 并提示。

## 修改约定

- 保持现有中文 docstring、CLI 帮助和结果报告语言。
- Python 函数和变量使用 `snake_case`；`filterDir`、`filterExt`、`lastModifyBegin` 等字段沿用 Anytxt API 的 `camelCase` 名称，避免擅自改名导致请求不兼容。
- 新增 RPC 方法时，沿用 `AnytxtClient._rpc_call()` 的请求封装和 `result.data.output` 响应解析方式（可用 `_output()` 辅助），并使用对应数据类承载参数。
- 文件记录的位置索引解析只能改 `FileRecord.from_raw()` 一处，保留索引 3 为路径的约定和短记录防护；其他代码一律使用 `FileRecord` 的命名字段。
- 个人化数据（关键词、盘符、服务地址等）只写入 `config.toml` 或本地脚本调用参数，不要硬编码进入库文件；`config.toml` 与搜索结果输出必须保持在 `.gitignore` 中。
- 结果文件统一使用 UTF-8 覆盖写入（`cli._write_report()`），不要无意间改成追加或让多次操作互相覆盖。
- 项目没有配置格式化工具、linter 或类型检查器，也没有强制风格配置。修改应保持现有轻量结构，不要无必要地引入框架或依赖。

## 测试与验证

项目目前没有自动化测试或测试框架，也没有可离线运行的 RPC 测试替身。基础语法和 CLI 验证可使用：

```bash
python -m py_compile anytxt/*.py anytxt_client.py scripts/combo_search.py
python -m anytxt --help
```

涉及 RPC 的修改需要在 Anytxt 实际运行且相关目录已建立索引的环境中做端到端验证。优先用限定目录和明确关键词的小范围查询，分别检查返回数量、文件记录字段、分页边界、片段响应及 UTF-8 输出；`intersect` 还应验证多关键词交集和默认多盘符行为。连接错误场景可用 `--url http://127.0.0.1:19999` 指向错误端口验证退出码与错误报告。

`scripts/combo_search.py` 可以安全导入做无副作用检查（不会立即执行搜索），但实际运行会按配置跨盘发起多轮搜索并覆盖配置的输出文件，验证时注意范围。

## 安全与隐私

- 搜索结果可能包含真实姓名、本地绝对路径、私人文件名、正文片段和 OCR 文本。所有搜索输出文件和 `config.toml` 均在 `.gitignore` 中，提交代码前用 `git status` 确认没有敏感文件被跟踪。
- 默认 `intersect` 和组合搜索脚本会跨多个盘符查询，可能产生大量请求并暴露广泛的文件元数据；运行前确认范围，开发验证时显式缩小目录。
- 默认端点仅为本机回环地址且没有认证或 TLS。若通过 `--url` 或 `AnytxtClient(base_url=...)` 指向其他地址，调用方需自行评估网络与数据泄露风险。
- `sync` 会请求 Anytxt 更新索引；OCR 和片段命令会把文件内容派生为明文报告。不要将这些输出视为无敏感信息。
- 组合搜索脚本中的关键词只是搜索条件，命中结果只是文本匹配，需人工复核确认。

## 部署

没有独立构建或发布流程。实际部署就是在装有 Anytxt 的 Windows 机器上克隆仓库、安装 `requests`（Python ≥ 3.11）、按需复制 `config.example.toml` 为 `config.toml`，并确认 Anytxt HTTP 端口可用。输出文件写入进程当前工作目录，因此运行账户需要该目录的写权限。项目不包含后台服务、自动启动、安装器或远程部署能力。
