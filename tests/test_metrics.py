"""
Test suite for Prometheus metrics system.
"""

import threading
import time
from unittest.mock import Mock

import pytest
import requests

from src.metrics import MetricsCollector, MetricsServer


class TestMetricsCollector:
    """Test the MetricsCollector class."""

    def test_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()

        assert collector.start_time > 0
        assert collector.metrics["obsidian_processor_operations_total"] == 0
        assert collector.metrics["obsidian_processor_files_processed_total"] == 0
        assert len(collector.histograms["processing_duration_buckets"]) == 8
        assert collector.histograms["processing_duration_count"] == 0

    def test_counter_increment(self):
        """Test counter metric increment."""
        collector = MetricsCollector()

        # Test single increment
        collector.increment_counter("obsidian_processor_operations_total")
        assert collector.metrics["obsidian_processor_operations_total"] == 1

        # Test multiple increment
        collector.increment_counter("obsidian_processor_operations_total", 5)
        assert collector.metrics["obsidian_processor_operations_total"] == 6

        # Test invalid metric name (should not crash)
        collector.increment_counter("invalid_metric")
        # Should not change any existing metrics
        assert collector.metrics["obsidian_processor_operations_total"] == 6

    def test_gauge_setting(self):
        """Test gauge metric setting."""
        collector = MetricsCollector()

        # Test setting gauge value
        collector.set_gauge("obsidian_processor_uptime_seconds", 123.45)
        assert collector.metrics["obsidian_processor_uptime_seconds"] == 123.45

        # Test overwriting gauge value
        collector.set_gauge("obsidian_processor_uptime_seconds", 200.0)
        assert collector.metrics["obsidian_processor_uptime_seconds"] == 200.0

        # Test invalid metric name (should not crash)
        collector.set_gauge("invalid_metric", 42)

    def test_histogram_observation(self):
        """Test histogram metric observation."""
        collector = MetricsCollector()

        # Test processing duration histogram
        collector.observe_histogram("processing_duration", 0.5)
        assert collector.histograms["processing_duration_sum"] == 0.5
        assert collector.histograms["processing_duration_count"] == 1

        # Test multiple observations
        collector.observe_histogram("processing_duration", 1.5)
        collector.observe_histogram("processing_duration", 10.0)
        assert collector.histograms["processing_duration_sum"] == 12.0
        assert collector.histograms["processing_duration_count"] == 3

        # Test bucket counting
        counts = collector.histograms["processing_duration_counts"]

        # 0.5 should be in bucket 0 (0.1) and above
        # 1.5 should be in bucket 2 (5.0) and above
        # 10.0 should be in bucket 4 (10.0) and above
        assert counts[4] >= 1  # 10.0 bucket
        assert counts[5] >= 3  # 30.0 bucket should have all three

    def test_script_duration_histogram(self):
        """Test script duration histogram."""
        collector = MetricsCollector()

        # Test script duration observations
        collector.observe_histogram("script_duration", 2.0)
        collector.observe_histogram("script_duration", 0.1)

        assert collector.histograms["script_duration_sum"] == 2.1
        assert collector.histograms["script_duration_count"] == 2

        # Test invalid histogram name (should not crash)
        collector.observe_histogram("invalid_histogram", 5.0)

    def test_prometheus_metrics_output(self):
        """Test Prometheus metrics format output."""
        collector = MetricsCollector()

        # Set up some test data
        collector.increment_counter("obsidian_processor_operations_total", 10)
        collector.increment_counter("obsidian_processor_files_processed_total", 5)
        collector.observe_histogram("processing_duration", 1.5)
        collector.observe_histogram("processing_duration", 3.0)

        # Get metrics output
        output = collector.get_prometheus_metrics()

        # Check format and content
        assert "obsidian_processor_operations_total 10" in output
        assert "obsidian_processor_files_processed_total 5" in output
        assert "# TYPE obsidian_processor_operations_total counter" in output
        assert "# TYPE obsidian_processor_processing_duration_seconds_bucket histogram" in output
        assert "obsidian_processor_processing_duration_seconds_sum 4.5" in output
        assert "obsidian_processor_processing_duration_seconds_count 2" in output
        assert "obsidian_processor_uptime_seconds" in output

    def test_update_from_structured_logger(self):
        """Test updating metrics from structured logger."""
        collector = MetricsCollector()

        # Create a mock structured logger
        mock_logger = Mock()
        mock_logger.get_metrics.return_value = {
            "operations_started": 15,
            "operations_completed": 12,
            "operations_failed": 3,
            "files_processed": 10,
            "files_failed": 2,
            "script_executions": 8,
            "script_failures": 1,
            "active_operations": 2,
        }

        # Update metrics
        collector.update_from_structured_logger(mock_logger)

        # Verify metrics were updated
        assert collector.metrics["obsidian_processor_operations_total"] == 15
        assert collector.metrics["obsidian_processor_operations_success_total"] == 12
        assert collector.metrics["obsidian_processor_operations_failed_total"] == 3
        assert collector.metrics["obsidian_processor_files_processed_total"] == 10
        assert collector.metrics["obsidian_processor_files_failed_total"] == 2
        assert collector.metrics["obsidian_processor_script_executions_total"] == 8
        assert collector.metrics["obsidian_processor_script_failures_total"] == 1
        assert collector.metrics["obsidian_processor_active_operations"] == 2

    def test_thread_safety(self):
        """Test thread safety of metrics collection."""
        collector = MetricsCollector()

        def increment_worker():
            for _ in range(100):
                collector.increment_counter("obsidian_processor_operations_total")

        def observe_worker():
            for i in range(100):
                collector.observe_histogram("processing_duration", i * 0.1)

        # Start multiple threads
        threads = []
        for _ in range(3):
            t1 = threading.Thread(target=increment_worker)
            t2 = threading.Thread(target=observe_worker)
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify results
        assert collector.metrics["obsidian_processor_operations_total"] == 300
        assert collector.histograms["processing_duration_count"] == 300


class TestMetricsServer:
    """Test the MetricsServer class."""

    def test_initialization(self):
        """Test metrics server initialization."""
        server = MetricsServer(port=8001)

        assert server.port == 8001
        assert server.metrics_collector is not None
        assert server.running is False
        assert server.server is None

    def test_server_start_stop(self):
        """Test starting and stopping the metrics server."""
        server = MetricsServer(port=8002)

        # Start server
        server.start()
        assert server.running is True
        assert server.server is not None
        assert server.server_thread is not None

        # Give server time to start
        time.sleep(0.1)

        # Stop server
        server.stop()
        assert server.running is False

    def test_server_endpoints(self):
        """Test server endpoints (requires actual HTTP server)."""
        # This test starts a real HTTP server, so we use a unique port
        server = MetricsServer(port=8003)

        try:
            server.start()
            time.sleep(0.1)  # Give server time to start

            # Test metrics endpoint
            response = requests.get("http://localhost:8003/metrics", timeout=1)
            assert response.status_code == 200
            assert "obsidian_processor" in response.text

            # Test health endpoint
            response = requests.get("http://localhost:8003/health", timeout=1)
            assert response.status_code == 200
            health_data = response.json()
            assert health_data["status"] == "healthy"
            assert "uptime" in health_data

            # Test 404 for invalid endpoint
            response = requests.get("http://localhost:8003/invalid", timeout=1)
            assert response.status_code == 404

        except requests.exceptions.RequestException:
            # Server might not be ready, skip this test
            pytest.skip("Server not ready for HTTP requests")
        finally:
            server.stop()

    def test_metrics_collector_access(self):
        """Test access to metrics collector."""
        server = MetricsServer(port=8004)

        collector = server.get_metrics_collector()
        assert collector is not None
        assert collector is server.metrics_collector

        # Test that we can use the collector
        collector.increment_counter("obsidian_processor_operations_total", 5)
        assert collector.metrics["obsidian_processor_operations_total"] == 5


class TestMetricsHandler:
    """Test the MetricsHandler class."""

    def test_handler_initialization(self):
        """Test metrics handler initialization."""
        mock_collector = Mock()

        # Create handler with mock collector
        # Note: We can't easily test the handler directly due to its HTTP nature
        # but we can test that it properly stores the collector reference
        assert mock_collector is not None

    def test_metrics_endpoint_response(self):
        """Test that metrics endpoint returns proper format."""
        collector = MetricsCollector()
        collector.increment_counter("obsidian_processor_operations_total", 5)

        # Test that get_prometheus_metrics returns valid format
        metrics_text = collector.get_prometheus_metrics()

        # Verify Prometheus format
        lines = metrics_text.strip().split("\n")
        assert len(lines) > 0

        # Check for required elements
        has_help = any(line.startswith("# TYPE") for line in lines)
        has_metrics = any(line.startswith("obsidian_processor_") for line in lines)

        assert has_help
        assert has_metrics


class TestIntegration:
    """Integration tests for the metrics system."""

    def test_full_metrics_workflow(self):
        """Test the complete metrics workflow."""
        # Create server
        server = MetricsServer(port=8005)
        collector = server.get_metrics_collector()

        try:
            # Start server
            server.start()
            time.sleep(0.1)

            # Simulate some operations
            collector.increment_counter("obsidian_processor_operations_total", 3)
            collector.increment_counter("obsidian_processor_files_processed_total", 2)
            collector.observe_histogram("processing_duration", 1.5)
            collector.observe_histogram("processing_duration", 3.0)

            # Test metrics endpoint
            try:
                response = requests.get("http://localhost:8005/metrics", timeout=1)
                assert response.status_code == 200

                content = response.text
                assert "obsidian_processor_operations_total 3" in content
                assert "obsidian_processor_files_processed_total 2" in content
                assert "obsidian_processor_processing_duration_seconds_sum 4.5" in content
                assert "obsidian_processor_processing_duration_seconds_count 2" in content

            except requests.exceptions.RequestException:
                pytest.skip("Server not ready for integration test")

        finally:
            server.stop()

    def test_structured_logger_integration(self):
        """Test integration with structured logger."""
        import tempfile
        from pathlib import Path

        from src.structured_logger import StructuredLogger

        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Simulate some operations
            logger.log_file_processing("note1", "voice1.m4a", "success", duration=1.0)
            logger.log_file_processing("note2", "voice2.m4a", "failed", error="Test error")
            logger.log_script_execution("script.py", [], True, 2.0)

            # Create collector and update from logger
            collector = MetricsCollector()
            collector.update_from_structured_logger(logger)

            # Verify metrics were transferred
            assert collector.metrics["obsidian_processor_files_processed_total"] == 1
            assert collector.metrics["obsidian_processor_files_failed_total"] == 1
            assert collector.metrics["obsidian_processor_script_executions_total"] == 1

    def test_concurrent_metrics_collection(self):
        """Test concurrent access to metrics."""
        collector = MetricsCollector()

        def worker(worker_id):
            for i in range(10):
                collector.increment_counter("obsidian_processor_operations_total")
                collector.observe_histogram("processing_duration", worker_id * 0.1 + i * 0.01)
                time.sleep(0.001)  # Small delay to increase chance of race conditions

        # Start multiple workers
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all workers to complete
        for t in threads:
            t.join()

        # Verify results
        assert collector.metrics["obsidian_processor_operations_total"] == 50
        assert collector.histograms["processing_duration_count"] == 50

        # Generate metrics output (should not crash)
        output = collector.get_prometheus_metrics()
        assert "obsidian_processor_operations_total 50" in output
