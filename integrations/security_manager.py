"""
Security Manager for GitHub Webhooks.

This module provides enhanced security features including IP whitelisting,
payload validation, and audit logging.
"""

import ipaddress
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timezone
from mas_core.utils.logging import MASLogger

class SecurityManager:
    """Security manager for webhook processing."""

    # GitHub webhook IP ranges - should be updated periodically
    GITHUB_IP_RANGES = [
        "192.30.252.0/22",
        "185.199.108.0/22",
        "140.82.112.0/20",
        "143.55.64.0/20"
    ]

    def __init__(self) -> None:
        """Initialize security manager."""
        self.logger = MASLogger("security_manager")
        self._ip_whitelist = [ipaddress.ip_network(cidr) for cidr in self.GITHUB_IP_RANGES]
        self._audit_log = []

    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if IP is in GitHub's webhook range.

        Args:
            ip_address: IP address to check

        Returns:
            bool: True if IP is allowed
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            is_allowed = any(ip in network for network in self._ip_whitelist)
            
            self.log_security_event(
                "ip_check",
                {
                    "ip": ip_address,
                    "allowed": is_allowed
                }
            )
            
            return is_allowed
        except ValueError:
            self.logger.log_error(
                error_type="security_error",
                message="Invalid IP address format",
                context={"ip": ip_address}
            )
            return False

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """
        Validate webhook payload structure and content.

        Args:
            payload: Webhook payload to validate

        Returns:
            bool: True if payload is valid
        """
        required_fields = ["repository", "sender"]
        
        # Check required fields
        if not all(field in payload for field in required_fields):
            self.log_security_event(
                "payload_validation_failed",
                {
                    "reason": "missing_required_fields",
                    "missing_fields": [f for f in required_fields if f not in payload]
                }
            )
            return False

        # Check for suspicious content
        if self._contains_suspicious_content(payload):
            self.log_security_event(
                "payload_validation_failed",
                {
                    "reason": "suspicious_content_detected"
                }
            )
            return False

        return True

    def _contains_suspicious_content(self, payload: Dict[str, Any]) -> bool:
        """
        Check payload for suspicious content.

        Args:
            payload: Webhook payload to check

        Returns:
            bool: True if suspicious content found
        """
        suspicious_patterns = [
            "eval(",
            "exec(",
            "<script",
            "function(",
            "setTimeout",
            "setInterval"
        ]

        payload_str = json.dumps(payload).lower()
        return any(pattern.lower() in payload_str for pattern in suspicious_patterns)

    def log_security_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        severity: str = "info"
    ) -> None:
        """
        Log security event for audit purposes.

        Args:
            event_type: Type of security event
            details: Event details
            severity: Event severity level
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "details": details
        }
        
        self._audit_log.append(event)
        self.logger.log_event(
            source="security_manager",
            event_type=event_type,
            payload=event
        )

    def get_audit_log(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get filtered audit log entries.

        Args:
            start_time: Filter events after this time
            end_time: Filter events before this time
            event_types: Filter by event types

        Returns:
            List of matching audit log entries
        """
        filtered_log = self._audit_log

        if start_time:
            filtered_log = [
                event for event in filtered_log
                if datetime.fromisoformat(event["timestamp"]) >= start_time
            ]

        if end_time:
            filtered_log = [
                event for event in filtered_log
                if datetime.fromisoformat(event["timestamp"]) <= end_time
            ]

        if event_types:
            filtered_log = [
                event for event in filtered_log
                if event["event_type"] in event_types
            ]

        return filtered_log 