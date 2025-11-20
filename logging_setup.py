# logging_setup.py
import logging
import logging.handlers
import os
import json
from typing import Optional

DEFAULT_LEVEL = "INFO"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "smart_trader.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5

NOISY_LIBS = ("urllib3", "requests")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _level_from_str(level: Optional[str]) -> int:
    if not level:
        return logging.INFO
    return getattr(logging, str(level).upper(), logging.INFO)


def _make_rotating_handler(
    path: str,
    level: int,
    formatter: logging.Formatter,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Handler:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    return fh


def setup_logging(
    level: str = DEFAULT_LEVEL,
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    json_console: bool = False,
    quiet_noisy_libs: bool = True,
) -> logging.Logger:
    """
    Initialize the root 'smart_trader' logger with console + rotating file handlers.

    Params:
    - level: base log level (string like "INFO", "DEBUG").
    - log_dir, log_file: where to store the rotating logs.
    - max_bytes, backup_count: rotation config.
    - json_console: if True, console logs in JSON; else human-readable.
    - quiet_noisy_libs: if True, sets common noisy libs to WARNING.

    Returns:
    - The configured 'smart_trader' logger.
    """
    # Env overrides (ops-friendly)
    level = os.getenv("LOG_LEVEL", level)
    log_dir = os.getenv("LOG_DIR", log_dir)

    logger_name = "smart_trader"
    logger = logging.getLogger(logger_name)
    logger.setLevel(_level_from_str(level))
    logger.propagate = False

    # Clear existing handlers to allow re-init without duplicates
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    # Console handler
    if json_console:
        ch_formatter = JsonFormatter()
    else:
        ch_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    ch = logging.StreamHandler()
    ch.setLevel(_level_from_str(level))
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    # File handler (rotating)
    fh_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_path = os.path.join(log_dir, log_file)
    fh = _make_rotating_handler(
        file_path, _level_from_str(level), fh_formatter, max_bytes, backup_count
    )
    logger.addHandler(fh)

    # Quiet noisy libs globally
    if quiet_noisy_libs:
        for noisy in NOISY_LIBS:
            logging.getLogger(noisy).setLevel(logging.WARNING)

    # Optional: also reduce root logger chatter if needed
    root = logging.getLogger()
    if not root.handlers:
        # Keep root minimal to avoid duplicate console prints from other libs
        root.setLevel(logging.WARNING)

    logger.debug(
        "Logging initialized",
        extra={
            "log_dir": log_dir,
            "log_file": log_file,
            "level": level,
            "json_console": json_console,
        },
    )
    return logger


def get_child_logger(
    parent_name: str,
    child_name: str,
    log_dir: str = DEFAULT_LOG_DIR,
    filename: Optional[str] = None,
    level: Optional[str] = None,
    add_console: bool = False,
    json_console: bool = False,
) -> logging.Logger:
    """
    Create a child logger with its own rotating file handler.

    Example:
        get_child_logger("smart_trader", "telegram", filename="telegram.log", level="INFO")

    Params:
    - parent_name, child_name: names combined as 'parent.child'.
    - log_dir: directory for file logs.
    - filename: file name for the child logger (defaults to f"{child_name}.log").
    - level: child-specific level; defaults to parent's effective level.
    - add_console: if True, also attach a console handler to the child logger.
    - json_console: console in JSON if add_console is True.
    """
    os.makedirs(log_dir, exist_ok=True)
    lname = f"{parent_name}.{child_name}"
    clog = logging.getLogger(lname)
    clog.propagate = False

    eff_level = _level_from_str(level) if level else logging.getLogger(parent_name).level
    clog.setLevel(eff_level)

    # Clear existing handlers to avoid duplication on re-init
    if clog.handlers:
        for h in list(clog.handlers):
            clog.removeHandler(h)

    # File handler
    file_name = filename or f"{child_name}.log"
    fh_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    path = os.path.join(log_dir, file_name)
    fh = _make_rotating_handler(path, eff_level, fh_formatter)
    clog.addHandler(fh)

    # Optional console handler
    if add_console:
        if json_console:
            ch_formatter = JsonFormatter()
        else:
            ch_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        ch = logging.StreamHandler()
        ch.setLevel(eff_level)
        ch.setFormatter(ch_formatter)
        clog.addHandler(ch)

    return clog
