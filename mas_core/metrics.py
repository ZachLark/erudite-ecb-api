"""
MAS Metrics Module.

This module provides performance tracking and system health monitoring for the
MAS Lite Protocol v2.1 implementation, including task metrics, consensus metrics,
and system resource utilization.
"""

import time
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from functools import wraps
import statistics
from .utils.logging import MASLogger

@dataclass
class TaskMetrics:
    """Task-related performance metrics."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_completion_time: float = 0.0
    success_rate: float = 0.0

@dataclass
class ConsensusMetrics:
    """Consensus-related performance metrics."""
    total_rounds: int = 0
    successful_consensus: int = 0
    failed_consensus: int = 0
    avg_rounds_per_task: float = 0.0
    avg_time_per_round: float = 0.0

@dataclass
class SystemMetrics:
    """System resource utilization metrics."""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, float] = None

class MetricsCollector:
    """Collects and manages system-wide metrics."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.logger = MASLogger("metrics")
        self.task_metrics = TaskMetrics()
        self.consensus_metrics = ConsensusMetrics()
        self.system_metrics = SystemMetrics()
        self.task_timings: List[float] = []
        self.consensus_timings: List[float] = []

    def track_task_timing(self, func):
        """
        Decorator to track task execution time.

        Args:
            func: Function to track
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                self.record_task_completion(time.time() - start_time)
                return result
            except Exception as e:
                self.record_task_failure()
                raise e
        return wrapper

    def track_consensus_timing(self, func):
        """
        Decorator to track consensus round timing.

        Args:
            func: Function to track
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                self.record_consensus_round(time.time() - start_time)
                return result
            except Exception as e:
                self.record_consensus_failure()
                raise e
        return wrapper

    def record_task_completion(self, execution_time: float) -> None:
        """
        Record successful task completion.

        Args:
            execution_time: Task execution time in seconds
        """
        self.task_metrics.total_tasks += 1
        self.task_metrics.completed_tasks += 1
        self.task_timings.append(execution_time)
        self.task_metrics.avg_completion_time = statistics.mean(self.task_timings)
        self.task_metrics.success_rate = (
            self.task_metrics.completed_tasks / self.task_metrics.total_tasks
        )

    def record_task_failure(self) -> None:
        """Record task failure."""
        self.task_metrics.total_tasks += 1
        self.task_metrics.failed_tasks += 1
        self.task_metrics.success_rate = (
            self.task_metrics.completed_tasks / self.task_metrics.total_tasks
        )

    def record_consensus_round(self, round_time: float) -> None:
        """
        Record consensus round completion.

        Args:
            round_time: Round completion time in seconds
        """
        self.consensus_metrics.total_rounds += 1
        self.consensus_metrics.successful_consensus += 1
        self.consensus_timings.append(round_time)
        self.consensus_metrics.avg_time_per_round = statistics.mean(self.consensus_timings)
        self.consensus_metrics.avg_rounds_per_task = (
            self.consensus_metrics.total_rounds / self.task_metrics.total_tasks
            if self.task_metrics.total_tasks > 0 else 0.0
        )

    def record_consensus_failure(self) -> None:
        """Record consensus failure."""
        self.consensus_metrics.total_rounds += 1
        self.consensus_metrics.failed_consensus += 1

    def update_system_metrics(self) -> None:
        """Update system resource utilization metrics."""
        self.system_metrics.cpu_usage = psutil.cpu_percent()
        self.system_metrics.memory_usage = psutil.virtual_memory().percent
        self.system_metrics.disk_usage = psutil.disk_usage('/').percent
        net_io = psutil.net_io_counters()
        self.system_metrics.network_io = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv
        }

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.

        Returns:
            Dict containing all metrics
        """
        self.update_system_metrics()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_metrics": {
                "total": self.task_metrics.total_tasks,
                "completed": self.task_metrics.completed_tasks,
                "failed": self.task_metrics.failed_tasks,
                "avg_completion_time": self.task_metrics.avg_completion_time,
                "success_rate": self.task_metrics.success_rate
            },
            "consensus_metrics": {
                "total_rounds": self.consensus_metrics.total_rounds,
                "successful": self.consensus_metrics.successful_consensus,
                "failed": self.consensus_metrics.failed_consensus,
                "avg_rounds_per_task": self.consensus_metrics.avg_rounds_per_task,
                "avg_time_per_round": self.consensus_metrics.avg_time_per_round
            },
            "system_metrics": {
                "cpu_usage": self.system_metrics.cpu_usage,
                "memory_usage": self.system_metrics.memory_usage,
                "disk_usage": self.system_metrics.disk_usage,
                "network_io": self.system_metrics.network_io
            }
        }

    def log_metrics(self) -> None:
        """Log current metrics to the MAS logger."""
        metrics = self.get_metrics_summary()
        self.logger.logger.info(
            "System metrics update",
            extra={"metrics": metrics}
        ) 