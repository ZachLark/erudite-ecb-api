"""
MAS Logging Utility Module.

This module provides centralized logging functionality for the MAS Lite Protocol v2.1
implementation, including structured logging, rotation policies, and audit trails.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger

# Configure default paths
LOG_DIR = Path("logs")
MAS_LOG_FILE = LOG_DIR / "mas.log"
AUDIT_LOG_FILE = LOG_DIR / "audit.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"

class MASLogger:
    """MAS-specific logger with protocol-compliant formatting."""

    def __init__(self, name: str, log_file: Optional[Path] = None) -> None:
        """
        Initialize MAS logger.

        Args:
            name: Logger name
            log_file: Optional custom log file path
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Ensure log directory exists
        LOG_DIR.mkdir(exist_ok=True)

        # Create JSON formatter
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )

        # Add file handler
        file_handler = logging.FileHandler(
            log_file or MAS_LOG_FILE,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def log_task(self, task_id: str, action: str, details: Dict[str, Any]) -> None:
        """
        Log a task-related event.

        Args:
            task_id: Unique task identifier
            action: Action being performed
            details: Additional task details
        """
        self.logger.info(
            "Task event",
            extra={
                "task_id": task_id,
                "action": action,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_consensus(self, task_id: str, status: str, votes: Dict[str, str]) -> None:
        """
        Log a consensus event.

        Args:
            task_id: Task identifier
            status: Consensus status
            votes: Agent votes
        """
        self.logger.info(
            "Consensus event",
            extra={
                "task_id": task_id,
                "status": status,
                "votes": votes,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_error(self, error_type: str, message: str, context: Dict[str, Any]) -> None:
        """
        Log an error event.

        Args:
            error_type: Type of error
            message: Error message
            context: Error context
        """
        self.logger.error(
            message,
            extra={
                "error_type": error_type,
                "context": context,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_audit(self, agent_id: str, action: str, resource: str) -> None:
        """
        Log an audit event.

        Args:
            agent_id: Agent identifier
            action: Action performed
            resource: Resource accessed
        """
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_id": agent_id,
                "action": action,
                "resource": resource
            }, f)
            f.write('\n')

    def log(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log a message.
        
        Args:
            level: Log level
            message: Log message
            extra: Optional extra fields
        """
        self.logger.log(
            getattr(logging, level.upper()),
            message,
            extra=extra or {}
        )
        
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log an info message.
        
        Args:
            message: Log message
            extra: Optional extra fields
        """
        self.log("INFO", message, extra)
        
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning message.
        
        Args:
            message: Log message
            extra: Optional extra fields
        """
        self.log("WARNING", message, extra)
        
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log an error message.
        
        Args:
            message: Log message
            extra: Optional extra fields
        """
        self.log("ERROR", message, extra)
        
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log a critical message.
        
        Args:
            message: Log message
            extra: Optional extra fields
        """
        self.log("CRITICAL", message, extra) 