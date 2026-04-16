import os
from typing import Optional

from .metrics import (
    MetricsManager,
    init_metrics,
    get_metrics_manager,
    record_message_processed,
    record_message_failed,
    record_processing_duration,
)

from .logging import (
    setup_logging,
    get_structured_logger,
)

from .tracing import (
    init_tracing,
    start_span,
    add_span_attributes,
    record_exception,
)


_initialized = False


def init_observability(
    service_name: str,
    version: str = "1.0.0",
    log_level: str = "INFO",
    environment: Optional[str] = None
):

    global _initialized

    if _initialized:
        return

    if environment is None:
        environment = os.getenv("ENVIRONMENT", "local")

    setup_logging(
        service_name=service_name,
        level=log_level,
        environment=environment,
        json_output=True
    )

    init_metrics(service_name, version)

    init_tracing(service_name, version)

    _initialized = True

    logger = get_structured_logger(service_name)
    logger.startup(version, {
        "environment": environment,
        "otel_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        "log_level": log_level,
    })


__all__ = [
    'init_observability',

    'MetricsManager',
    'get_metrics_manager',
    'record_message_processed',
    'record_message_failed',
    'record_processing_duration',

    'get_structured_logger',

    'start_span',
    'add_span_attributes',
    'record_exception',
]
