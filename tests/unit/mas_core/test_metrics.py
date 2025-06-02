"""Unit tests for MAS metrics module."""

import pytest
import time
from datetime import datetime
from mas_core.metrics import MetricsCollector, TaskMetrics, ConsensusMetrics, SystemMetrics

@pytest.fixture
def metrics_collector():
    """Provide a fresh metrics collector instance."""
    return MetricsCollector()

def test_task_timing_decorator(metrics_collector):
    """Test task timing decorator functionality."""
    @metrics_collector.track_task_timing
    def sample_task():
        time.sleep(0.1)
        return True

    # Execute task
    result = sample_task()
    assert result
    assert metrics_collector.task_metrics.total_tasks == 1
    assert metrics_collector.task_metrics.completed_tasks == 1
    assert metrics_collector.task_metrics.avg_completion_time >= 0.1

def test_consensus_timing_decorator(metrics_collector):
    """Test consensus timing decorator functionality."""
    @metrics_collector.track_consensus_timing
    def sample_consensus():
        time.sleep(0.1)
        return True

    # Execute consensus round
    result = sample_consensus()
    assert result
    assert metrics_collector.consensus_metrics.total_rounds == 1
    assert metrics_collector.consensus_metrics.successful_consensus == 1
    assert metrics_collector.consensus_metrics.avg_time_per_round >= 0.1

def test_task_failure_handling(metrics_collector):
    """Test handling of task failures."""
    @metrics_collector.track_task_timing
    def failing_task():
        raise ValueError("Task failed")

    # Execute failing task
    with pytest.raises(ValueError):
        failing_task()

    assert metrics_collector.task_metrics.total_tasks == 1
    assert metrics_collector.task_metrics.failed_tasks == 1
    assert metrics_collector.task_metrics.completed_tasks == 0
    assert metrics_collector.task_metrics.success_rate == 0.0

def test_consensus_failure_handling(metrics_collector):
    """Test handling of consensus failures."""
    @metrics_collector.track_consensus_timing
    def failing_consensus():
        raise ValueError("Consensus failed")

    # Execute failing consensus
    with pytest.raises(ValueError):
        failing_consensus()

    assert metrics_collector.consensus_metrics.total_rounds == 1
    assert metrics_collector.consensus_metrics.failed_consensus == 1
    assert metrics_collector.consensus_metrics.successful_consensus == 0

def test_system_metrics_update(metrics_collector):
    """Test system metrics collection."""
    metrics_collector.update_system_metrics()
    
    assert 0 <= metrics_collector.system_metrics.cpu_usage <= 100
    assert 0 <= metrics_collector.system_metrics.memory_usage <= 100
    assert 0 <= metrics_collector.system_metrics.disk_usage <= 100
    assert metrics_collector.system_metrics.network_io is not None
    assert 'bytes_sent' in metrics_collector.system_metrics.network_io
    assert 'bytes_recv' in metrics_collector.system_metrics.network_io

def test_metrics_summary(metrics_collector):
    """Test metrics summary generation."""
    # Record some sample metrics
    @metrics_collector.track_task_timing
    def sample_task():
        time.sleep(0.1)
        return True

    @metrics_collector.track_consensus_timing
    def sample_consensus():
        time.sleep(0.1)
        return True

    sample_task()
    sample_consensus()

    summary = metrics_collector.get_metrics_summary()
    
    assert "timestamp" in summary
    assert "task_metrics" in summary
    assert "consensus_metrics" in summary
    assert "system_metrics" in summary
    
    assert summary["task_metrics"]["total"] == 1
    assert summary["task_metrics"]["completed"] == 1
    assert summary["consensus_metrics"]["total_rounds"] == 1
    assert summary["consensus_metrics"]["successful"] == 1

def test_multiple_task_statistics(metrics_collector):
    """Test statistical calculations for multiple tasks."""
    @metrics_collector.track_task_timing
    def sample_task():
        time.sleep(0.1)
        return True

    # Execute multiple tasks
    for _ in range(3):
        sample_task()

    assert metrics_collector.task_metrics.total_tasks == 3
    assert metrics_collector.task_metrics.completed_tasks == 3
    assert metrics_collector.task_metrics.success_rate == 1.0
    assert len(metrics_collector.task_timings) == 3
    assert metrics_collector.task_metrics.avg_completion_time >= 0.1

def test_metrics_logging(metrics_collector):
    """Test metrics logging functionality."""
    # Record some metrics
    metrics_collector.record_task_completion(0.1)
    metrics_collector.record_consensus_round(0.2)
    
    # Test logging
    metrics_collector.log_metrics()
    # Note: We can't easily verify the log output directly,
    # but we can verify the method executes without errors 