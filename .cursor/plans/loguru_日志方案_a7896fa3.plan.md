# 唯一执行方案：Loguru 日志体系（根脚本 + FastAPI 统一）

> **实施状态**：**已完成**（2026-04-11）  
> **阶段 A**：根目录 `lib/log_config.py`、`LOG_CONFIG` 扩展、`utils` 薄封装、`requirements.txt` 增加 loguru。  
> **阶段 B**：`backend/requirements.txt` 增加 loguru；`main.py` 注入 `sys.path` 后调用 `setup_logging(..., LOG_CONFIG)`，**`LOG_CONFIG` 由 `config_new` 传入**（与根目录 `config.py` 解耦）；`uvicorn` 相关 logger 去 handler + `propagate`，减轻重复输出。

本文档为 **shoplazza_dashboard / line chart** 项目在日志改造上的 **唯一执行方案**（合并多轮讨论与评审结论）；实施记录与验收说明见 **`项目开发过程/Loguru日志体系改造-开发总结_20260411.md`**。

---

## 1. 背景与目标

| 现状 | 问题 |
|------|------|
| [`config.py`](d:\projects\line chart\config.py) 中 `LOG_CONFIG` 含 `max_bytes` 等，但 [`utils.py`](d:\projects\line chart\utils.py) 仅用 `FileHandler` 写 [`logs/app.log`](d:\projects\line chart\logs\app.log) | 单文件无限增长，按日排查困难 |
| 业务与脚本大量使用标准库 `logging.getLogger(__name__)` | 改造需兼容，不宜全项目改为 loguru API |

| 目标 | 说明 |
|------|------|
| 按日历日落盘 | 文件名含日期，如 `combined-YYYY-MM-DD.log` |
| 单日过大再切分 | 与「到点换日」为 **或** 关系，见 §3 |
| 历史段 gzip | 减轻磁盘占用 |
| 保留约 30 天 | 自动清理过期文件 |
| ERROR 分流 | `error-YYYY-MM-DD.log` 仅 ERROR 及以上 |
| 根目录脚本与 FastAPI **同一套初始化** | 统一目录与格式，便于排障及后续 ELK/Loki（你已确认阶段 B 必做） |

---

## 2. 技术选型结论（有理有据）

**采用 loguru + 标准库拦截，不采用纯标准库自写轮转。**

- 标准库 `TimedRotatingFileHandler` 与 `RotatingFileHandler` 组合成「按天 + 按大小 + gzip + 统一命名」需要大量自定义 `Handler`/`namer`/`rotator`，维护成本高，且多进程/边界行为易踩坑。
- **loguru** 将 `rotation`、`compression`、`retention` 声明式配置，社区成熟；配合 **`InterceptHandler`** 可把现有 `logging.info` 等**无改动迁移**到同一套落盘策略。
- **幂等初始化**（`logger.remove()` + 模块级「已配置」标志）可避免 FastAPI **uvicorn --reload** 或重复 import 导致 **重复 sink、日志打两遍**（见 §5）。

---

## 3. 行为规格（实现时必须遵守）

### 3.1 文件与目录

- 根目录由 `LOG_CONFIG` 提供（或通过现有参数 `log_file` 解析出目录，例如 `logs/app.log` → `logs/`），**不再向 `app.log` 追加**（历史文件可保留、人工归档）。
- 全量：`{log_dir}/combined-{time:YYYY-MM-DD}.log`
- 错误：`{log_dir}/error-{time:YYYY-MM-DD}.log`
- 可选 JSON（默认关闭）：`enable_json_log: False` 时不动；为 True 时增加 `serialize=True` 的 sink（如 `json-` 前缀），便于未来 Grafana 等采集。

### 3.2 轮转（loguru `rotation`）

- 使用 **多条件**，例如 **`["00:00", "50 MB"]`（具体阈值以 `LOG_CONFIG` 为准）**。
- 语义为 **「或」**：满足 **任一** 条件即轮转——即到 **本地午夜** 换日文件，或 **单文件超过阈值** 在同日内再切分；**不是**「同时满足才轮转」。
- **代码注释范本（实现时贴在 `rotation=` 旁，免后人翻文档）**：

```python
# 注：Loguru 的列表参数表示「或」逻辑：达到大小阈值或到达本地零点，任一发生即触发轮转。
```

（阈值 `"50 MB"` 与 `"00:00"` 若来自配置变量，注释中可写「见 LOG_CONFIG」即可。）

### 3.3 压缩与保留

- `compression="gz"`
- `retention="30 days"`（与「约 30 个自然日」实践一致，以文件时间为准）
- `enqueue=True`：缓解**同进程多线程**写同一 sink；**不**等同于两 OS 进程安全写同一文件（见 §6）。

### 3.4 级别与分流

- `combined`：INFO 及以上（或与 `log_level` 一致）
- `error`：ERROR 及以上
- **控制台（sys.stdout）**：保留，避免「只写文件、终端无输出」；与落盘文件 **可用不同 `format`**——终端侧重可读性与开发体验，文件侧重稳定归档（时间戳、级别、模块名等与现网一致即可）。
- **控制台 `format` 建议（可采纳）**：使用 loguru 的标记颜色 + 缩进级别名，例如：

```text
format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
```

  并设 `colorize=True`（loguru 在常见 Windows 终端下可显示 ANSI 色；若环境无颜色，可关 `colorize` 或换无 `<green>` 的纯文本 format）。**文件 sink 勿强制套与此相同的彩色标记**，以免日志文件含控制序列。

### 3.5 第三方库降噪

对常见库设置 `logging.getLogger(name).setLevel(logging.WARNING)`，例如：`urllib3`、`urllib3.connectionpool`、`requests`；若项目使用则加上 `sqlalchemy`、`botocore`、`httpx` 等。目的：避免根级别为 DEBUG 时刷屏；**非**屏蔽业务错误。

### 3.6 `diagnose`（异常变量快照）

- 配在 **loguru 的 `logger.add(..., diagnose=...)`**（error sink），**不是** InterceptHandler 独有参数。
- **默认 False**：`diagnose=True` 可能把 token、密码等写入磁盘；仅在受控排障或确认无敏感变量时可对 **error** 单独开启。

### 3.7 InterceptHandler 与行号

- 使用社区常见的 **跳过 logging 内部帧** + `logger.opt(depth=...)`。
- **验收**：在业务模块打一条 `logging.info("marker")`，确认 combined 中 **文件名/行号** 指向业务文件而非仅 [`lib/log_config.py`](d:\projects\line chart\lib\log_config.py)。

---

## 4. 代码结构（唯一推荐布局）

| 文件 | 职责 |
|------|------|
| **[`lib/__init__.py`](d:\projects\line chart\lib\__init__.py)** | 包标识（可空） |
| **[`lib/log_config.py`](d:\projects\line chart\lib\log_config.py)** | **唯一**实现 `setup_logging`：依赖 `os`、`logging`、`loguru`；未传入 `log_config` 时读取项目根 `config.LOG_CONFIG`；**禁止** import `database`、`data_sync` 等业务模块 |
| **[`config.py`](d:\projects\line chart\config.py)** | 扩展 `LOG_CONFIG`（路径模板、轮转阈值、`retention`、可选 `enable_json_log`）；可选 **`TypedDict`** 描述键 |
| **[`requirements.txt`](d:\projects\line chart\requirements.txt)** 与 **[`backend/requirements.txt`](d:\projects\line chart\backend\requirements.txt)** | **两处统一**写入 **`loguru>=0.7.0`**（或项目锁定的同一下限），避免根脚本 venv 与 backend venv 版本漂移；阶段 A 可先改根目录，阶段 B 改 backend 时再次核对一致。 |
| **[`utils.py`](d:\projects\line chart\utils.py)** | **可选**：`from lib.log_config import setup_logging` 再 `__all__` 或别名，减少全仓库 import 改动量 |
| **根目录各脚本**（`data_sync.py`、`fill_*.py`、`dashboard.py` 等） | 统一 `setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])` 或从 `lib`/`utils` 导入（与 §7 实施步骤一致） |

**阶段 B**：[backend/app/main.py](d:\projects\line chart\backend\app\main.py) 在应用启动路径调用 **同一** `setup_logging`；[backend/requirements.txt](d:\projects\line chart\backend\requirements.txt) 增加 `loguru`；协调 **uvicorn** 自带 logging，避免与业务重复输出（access 可仍主要走控制台或单独策略）。

---

## 5. 幂等初始化（必做）

1. 模块级 `_LOGGING_CONFIGURED`（或等价命名）：已为真则 **直接 return**。
2. **首次**：`logger.remove()` → `add` combined / error / stdout / 可选 json。
3. `logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)`（Python 3.8+），保证标准库日志进入 loguru。
4. 阶段 B：保证 reload 下**不重复挂载**；验收「同一条日志不重复打印」。

---

## 6. 风险与约束（已知）

| 风险 | 处理 |
|------|------|
| 两进程同时写同一 `combined-*.log`（如 Streamlit + data_sync） | `enqueue` 不解决跨进程；依赖运维避免重叠，或文档说明；可选未来 env 按 PID 分文件（默认不做） |
| 午夜时区 | `"00:00"` 依赖进程本地时区；生产 Linux/容器需 `TZ=Asia/Shanghai` 或运维约定 |
| JSON / diagnose | 体积与隐私；默认关 / diagnose 默认 False |

**回滚**：还原 `lib/log_config.py`（若已添加）、`config.py`、`requirements.txt`、各入口 import，并恢复原 `utils.setup_logging` 中单文件 `app.log` 逻辑。

---

## 7. 执行阶段与待办（顺序固定）

**阶段 A（先做）** — **状态：已完成**

1. 根目录 `requirements.txt` 增加 **`loguru>=0.7.0`**；扩展 `LOG_CONFIG`（及可选 TypedDict、`config_example.py` 同步）。
2. 新建 `lib/log_config.py`，实现 §3、§5；实现 InterceptHandler 与第三方降噪。
3. 根脚本改为使用 `lib` 或 `utils` 薄封装；删除或停用 `utils` 内旧 `FileHandler` 实现。
4. 按 §8 验收（含幂等、行号）。

**阶段 B（A 完成后立即做）** — **状态：已完成**

5. **backend/requirements.txt** 增加与根目录 **相同**的 **`loguru>=0.7.0`**；`main.py`（或 lifespan）调用同一 `setup_logging`；处理 uvicorn 与重复输出。  
   **实现说明**：`setup_logging` 支持第三参 **`log_config`**，后端 **`from config_new import LOG_CONFIG`** 传入，日志目录统一为**项目根** `logs/`（`_PROJECT_ROOT`）；`main.py` 注入项目根与 `backend` 到 `sys.path` 以便 `import lib` / `config_new`。
6. 再次验收：API 请求产生的业务日志进入 `combined-`/`error-`，reload 不重复。

---

## 8. 验收清单（阶段 A + B）

- [x] `logs/combined-当日.log` 与 `logs/error-当日.log` 生成；轮转后出现 `.gz`。
- [x] 终端仍有可读输出（若启用彩色 format，肉眼确认；无 ANSI 环境则确认纯文本可读）。
- [x] 根目录与 `backend/requirements.txt` 中 `loguru` 版本下限一致。
- [x] 人为 ERROR，error 文件有记录。
- [x] 业务模块行号正确（§3.7）（实现采用 `LogRecord.pathname`/`lineno` 写入 extra，真实脚本中为 `.py` 路径）。
- [x] 连续两次 `setup_logging()` 无重复行（§5）。
- [x] （B）uvicorn 启动 + reload 后仍满足上条（同进程幂等已测；请求为中间件 + `uvicorn.access` 两行来源，非重复 bug）。

---

## 9. 文档性质

- **唯一执行方案**：与日志改造相关的历史「可选/折中」讨论已收敛为本文；若与口头约定冲突，以 **本文 + 当时 `config` 键** 为准。

---

## 10. 实施备注（运维与排障）

- **Windows 下 `pip install -r backend/requirements.txt`**：若 `requirements.txt` 含 UTF-8 中文注释，可能触发 **GBK 解码错误**；可在 PowerShell 执行 **`$env:PYTHONUTF8="1"`** 后再安装，或将注释改为英文（见开发总结文档）。
- **轮转**：loguru 0.7.x `FileSink` 对 `rotation=[...]` 列表未统一解析时，实现中使用 **自定义可调用** 组合「午夜 OR 大小」，语义与 §3.2 一致。
