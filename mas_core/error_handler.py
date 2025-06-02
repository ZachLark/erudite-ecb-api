"""
Error handling for GitBridge.

This module provides error handling functionality for GitBridge's event processing
system, handling task errors, consensus errors, and queue errors.

MAS Lite Protocol v2.1 References:
- Section 6.2: Error Handling Requirements
- Section 6.3: Error Recovery
- Section 6.4: Error Reporting
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from .utils.logging import MASLogger

logger = MASLogger(__name__)

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(str, Enum):
    """Error categories."""
    TASK = "task"
    CONSENSUS = "consensus"
    QUEUE = "queue"
    SYSTEM = "system"

class ErrorHandler:
    """Error handler for GitBridge."""
    
    def __init__(self):
        """Initialize error handler."""
        self.errors: Dict[str, Dict[str, Any]] = {}
        self.logger = MASLogger("error_handler")
        
    def handle_error(
        self,
        error_id: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle an error.
        
        Args:
            error_id: Error identifier
            category: Error category
            severity: Error severity
            message: Error message
            details: Optional error details
        """
        error = {
            "category": category,
            "severity": severity,
            "message": message,
            "details": details or {},
            "timestamp": "2025-06-02T12:00:00Z"
        }
        
        self.errors[error_id] = error
        
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"{category} error: {message}", extra=details)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(f"{category} error: {message}", extra=details)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(f"{category} warning: {message}", extra=details)
        else:
            self.logger.info(f"{category} info: {message}", extra=details)
            
    def get_error(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get error by ID.
        
        Args:
            error_id: Error identifier
            
        Returns:
            Optional[Dict[str, Any]]: Error details if found
        """
        return self.errors.get(error_id)
        
    def clear_error(self, error_id: str) -> None:
        """Clear error by ID.
        
        Args:
            error_id: Error identifier
        """
        if error_id in self.errors:
            del self.errors[error_id]
            
    def get_errors_by_category(self, category: ErrorCategory) -> Dict[str, Dict[str, Any]]:
        """Get errors by category.
        
        Args:
            category: Error category
            
        Returns:
            Dict[str, Dict[str, Any]]: Errors in the category
        """
        return {
            error_id: error
            for error_id, error in self.errors.items()
            if error["category"] == category
        }
        
    def get_errors_by_severity(self, severity: ErrorSeverity) -> Dict[str, Dict[str, Any]]:
        """Get errors by severity.
        
        Args:
            severity: Error severity
            
        Returns:
            Dict[str, Dict[str, Any]]: Errors with the severity
        """
        return {
            error_id: error
            for error_id, error in self.errors.items()
            if error["severity"] == severity
        }
        
    def clear_all_errors(self) -> None:
        """Clear all errors."""
        self.errors.clear() 