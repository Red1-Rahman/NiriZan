# src\nirizan\instrumentation\otel\to_otel.py
import logging
import os
from typing import Optional

from opentelemetry import metrics, trace, _logs
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor


def init_telemetry(
    service_name: str = "my-python-service",
    service_version: str = "1.0.0",
    endpoint: Optional[str] = None,
    insecure: bool = True,
) -> trace.Tracer:
    """
    Initializes OpenTelemetry Providers (Traces, Metrics, Logs) and exports to an OTLP Collector.

    Default endpoint checks 'OTEL_EXPORTER_OTLP_ENDPOINT' or defaults to localhost:4317.
    """
    otlp_endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Define common resource attributes
    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
        }
    )

    # 1. Tracing Setup
    tracer_provider = TracerProvider(resource=resource)
    span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=insecure))
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # 2. Metrics Setup
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=insecure)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # 3. Logging Setup
    logger_provider = LoggerProvider(resource=resource)
    log_processor = BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=otlp_endpoint, insecure=insecure)
    )
    logger_provider.add_log_record_processor(log_processor)
    _logs.set_logger_provider(logger_provider)

    # Attach OpenTelemetry handler to standard Python logging
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    return trace.get_tracer(service_name)
