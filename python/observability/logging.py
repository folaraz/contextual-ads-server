import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry._logs import set_logger_provider


_otel_log_provider: Optional[LoggerProvider] = None


def init_otel_logging(service_name: str, version: str = "1.0.0") -> Optional[LoggerProvider]:
    global _otel_log_provider

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: version,
        "environment": os.getenv("ENVIRONMENT", "development"),
    })

    try:
        exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
        _otel_log_provider = LoggerProvider(resource=resource)
        _otel_log_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        set_logger_provider(_otel_log_provider)
        return _otel_log_provider
    except Exception as e:
        print(f"[WARN] Failed to initialize OTel log exporter: {e}", file=sys.stderr)
        return None


class StructuredFormatter(logging.Formatter):
    def __init__(
            self,
            service_name: str = "unknown",
            environment: str = "development"
    ):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                     "logger": record.name, "message": record.getMessage(), "service": self.service_name,
                     "environment": self.environment, "source": {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }}

        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stacktrace": ''.join(traceback.format_exception(*record.exc_info))
            }

        return json.dumps(log_entry, default=str)


def setup_logging(
        service_name: str,
        level: str = "INFO",
        environment: Optional[str] = None,
        json_output: bool = True
) -> logging.Logger:
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if json_output:
        formatter = StructuredFormatter(
            service_name=service_name,
            environment=environment
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    provider = init_otel_logging(service_name)
    if provider is not None:
        otel_handler = LoggingHandler(level=log_level, logger_provider=provider)
        root_logger.addHandler(otel_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)

    return root_logger


class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

    def _log(self, level: int, message: str, **kwargs):
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown file)",
            0,
            message,
            (),
            None
        )
        record.extra_fields = kwargs
        self.logger.handle(record)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        if exc_info:
            kwargs['exc_info'] = sys.exc_info()
        self._log(logging.ERROR, message, **kwargs)

    def exception(self, message: str, **kwargs):
        kwargs['exc_info'] = sys.exc_info()
        self._log(logging.ERROR, message, **kwargs)

    def message_received(self, topic: str, partition: int, offset: int, key: Optional[str] = None):
        self.debug(
            "Message received",
            event="message_received",
            topic=topic,
            partition=partition,
            offset=offset,
            key=key
        )

    def message_processed(self, topic: str, duration_ms: float, status: str = "success"):
        self.info(
            "Message processed",
            event="message_processed",
            topic=topic,
            duration_ms=round(duration_ms, 2),
            status=status
        )

    def message_failed(self, topic: str, error: str, duration_ms: float):
        self.error(
            "Message processing failed",
            event="message_failed",
            topic=topic,
            error=error,
            duration_ms=round(duration_ms, 2)
        )

    def startup(self, version: str, config: Dict[str, Any]):
        self.info(
            "Service starting",
            event="startup",
            version=version,
            config=config
        )


def get_structured_logger(name: str = None) -> StructuredLogger:
    if name:
        return StructuredLogger(name)
    return StructuredLogger("default")
