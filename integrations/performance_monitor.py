"""
Performance Monitor for GitHub Webhooks.

This module provides real-time performance monitoring, metrics collection,
and alerting capabilities for webhook processing.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import time
import statistics
from collections import deque
from mas_core.utils.logging import MASLogger

class PerformanceMetric:
    """Performance metric with rolling window statistics."""

    def __init__(self, window_size: int = 100) -> None:
        """Initialize metric with window size."""
        self.values = deque(maxlen=window_size)
        self.window_size = window_size

    def add(self, value: float) -> None:
        """Add value to metric window."""
        self.values.append(value)

    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary of metric."""
        if not self.values:
            return {
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p95": 0.0,
                "p99": 0.0
            }

        values_list = list(self.values)
        sorted_values = sorted(values_list)
        p95_idx = int(len(values_list) * 0.95)
        p99_idx = int(len(values_list) * 0.99)

        return {
            "avg": statistics.mean(values_list),
            "min": min(values_list),
            "max": max(values_list),
            "p95": sorted_values[p95_idx],
            "p99": sorted_values[p99_idx]
        }

class PerformanceMonitor:
    """Performance monitoring system for webhook processing."""

    def __init__(self) -> None:
        """Initialize performance monitor."""
        self.logger = MASLogger("performance_monitor")
        self._metrics = {
            "processing_time": PerformanceMetric(),
            "payload_size": PerformanceMetric(),
            "queue_length": PerformanceMetric()
        }
        self._error_counts = {}
        self._last_alert = {}
        self._alert_thresholds = {
            "processing_time": 5.0,  # seconds
            "error_rate": 0.1,  # 10% error rate
            "queue_length": 100  # tasks
        }

    def start_operation(self, operation_id: str) -> None:
        """
        Start timing an operation.

        Args:
            operation_id: Unique operation identifier
        """
        self._metrics[f"operation_{operation_id}_start"] = time.time()

    def end_operation(self, operation_id: str, metadata: Dict[str, Any] = None) -> float:
        """
        End timing an operation and record metrics.

        Args:
            operation_id: Operation identifier
            metadata: Additional operation metadata

        Returns:
            float: Operation duration in seconds
        """
        start_time = self._metrics.pop(f"operation_{operation_id}_start", None)
        if start_time is None:
            self.logger.log_error(
                error_type="monitoring_error",
                message=f"No start time found for operation {operation_id}",
                context={"metadata": metadata}
            )
            return 0.0

        duration = time.time() - start_time
        self._metrics["processing_time"].add(duration)

        if metadata:
            if "payload_size" in metadata:
                self._metrics["payload_size"].add(metadata["payload_size"])
            if "queue_length" in metadata:
                self._metrics["queue_length"].add(metadata["queue_length"])

        self._check_thresholds(operation_id, duration, metadata)
        return duration

    def record_error(self, error_type: str, details: Dict[str, Any]) -> None:
        """
        Record an error occurrence.

        Args:
            error_type: Type of error
            details: Error details
        """
        if error_type not in self._error_counts:
            self._error_counts[error_type] = {
                "count": 0,
                "first_seen": datetime.now(timezone.utc),
                "last_seen": None
            }

        self._error_counts[error_type]["count"] += 1
        self._error_counts[error_type]["last_seen"] = datetime.now(timezone.utc)

        self._check_error_thresholds(error_type)

    def get_metrics(self, metric_names: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        """
        Get current metrics.

        Args:
            metric_names: Optional list of specific metrics to retrieve

        Returns:
            Dict of metric statistics
        """
        if metric_names is None:
            metric_names = list(self._metrics.keys())

        return {
            name: self._metrics[name].get_stats()
            for name in metric_names
            if name in self._metrics and isinstance(self._metrics[name], PerformanceMetric)
        }

    def get_error_stats(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get error statistics.

        Args:
            time_window: Optional time window to filter errors

        Returns:
            Dict of error statistics by type
        """
        now = datetime.now(timezone.utc)
        stats = {}

        for error_type, data in self._error_counts.items():
            if time_window and (now - data["last_seen"]) > time_window:
                continue

            stats[error_type] = {
                "count": data["count"],
                "first_seen": data["first_seen"].isoformat(),
                "last_seen": data["last_seen"].isoformat()
            }

        return stats

    def _check_thresholds(
        self,
        operation_id: str,
        duration: float,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Check metric thresholds and trigger alerts if needed."""
        # Check processing time
        if duration > self._alert_thresholds["processing_time"]:
            self._trigger_alert(
                "high_processing_time",
                {
                    "operation_id": operation_id,
                    "duration": duration,
                    "threshold": self._alert_thresholds["processing_time"],
                    "metadata": metadata
                }
            )

        # Check queue length
        if metadata and "queue_length" in metadata:
            if metadata["queue_length"] > self._alert_thresholds["queue_length"]:
                self._trigger_alert(
                    "high_queue_length",
                    {
                        "queue_length": metadata["queue_length"],
                        "threshold": self._alert_thresholds["queue_length"]
                    }
                )

    def _check_error_thresholds(self, error_type: str) -> None:
        """Check error rate thresholds."""
        window_start = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent_errors = sum(
            1 for data in self._error_counts.values()
            if data["last_seen"] >= window_start
        )
        
        total_ops = len(self._metrics["processing_time"].values)
        if total_ops > 0:
            error_rate = recent_errors / total_ops
            if error_rate > self._alert_thresholds["error_rate"]:
                self._trigger_alert(
                    "high_error_rate",
                    {
                        "error_rate": error_rate,
                        "threshold": self._alert_thresholds["error_rate"],
                        "window_minutes": 5
                    }
                )

    def _trigger_alert(self, alert_type: str, details: Dict[str, Any]) -> None:
        """Trigger performance alert."""
        now = datetime.now(timezone.utc)
        
        # Prevent alert spam by checking last alert time
        if alert_type in self._last_alert:
            if (now - self._last_alert[alert_type]) < timedelta(minutes=5):
                return

        self._last_alert[alert_type] = now
        
        self.logger.log_event(
            source="performance_monitor",
            event_type=f"alert_{alert_type}",
            payload=details
        ) 