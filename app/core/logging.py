import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in ("task_id", "duration_ms", "error_code"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
