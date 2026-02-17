import json
import logging
import logging.config
import os
from datetime import datetime, timezone

from .context import get_correlation_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in (
            "event",
            "correlation_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error",
            "trigger",
            "reason",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            cid = get_correlation_id()
            if cid:
                record.correlation_id = cid
        return True


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": JsonFormatter,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["correlation_id"],
                }
            },
            "filters": {
                "correlation_id": {
                    "()": CorrelationIdFilter,
                }
            },
            "root": {"handlers": ["console"], "level": level},
        }
    )
