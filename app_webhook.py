"""
GitBridge Webhook Server.

This is the main entry point for the GitHub webhook server.
It initializes the Flask application and starts the server.
"""

import os
from integrations.webhook_listener import app
from mas_core.utils.logging import MASLogger

logger = MASLogger("webhook_server")

if __name__ == "__main__":
    # Check for webhook secret
    if not os.environ.get("GITHUB_WEBHOOK_SECRET"):
        logger.log_error(
            error_type="configuration_error",
            message="GITHUB_WEBHOOK_SECRET environment variable must be set",
            context={}
        )
        exit(1)

    # Start server
    logger.log_event(
        source="system",
        event_type="server_start",
        payload={"port": 5001}
    )
    app.run(host="0.0.0.0", port=5001) 