"""
根脚本与（阶段 B）FastAPI 共用的日志初始化：loguru 落盘 + 标准库 logging 拦截。

禁止在此模块 import 业务代码（database、data_sync 等）。
未传入 log_config 时默认读取项目根 config.LOG_CONFIG；后端可传入 config_new.LOG_CONFIG 以解耦。
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Callable, Dict, Optional

from loguru import logger

# 幂等：重复调用 setup_logging（如 uvicorn reload）时不重复挂载 sink
_LOGGING_CONFIGURED = False


def _bytes_to_rotation_size(n: int) -> str:
    """将字节数转为 loguru rotation 可识别的字符串（见 LOG_CONFIG max_bytes）。"""
    if n >= 1024 * 1024:
        mb = max(1, n // (1024 * 1024))
        return f"{mb} MB"
    if n >= 1024:
        kb = max(1, n // 1024)
        return f"{kb} KB"
    return f"{n} B"


def _rotation_or_midnight_and_size(midnight: str, size_label: str) -> Callable[..., bool]:
    """
    组合「本地午夜」与「单文件大小」两种轮转条件，语义与文档中的 rotation=[...]「或」一致。
    （当前 loguru 0.7.x 的 FileSink 对 list 型 rotation 未统一解析，故用手工 OR。）
    """
    from loguru._file_sink import FileSink

    fn_time = FileSink._make_rotation_function(midnight)
    fn_size = FileSink._make_rotation_function(size_label)

    def _or(message: Any, file: Any) -> bool:
        return bool(fn_time(message, file)) or bool(fn_size(message, file))

    return _or


class InterceptHandler(logging.Handler):
    """
    将标准库 logging 记录转发到 loguru，便于业务继续用 logging.getLogger(__name__)。
    通过 opt(depth=...) 跳过 logging 内部栈帧，使行号/文件指向业务调用处（方案 §3.7）。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        # 行号/文件用标准库 LogRecord（与业务 logging.info 调用一致），避免仅依赖 opt(depth) 在部分环境下变成 <unknown>:0
        logger.bind(
            logging_name=record.name,
            log_path=record.pathname,
            log_line=record.lineno,
        ).opt(exception=record.exc_info).log(level, record.getMessage())


def _suppress_noisy_loggers() -> None:
    """第三方库在根级别为 DEBUG 时降噪；不屏蔽业务 logger。"""
    for name in (
        "urllib3",
        "urllib3.connectionpool",
        "requests",
        "sqlalchemy",
        "sqlalchemy.engine",
        "botocore",
        "httpx",
        "httpcore",
        "charset_normalizer",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging(
    log_file: str | None = None,
    log_level: str | None = None,
    log_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    初始化日志：combined / error 文件、gzip、保留策略、控制台输出，并拦截标准库 logging。

    log_file：沿用旧参数，用于解析日志目录（例如 logs/app.log -> logs/）；不再写入 app.log。
    log_level：与 LOG_CONFIG['log_level'] 一致时作用于 combined 与控制台。
    log_config：完整 LOG_CONFIG 字典；若省略则从项目根 config 模块读取（根脚本兼容）。
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    if log_config is not None:
        lc: Dict[str, Any] = log_config
    else:
        from config import LOG_CONFIG as _root_lc

        lc = _root_lc
    path_for_dir = log_file if log_file is not None else lc["log_file"]
    level_str = (log_level if log_level is not None else lc["log_level"]).upper()

    log_dir = os.path.dirname(os.path.abspath(path_for_dir))
    if not log_dir:
        log_dir = lc.get("log_dir", "logs")
    os.makedirs(log_dir, exist_ok=True)

    max_bytes = int(lc.get("max_bytes", 10 * 1024 * 1024))
    midnight = str(lc.get("rotation_midnight", "00:00"))
    retention = str(lc.get("retention", "30 days"))
    enable_json = bool(lc.get("enable_json_log", False))
    error_diagnose = bool(lc.get("error_diagnose", False))

    size_str = _bytes_to_rotation_size(max_bytes)
    # 注：达到大小阈值或到达本地零点，任一发生即触发轮转（阈值见 LOG_CONFIG max_bytes / rotation_midnight）。
    rotation = _rotation_or_midnight_and_size(midnight, size_str)

    file_fmt = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[logging_name]} | "
        "{extra[log_path]}:{extra[log_line]} - {message}\n"
    )
    console_fmt = (
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{extra[logging_name]}</cyan> | "
        "<cyan>{extra[log_path]}</cyan>:<cyan>{extra[log_line]}</cyan> - <level>{message}</level>"
    )

    def _patch(record: Any) -> None:
        # loguru 原生日志无 logging_name/log_path 时从 record 补全，便于 combined 格式统一
        extra = record["extra"]
        if "logging_name" not in extra:
            extra["logging_name"] = record["name"]
        if "log_path" not in extra:
            try:
                extra["log_path"] = record["file"].path
            except (AttributeError, KeyError, ValueError):
                extra["log_path"] = "?"
        if "log_line" not in extra:
            try:
                extra["log_line"] = record["line"]
            except (KeyError, TypeError):
                extra["log_line"] = 0

    logger.remove()
    combined_path = os.path.join(log_dir, "combined-{time:YYYY-MM-DD}.log")
    error_path = os.path.join(log_dir, "error-{time:YYYY-MM-DD}.log")

    logger.configure(patcher=_patch)

    logger.add(
        combined_path,
        level=level_str,
        format=file_fmt,
        rotation=rotation,
        compression="gz",
        retention=retention,
        enqueue=True,
        encoding="utf-8",
    )
    logger.add(
        error_path,
        level="ERROR",
        format=file_fmt,
        rotation=rotation,
        compression="gz",
        retention=retention,
        enqueue=True,
        encoding="utf-8",
        diagnose=error_diagnose,
    )
    logger.add(
        sys.stdout,
        level=level_str,
        format=console_fmt,
        colorize=True,
        enqueue=False,
    )

    if enable_json:
        json_path = os.path.join(log_dir, "json-{time:YYYY-MM-DD}.log")
        logger.add(
            json_path,
            level=level_str,
            serialize=True,
            rotation=rotation,
            compression="gz",
            retention=retention,
            enqueue=True,
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    _suppress_noisy_loggers()
    _LOGGING_CONFIGURED = True
