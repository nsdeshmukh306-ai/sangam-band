"""
Structured JSON logging for the Sangam backend.
Call configure_logging() once at startup (done in backend/main.py lifespan).

Log format: one JSON object per line, fields:
  ts, level, logger, job_id?, case_id?, run_id?, msg, ...extra
"""

import json
import logging
import sys
import traceback
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Propagate structured context fields set via extra={}
        for field in ("job_id", "case_id", "run_id", "case_study", "tier"):
            val = getattr(record, field, None)
            if val is not None:
                obj[field] = val
        if record.exc_info:
            obj["exc"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        return json.dumps(obj)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Remove default handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
