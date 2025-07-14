"""
Prometheus metrics endpoint for Obsidian Post-Processor.

Provides metrics for monitoring processing performance and health.
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Prometheus metrics endpoint."""

    def __init__(self, metrics_collector, *args, **kwargs):
        self.metrics_collector = metrics_collector
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests for metrics."""
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            metrics_text = self.metrics_collector.get_prometheus_metrics()
            self.wfile.write(metrics_text.encode("utf-8"))

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "uptime": time.time() - self.metrics_collector.start_time,
            }
            self.wfile.write(json.dumps(health_data).encode("utf-8"))

        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        """Override to suppress default HTTP logging."""
        pass


class MetricsCollector:
    """Collects and exposes metrics for Prometheus."""

    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            # Processing metrics
            "obsidian_processor_operations_total": 0,
            "obsidian_processor_operations_success_total": 0,
            "obsidian_processor_operations_failed_total": 0,
            "obsidian_processor_processing_duration_seconds": 0,
            "obsidian_processor_files_processed_total": 0,
            "obsidian_processor_files_failed_total": 0,
            # Script execution metrics
            "obsidian_processor_script_executions_total": 0,
            "obsidian_processor_script_failures_total": 0,
            "obsidian_processor_script_duration_seconds": 0,
            # State management metrics
            "obsidian_processor_frontmatter_errors_total": 0,
            "obsidian_processor_notes_processed_total": 0,
            "obsidian_processor_voice_files_detected_total": 0,
            # System metrics
            "obsidian_processor_uptime_seconds": 0,
            "obsidian_processor_active_operations": 0,
        }
        self.histograms = {
            "processing_duration_buckets": [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            "processing_duration_counts": [0] * 8,
            "processing_duration_sum": 0,
            "processing_duration_count": 0,
            "script_duration_buckets": [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            "script_duration_counts": [0] * 8,
            "script_duration_sum": 0,
            "script_duration_count": 0,
        }
        self.lock = threading.Lock()

    def increment_counter(self, metric_name: str, value: int = 1):
        """Increment a counter metric."""
        with self.lock:
            if metric_name in self.metrics:
                self.metrics[metric_name] += value

    def set_gauge(self, metric_name: str, value: float):
        """Set a gauge metric."""
        with self.lock:
            if metric_name in self.metrics:
                self.metrics[metric_name] = value

    def observe_histogram(self, metric_name: str, value: float):
        """Observe a histogram metric."""
        with self.lock:
            if metric_name == "processing_duration":
                self.histograms["processing_duration_sum"] += value
                self.histograms["processing_duration_count"] += 1

                buckets = self.histograms["processing_duration_buckets"]
                counts = self.histograms["processing_duration_counts"]

                for i, bucket in enumerate(buckets):
                    if value <= bucket:
                        counts[i] += 1

            elif metric_name == "script_duration":
                self.histograms["script_duration_sum"] += value
                self.histograms["script_duration_count"] += 1

                buckets = self.histograms["script_duration_buckets"]
                counts = self.histograms["script_duration_counts"]

                for i, bucket in enumerate(buckets):
                    if value <= bucket:
                        counts[i] += 1

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        with self.lock:
            current_time = time.time()
            self.metrics["obsidian_processor_uptime_seconds"] = current_time - self.start_time

            lines = []

            # Counter metrics
            for metric_name, value in self.metrics.items():
                if metric_name.endswith("_total") or metric_name.endswith("_seconds"):
                    lines.append(f"# TYPE {metric_name} counter")
                    lines.append(f"{metric_name} {value}")
                else:
                    lines.append(f"# TYPE {metric_name} gauge")
                    lines.append(f"{metric_name} {value}")

            # Histogram metrics
            # Processing duration histogram
            lines.append("# TYPE obsidian_processor_processing_duration_seconds_bucket histogram")
            buckets = self.histograms["processing_duration_buckets"]
            counts = self.histograms["processing_duration_counts"]

            for i, bucket in enumerate(buckets):
                lines.append(f'obsidian_processor_processing_duration_seconds_bucket{{le="{bucket}"}} {counts[i]}')

            count = self.histograms["processing_duration_count"]
            lines.append(f'obsidian_processor_processing_duration_seconds_bucket{{le="+Inf"}} {count}')
            lines.append(
                f'obsidian_processor_processing_duration_seconds_sum {self.histograms["processing_duration_sum"]}'
            )
            lines.append(f"obsidian_processor_processing_duration_seconds_count {count}")

            # Script duration histogram
            lines.append("# TYPE obsidian_processor_script_duration_seconds_bucket histogram")
            buckets = self.histograms["script_duration_buckets"]
            counts = self.histograms["script_duration_counts"]

            for i, bucket in enumerate(buckets):
                lines.append(f'obsidian_processor_script_duration_seconds_bucket{{le="{bucket}"}} {counts[i]}')

            scount = self.histograms["script_duration_count"]
            lines.append(f'obsidian_processor_script_duration_seconds_bucket{{le="+Inf"}} {scount}')
            lines.append(f'obsidian_processor_script_duration_seconds_sum {self.histograms["script_duration_sum"]}')
            lines.append(f"obsidian_processor_script_duration_seconds_count {scount}")

            return "\n".join(lines) + "\n"

    def update_from_structured_logger(self, structured_logger):
        """Update metrics from structured logger data."""
        metrics_data = structured_logger.get_metrics()

        with self.lock:
            self.metrics["obsidian_processor_operations_total"] = metrics_data.get("operations_started", 0)
            self.metrics["obsidian_processor_operations_success_total"] = metrics_data.get("operations_completed", 0)
            self.metrics["obsidian_processor_operations_failed_total"] = metrics_data.get("operations_failed", 0)
            self.metrics["obsidian_processor_files_processed_total"] = metrics_data.get("files_processed", 0)
            self.metrics["obsidian_processor_files_failed_total"] = metrics_data.get("files_failed", 0)
            self.metrics["obsidian_processor_script_executions_total"] = metrics_data.get("script_executions", 0)
            self.metrics["obsidian_processor_script_failures_total"] = metrics_data.get("script_failures", 0)
            self.metrics["obsidian_processor_active_operations"] = metrics_data.get("active_operations", 0)


class MetricsServer:
    """HTTP server for exposing Prometheus metrics."""

    def __init__(self, port: int = 8000):
        self.port = port
        self.metrics_collector = MetricsCollector()
        self.server = None
        self.server_thread = None
        self.running = False

    def start(self):
        """Start the metrics server."""

        def handler_factory(*args, **kwargs):
            return MetricsHandler(self.metrics_collector, *args, **kwargs)

        self.server = HTTPServer(("", self.port), handler_factory)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.running = True

        logger.info(f"Metrics server started on port {self.port}")
        logger.info(f"Metrics endpoint: http://localhost:{self.port}/metrics")
        logger.info(f"Health endpoint: http://localhost:{self.port}/health")

    def stop(self):
        """Stop the metrics server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.running = False
            logger.info("Metrics server stopped")

    def get_metrics_collector(self) -> MetricsCollector:
        """Get the metrics collector instance."""
        return self.metrics_collector

    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.running
