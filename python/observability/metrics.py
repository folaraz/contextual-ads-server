import os
from typing import Optional
from dataclasses import dataclass, field

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION


_meter: Optional[metrics.Meter] = None
_metrics_initialized = False


def init_metrics(service_name: str, version: str = "1.0.0") -> metrics.Meter:
    global _meter, _metrics_initialized

    if _metrics_initialized:
        return _meter

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: version,
        "environment": os.getenv("ENVIRONMENT", "development"),
    })

    exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=10000)

    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    _meter = metrics.get_meter(service_name, version)
    _metrics_initialized = True

    return _meter


def get_meter() -> metrics.Meter:
    global _meter
    if _meter is None:
        _meter = metrics.get_meter("contextual-ads-consumer")
    return _meter


@dataclass
class MetricsManager:
    consumer_name: str
    version: str = "1.0.0"
    _initialized: bool = field(default=False, init=False)

    _messages_processed: Optional[metrics.Counter] = field(default=None, init=False)
    _messages_failed: Optional[metrics.Counter] = field(default=None, init=False)
    _db_operations: Optional[metrics.Counter] = field(default=None, init=False)

    _processing_duration: Optional[metrics.Histogram] = field(default=None, init=False)

    def __post_init__(self):
        self._initialize_metrics()

    def _initialize_metrics(self):
        if self._initialized:
            return

        meter = init_metrics(self.consumer_name, self.version)

        self._messages_processed = meter.create_counter(
            name="kafka_messages_processed",
            description="Total Kafka messages processed",
            unit="1"
        )

        self._messages_failed = meter.create_counter(
            name="kafka_messages_failed",
            description="Total Kafka messages that failed processing",
            unit="1"
        )

        self._db_operations = meter.create_counter(
            name="db_operations",
            description="Total database operations",
            unit="1"
        )

        self._processing_duration = meter.create_histogram(
            name="kafka_message_processing_duration",
            description="Time spent processing a Kafka message",
            unit="s"
        )

        self._initialized = True

    def message_processed(self, topic: str, status: str = "success"):
        self._messages_processed.add(1, {
            "consumer": self.consumer_name,
            "topic": topic,
            "status": status
        })

    def message_failed(self, topic: str, error_type: str):
        self._messages_failed.add(1, {
            "consumer": self.consumer_name,
            "topic": topic,
            "error_type": error_type
        })

    def observe_processing_duration(self, topic: str, duration: float):
        self._processing_duration.record(duration, {
            "consumer": self.consumer_name,
            "topic": topic
        })

    def db_operation(self, operation: str, status: str, duration: float):
        attrs = {
            "consumer": self.consumer_name,
            "operation": operation,
            "status": status
        }
        self._db_operations.add(1, attrs)

    def record_pacing_calculation(self, campaign_id: str, multiplier: float, status: str):
        if not hasattr(self, '_pacing_calculations'):
            meter = get_meter()
            self._pacing_calculations = meter.create_counter(
                name="pacing_calculations_total",
                description="Total pacing calculations performed",
                unit="1"
            )
            self._pacing_multiplier = meter.create_histogram(
                name="pacing_multiplier",
                description="Pacing multiplier values",
                unit="1"
            )

        self._pacing_calculations.add(1, {
            "service": self.consumer_name,
            "status": status
        })
        if status == "ok":
            self._pacing_multiplier.record(multiplier, {
                "service": self.consumer_name,
                "campaign_id": campaign_id
            })


_metrics_manager: Optional[MetricsManager] = None


def get_metrics_manager(consumer_name: str = None) -> MetricsManager:
    global _metrics_manager
    if _metrics_manager is None:
        if consumer_name is None:
            consumer_name = "unknown_consumer"
        _metrics_manager = MetricsManager(consumer_name)
    return _metrics_manager


def record_message_processed(consumer: str, topic: str, status: str = "success"):
    get_metrics_manager(consumer).message_processed(topic, status)


def record_message_failed(consumer: str, topic: str, error_type: str):
    get_metrics_manager(consumer).message_failed(topic, error_type)


def record_processing_duration(consumer: str, topic: str, duration: float):
    get_metrics_manager(consumer).observe_processing_duration(topic, duration)
