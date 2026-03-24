"""
Centralized logging configuration for the Scanner service.

Log files:
  /app/logs/scanner.log       — all logs (DEBUG+), rotated at 10MB, 5 backups
  /app/logs/auth.log          — auth-specific logs (DEBUG+), rotated at 10MB, 3 backups  
  /app/logs/scan.log          — scan/crawl logs (DEBUG+), rotated at 10MB, 3 backups
  /app/logs/error.log         — errors only (ERROR+), rotated at 5MB, 3 backups
"""

import logging
import logging.handlers
import os
import sys

LOG_DIR = os.environ.get("LOG_DIR", "/app/logs")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
MAX_BYTES = 10 * 1024 * 1024   # 10 MB per file
BACKUP_COUNT = 5


def setup_logging():
    """Configure logging for the entire scanner service."""
    os.makedirs(LOG_DIR, exist_ok=True)

    # ── Root scanner logger ─────────────────────────────────────────
    root_logger = logging.getLogger("scanner")
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    # Format with timestamp, level, module, function, line
    detailed_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s.%(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    short_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 1. Console handler (INFO+)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(short_fmt)
    root_logger.addHandler(console)

    # 2. Main log file (DEBUG+) — everything
    main_file = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "scanner.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    main_file.setLevel(logging.DEBUG)
    main_file.setFormatter(detailed_fmt)
    root_logger.addHandler(main_file)

    # 3. Error-only file (ERROR+)
    error_file = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(detailed_fmt)
    root_logger.addHandler(error_file)

    # ── Auth logger — separate file ─────────────────────────────────
    auth_logger = logging.getLogger("scanner.auth")
    auth_file = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "auth.log"),
        maxBytes=MAX_BYTES,
        backupCount=3,
        encoding="utf-8",
    )
    auth_file.setLevel(logging.DEBUG)
    auth_file.setFormatter(detailed_fmt)
    auth_logger.addHandler(auth_file)

    # ── Scan/Crawl logger — separate file ───────────────────────────
    for name in ("scanner.engine", "scanner.spa_crawler"):
        scan_logger = logging.getLogger(name)
        scan_file = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "scan.log"),
            maxBytes=MAX_BYTES,
            backupCount=3,
            encoding="utf-8",
        )
        scan_file.setLevel(logging.DEBUG)
        scan_file.setFormatter(detailed_fmt)
        scan_logger.addHandler(scan_file)

    # ── Module loggers ──────────────────────────────────────────────
    for name in ("scanner.modules.robots", "scanner.modules.sitemap",
                 "scanner.modules.bruteforce", "scanner.modules.html",
                 "scanner.modules.js", "scanner.recorder"):
        mod_logger = logging.getLogger(name)
        mod_file = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "scan.log"),
            maxBytes=MAX_BYTES,
            backupCount=3,
            encoding="utf-8",
        )
        mod_file.setLevel(logging.DEBUG)
        mod_file.setFormatter(detailed_fmt)
        mod_logger.addHandler(mod_file)

    root_logger.info(
        f"Logging initialized: dir={LOG_DIR}, level={LOG_LEVEL}, "
        f"files=[scanner.log, auth.log, scan.log, error.log]"
    )

    return root_logger


def get_log_content(log_name: str = "scanner", lines: int = 500, level: str = None) -> list[dict]:
    """
    Read log file and return structured entries.
    
    Args:
        log_name: "scanner", "auth", "scan", or "error"
        lines: Number of lines to return (from end)
        level: Filter by level ("DEBUG", "INFO", "WARNING", "ERROR")
    
    Returns:
        List of dicts: [{timestamp, level, module, message}, ...]
    """
    filename = f"{log_name}.log"
    filepath = os.path.join(LOG_DIR, filename)
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception:
        return []
    
    # Take last N lines
    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    entries = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        
        # Parse: "2026-03-24 12:00:00 [DEBUG] scanner.auth.recorded_flow_login:123 — message"
        entry = {"raw": line}
        try:
            # Try to parse structured log
            parts = line.split(" — ", 1)
            if len(parts) == 2:
                header, message = parts
                entry["message"] = message
                
                # Extract level
                for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
                    if f"[{lvl}" in header:
                        entry["level"] = lvl
                        break
                
                # Extract timestamp (first 19 chars)
                if len(header) >= 19:
                    entry["timestamp"] = header[:19]
                
                # Extract module
                bracket_end = header.find("]")
                if bracket_end > 0 and bracket_end + 2 < len(header):
                    rest = header[bracket_end + 2:].strip()
                    entry["module"] = rest
            else:
                entry["message"] = line
        except Exception:
            entry["message"] = line
        
        # Filter by level if specified
        if level and entry.get("level") != level:
            continue
        
        entries.append(entry)
    
    return entries


def get_log_files_info() -> list[dict]:
    """Return info about all log files (name, size, modified)."""
    if not os.path.exists(LOG_DIR):
        return []
    
    files = []
    for name in os.listdir(LOG_DIR):
        if name.endswith(".log"):
            path = os.path.join(LOG_DIR, name)
            stat = os.stat(path)
            files.append({
                "name": name,
                "size": stat.st_size,
                "size_human": _human_size(stat.st_size),
                "modified": stat.st_mtime,
            })
    
    return sorted(files, key=lambda x: x["name"])


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
