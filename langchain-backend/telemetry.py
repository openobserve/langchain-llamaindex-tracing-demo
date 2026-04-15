import os
import logging
from urllib.parse import urljoin

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def init_telemetry():
    openobserve_url = os.getenv("OPENOBSERVE_URL")
    org = os.getenv("OPENOBSERVE_ORG")
    auth_token = os.getenv("OPENOBSERVE_AUTH_TOKEN")
    service_name = os.getenv("SERVICE_NAME", "langchain-rag-demo")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    if not openobserve_url or not org or not auth_token:
        raise RuntimeError("OPENOBSERVE_URL, OPENOBSERVE_ORG, and OPENOBSERVE_AUTH_TOKEN must be set.")

    endpoint = openobserve_url.rstrip("/") + f"/api/{org}/v1/traces"

    resource = Resource.create({
        "service.name": service_name,
        "deployment.environment": os.getenv("ENVIRONMENT", "local"),
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, headers={"Authorization": auth_token})
    provider.add_span_processor(BatchSpanProcessor(exporter))

    if debug:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Added ConsoleSpanExporter because DEBUG=true")

    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry initialized for service %s", service_name)
    return provider
