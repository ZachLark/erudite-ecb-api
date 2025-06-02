"""Unit tests for GitHub webhook signature validator."""

import pytest
import os
import hmac
import hashlib
from unittest.mock import patch
from integrations.signature_validator import SignatureValidator

@pytest.fixture
def webhook_secret():
    """Provide a test webhook secret."""
    return "test_secret_key"

@pytest.fixture
def validator(webhook_secret):
    """Provide a configured signature validator."""
    with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": webhook_secret}):
        return SignatureValidator()

@pytest.fixture
def sample_payload():
    """Provide sample webhook payload."""
    return b'{"action": "test"}'

def test_validator_initialization_with_secret(webhook_secret):
    """Test validator initialization with secret."""
    with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": webhook_secret}):
        validator = SignatureValidator()
        assert validator.webhook_secret == webhook_secret

def test_validator_initialization_without_secret():
    """Test validator initialization without secret."""
    with patch.dict(os.environ, {}, clear=True):
        validator = SignatureValidator()
        assert validator.webhook_secret is None

def test_valid_signature(validator, sample_payload, webhook_secret):
    """Test validation of correct signature."""
    # Calculate valid signature
    mac = hmac.new(
        webhook_secret.encode(),
        msg=sample_payload,
        digestmod=hashlib.sha256
    )
    signature = f"sha256={mac.hexdigest()}"
    
    assert validator.validate_signature(sample_payload, signature) is True

def test_invalid_signature(validator, sample_payload):
    """Test validation of incorrect signature."""
    invalid_signature = "sha256=invalid_signature"
    assert validator.validate_signature(sample_payload, invalid_signature) is False

def test_missing_signature(validator, sample_payload):
    """Test validation with missing signature."""
    assert validator.validate_signature(sample_payload, None) is False

def test_invalid_signature_format(validator, sample_payload):
    """Test validation with incorrectly formatted signature."""
    invalid_format = "invalid_format=1234"
    assert validator.validate_signature(sample_payload, invalid_format) is False

def test_missing_webhook_secret(sample_payload, webhook_secret):
    """Test validation when webhook secret is not configured."""
    with patch.dict(os.environ, {}, clear=True):
        validator = SignatureValidator()
        signature = f"sha256={webhook_secret}"
        assert validator.validate_signature(sample_payload, signature) is False

def test_empty_payload(validator):
    """Test validation with empty payload."""
    mac = hmac.new(
        validator.webhook_secret.encode(),
        msg=b"",
        digestmod=hashlib.sha256
    )
    signature = f"sha256={mac.hexdigest()}"
    
    assert validator.validate_signature(b"", signature) is True

def test_tampered_payload(validator, sample_payload, webhook_secret):
    """Test validation with tampered payload."""
    # Calculate signature for original payload
    mac = hmac.new(
        webhook_secret.encode(),
        msg=sample_payload,
        digestmod=hashlib.sha256
    )
    signature = f"sha256={mac.hexdigest()}"
    
    # Try to validate with modified payload
    tampered_payload = b'{"action": "tampered"}'
    assert validator.validate_signature(tampered_payload, signature) is False 