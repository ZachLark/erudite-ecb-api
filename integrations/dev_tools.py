"""
Developer Tools for GitHub Webhooks.

This module provides development utilities including webhook replay,
mock events, and configuration validation.
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
from mas_core.utils.logging import MASLogger

class WebhookTester:
    """Development tools for webhook testing."""

    def __init__(self, storage_dir: str = "tests/fixtures/webhooks") -> None:
        """
        Initialize webhook tester.

        Args:
            storage_dir: Directory for storing webhook fixtures
        """
        self.logger = MASLogger("webhook_tester")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def record_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> str:
        """
        Record webhook for later replay.

        Args:
            event_type: GitHub event type
            payload: Webhook payload
            headers: Request headers

        Returns:
            str: Recorded webhook ID
        """
        webhook_id = hashlib.sha256(
            f"{event_type}:{json.dumps(payload)}".encode()
        ).hexdigest()[:12]

        record = {
            "id": webhook_id,
            "event_type": event_type,
            "payload": payload,
            "headers": headers,
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }

        file_path = self.storage_dir / f"{webhook_id}.json"
        with open(file_path, "w") as f:
            json.dump(record, f, indent=2)

        self.logger.log_event(
            source="webhook_tester",
            event_type="webhook_recorded",
            payload={"webhook_id": webhook_id}
        )

        return webhook_id

    def replay_webhook(
        self,
        webhook_id: str,
        target_url: str,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Replay recorded webhook.

        Args:
            webhook_id: ID of recorded webhook
            target_url: URL to send webhook to
            secret: Optional webhook secret for signing

        Returns:
            Dict containing replay results
        """
        import requests

        file_path = self.storage_dir / f"{webhook_id}.json"
        if not file_path.exists():
            raise ValueError(f"No recorded webhook found with ID {webhook_id}")

        with open(file_path) as f:
            record = json.load(f)

        headers = record["headers"].copy()
        
        # Update signature if secret provided
        if secret:
            payload_bytes = json.dumps(record["payload"]).encode()
            signature = hmac.new(
                secret.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-Hub-Signature-256"] = f"sha256={signature}"

        try:
            response = requests.post(
                target_url,
                json=record["payload"],
                headers=headers
            )

            result = {
                "webhook_id": webhook_id,
                "status_code": response.status_code,
                "response": response.text,
                "replayed_at": datetime.now(timezone.utc).isoformat()
            }

            self.logger.log_event(
                source="webhook_tester",
                event_type="webhook_replayed",
                payload=result
            )

            return result

        except requests.RequestException as e:
            error = {
                "webhook_id": webhook_id,
                "error": str(e),
                "replayed_at": datetime.now(timezone.utc).isoformat()
            }

            self.logger.log_error(
                error_type="replay_error",
                message=str(e),
                context={"webhook_id": webhook_id}
            )

            return error

    def list_recorded_webhooks(
        self,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List recorded webhooks.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of recorded webhook metadata
        """
        webhooks = []
        
        for file_path in self.storage_dir.glob("*.json"):
            with open(file_path) as f:
                record = json.load(f)
                
            if event_type and record["event_type"] != event_type:
                continue
                
            webhooks.append({
                "id": record["id"],
                "event_type": record["event_type"],
                "recorded_at": record["recorded_at"]
            })
            
        return sorted(webhooks, key=lambda w: w["recorded_at"], reverse=True)

    def generate_mock_event(
        self,
        event_type: str,
        template_id: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate mock webhook event.

        Args:
            event_type: Type of event to generate
            template_id: Optional template to base event on
            custom_data: Custom data to include in event

        Returns:
            Dict containing mock event data
        """
        templates_dir = Path(__file__).parent / "templates"
        template_file = templates_dir / f"{event_type}.json"

        if template_id:
            template_file = templates_dir / f"{event_type}_{template_id}.json"

        if not template_file.exists():
            raise ValueError(f"No template found for event type {event_type}")

        with open(template_file) as f:
            template = json.load(f)

        if custom_data:
            template.update(custom_data)

        # Add required fields
        template.update({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sender": {
                "login": "mock-user",
                "id": 12345
            }
        })

        return template

class ConfigValidator:
    """Webhook configuration validator."""

    def __init__(self) -> None:
        """Initialize config validator."""
        self.logger = MASLogger("config_validator")

    def validate_webhook_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate webhook configuration.

        Args:
            config: Webhook configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        required_fields = ["url", "secret", "events"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate URL
        if "url" in config:
            if not config["url"].startswith(("http://", "https://")):
                errors.append("URL must start with http:// or https://")

        # Validate events
        if "events" in config:
            if not isinstance(config["events"], list):
                errors.append("Events must be a list")
            elif not config["events"]:
                errors.append("At least one event must be specified")
            else:
                valid_events = [
                    "push",
                    "pull_request",
                    "issues",
                    "issue_comment",
                    "discussion",
                    "discussion_comment",
                    "workflow_run"
                ]
                for event in config["events"]:
                    if event not in valid_events:
                        errors.append(f"Invalid event type: {event}")

        # Validate content type
        if "content_type" in config:
            if config["content_type"] not in ["json", "form"]:
                errors.append("Content type must be 'json' or 'form'")

        # Log validation result
        if errors:
            self.logger.log_error(
                error_type="config_validation_error",
                message="Configuration validation failed",
                context={"errors": errors}
            )
        else:
            self.logger.log_event(
                source="config_validator",
                event_type="config_validated",
                payload={"status": "valid"}
            )

        return errors

    def generate_config_template(self, event_types: List[str]) -> Dict[str, Any]:
        """
        Generate webhook configuration template.

        Args:
            event_types: List of event types to include

        Returns:
            Dict containing configuration template
        """
        return {
            "url": "https://example.com/webhook",
            "secret": "YOUR_WEBHOOK_SECRET",
            "content_type": "json",
            "events": event_types,
            "active": True,
            "insecure_ssl": "0",
            "retry_policy": {
                "max_attempts": 3,
                "retry_interval": 60
            }
        } 