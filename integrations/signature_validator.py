"""
GitHub Webhook Signature Validator.

This module provides HMAC-SHA256 signature verification for GitHub webhooks
as specified in the GitHub Webhooks API documentation.
"""

import hmac
import hashlib
from typing import Optional
import os

from mas_core.utils.logging import MASLogger

class SignatureValidator:
    """Validates GitHub webhook signatures."""

    def __init__(self) -> None:
        """Initialize signature validator."""
        self.logger = MASLogger("signature_validator")
        self.webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if not self.webhook_secret:
            self.logger.log_error(
                error_type="configuration_error",
                message="GITHUB_WEBHOOK_SECRET environment variable not set",
                context={}
            )

    def validate_signature(self, payload: bytes, signature_header: Optional[str]) -> bool:
        """
        Validate the GitHub webhook signature.

        Args:
            payload: Raw request payload
            signature_header: X-Hub-Signature-256 header value

        Returns:
            bool: True if signature is valid
        """
        if not self.webhook_secret:
            self.logger.log_error(
                error_type="validation_error",
                message="Cannot validate signature: webhook secret not configured",
                context={"has_signature": bool(signature_header)}
            )
            return False

        if not signature_header:
            self.logger.log_error(
                error_type="validation_error",
                message="No signature header provided",
                context={}
            )
            return False

        if not signature_header.startswith("sha256="):
            self.logger.log_error(
                error_type="validation_error",
                message="Invalid signature format",
                context={"signature": signature_header}
            )
            return False

        # Extract signature
        signature = signature_header.removeprefix("sha256=")

        # Calculate expected signature
        mac = hmac.new(
            self.webhook_secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()

        # Constant-time comparison
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            self.logger.log_error(
                error_type="validation_error",
                message="Invalid signature",
                context={"signature": signature_header}
            )

        return is_valid 