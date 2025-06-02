"""
GitHub Webhook Listener.

This module handles incoming GitHub webhook events, validates signatures,
and routes events to appropriate handlers.
"""

from typing import Dict, Any, Optional
import json
from flask import Flask, request, Response
from datetime import datetime, timezone

from mas_core.utils.logging import MASLogger
from .signature_validator import SignatureValidator
from .commit_router import CommitRouter

app = Flask(__name__)
logger = MASLogger("webhook_listener")
signature_validator = SignatureValidator()
commit_router = CommitRouter()

@app.route("/webhook", methods=["POST"])
def receive_webhook() -> Response:
    """
    Handle incoming GitHub webhook.

    Returns:
        Flask Response
    """
    # Get headers
    event_type = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256")

    # Get raw payload
    payload = request.get_data()

    # Validate signature
    if not signature_validator.validate_signature(payload, signature):
        logger.log_error(
            error_type="webhook_error",
            message="Invalid webhook signature",
            context={"event_type": event_type}
        )
        return Response(
            json.dumps({"error": "Invalid signature"}),
            status=401,
            mimetype="application/json"
        )

    # Parse payload
    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        logger.log_error(
            error_type="webhook_error",
            message="Invalid JSON payload",
            context={"event_type": event_type}
        )
        return Response(
            json.dumps({"error": "Invalid JSON"}),
            status=400,
            mimetype="application/json"
        )

    # Log event
    logger.log_event(
        source="GitHub",
        event_type=event_type,
        payload=event_data
    )

    # Route event
    try:
        if event_type == "push":
            task_ids = commit_router.handle_push_event(event_data)
            return Response(
                json.dumps({"status": "success", "task_ids": task_ids}),
                status=200,
                mimetype="application/json"
            )
        elif event_type == "pull_request":
            task_ids = commit_router.handle_pr_event(event_data)
            return Response(
                json.dumps({"status": "success", "task_ids": task_ids}),
                status=200,
                mimetype="application/json"
            )
        else:
            # Log unsupported event type
            logger.log_event(
                source="GitHub",
                event_type="unsupported",
                payload={"original_type": event_type}
            )
            return Response(
                json.dumps({"status": "ignored", "reason": "Unsupported event type"}),
                status=202,
                mimetype="application/json"
            )
    except Exception as e:
        logger.log_error(
            error_type="webhook_error",
            message=str(e),
            context={
                "event_type": event_type,
                "error": str(e)
            }
        )
        return Response(
            json.dumps({"error": "Internal error processing webhook"}),
            status=500,
            mimetype="application/json"
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001) 