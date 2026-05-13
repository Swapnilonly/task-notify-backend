"""
utils/log_formatters.py
Emits every log record as a single JSON line.
Compatible with Datadog, Grafana Loki, AWS CloudWatch, ELK.
"""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    _SKIP = {
        "args", "created", "exc_info", "exc_text", "filename",
        "funcName", "id", "levelname", "levelno", "lineno",
        "message", "module", "msecs", "msg", "name", "pathname",
        "process", "processName", "relativeCreated", "stack_info",
        "taskName", "thread", "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.message,
            "module":    record.module,
            "func":      record.funcName,
            "line":      record.lineno,
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key not in self._SKIP and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)