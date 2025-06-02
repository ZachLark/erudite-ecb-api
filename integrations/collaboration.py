"""
Collaboration Features for GitHub Webhooks.

This module provides team notification integration, custom approval workflows,
and automated documentation updates.
"""

from typing import Dict, Any, List, Optional, Union
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from mas_core.utils.logging import MASLogger

class NotificationManager:
    """Manages team notifications across different platforms."""

    def __init__(self) -> None:
        """Initialize notification manager."""
        self.logger = MASLogger("notification_manager")
        self._load_notification_config()

    def _load_notification_config(self) -> None:
        """Load notification configuration from file."""
        config_path = Path("config/notifications.json")
        try:
            with open(config_path) as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "slack": {"enabled": False},
                "teams": {"enabled": False},
                "email": {"enabled": False}
            }
            self.logger.log_error(
                error_type="config_error",
                message="Notification config not found, using defaults",
                context={"config_path": str(config_path)}
            )

    def notify_team(
        self,
        message: str,
        level: str = "info",
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to configured platforms.

        Args:
            message: Notification message
            level: Notification level (info/warning/error)
            channels: Optional specific channels to notify
            metadata: Additional notification metadata

        Returns:
            Dict containing notification results
        """
        results = {}
        
        if self.config["slack"]["enabled"]:
            results["slack"] = self._send_slack_notification(
                message, level, channels, metadata
            )
            
        if self.config["teams"]["enabled"]:
            results["teams"] = self._send_teams_notification(
                message, level, channels, metadata
            )
            
        if self.config["email"]["enabled"]:
            results["email"] = self._send_email_notification(
                message, level, channels, metadata
            )

        self.logger.log_event(
            source="notification_manager",
            event_type="notifications_sent",
            payload={
                "level": level,
                "channels": channels,
                "results": results
            }
        )

        return results

    def _send_slack_notification(
        self,
        message: str,
        level: str,
        channels: Optional[List[str]],
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send Slack notification."""
        if not self.config["slack"].get("webhook_url"):
            return {"error": "Slack webhook URL not configured"}

        color_map = {
            "info": "#36a64f",
            "warning": "#ffd700",
            "error": "#ff0000"
        }

        payload = {
            "attachments": [{
                "color": color_map.get(level, "#000000"),
                "text": message,
                "ts": int(datetime.now(timezone.utc).timestamp()),
                "footer": "GitBridge Notification"
            }]
        }

        if metadata:
            payload["attachments"][0]["fields"] = [
                {"title": k, "value": str(v), "short": True}
                for k, v in metadata.items()
            ]

        try:
            response = requests.post(
                self.config["slack"]["webhook_url"],
                json=payload
            )
            return {
                "status": "sent" if response.ok else "failed",
                "status_code": response.status_code
            }
        except requests.RequestException as e:
            return {"error": str(e)}

    def _send_teams_notification(
        self,
        message: str,
        level: str,
        channels: Optional[List[str]],
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send Microsoft Teams notification."""
        if not self.config["teams"].get("webhook_url"):
            return {"error": "Teams webhook URL not configured"}

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": message[:50],
            "themeColor": {
                "info": "0076D7",
                "warning": "FFC107",
                "error": "DC3545"
            }.get(level, "000000"),
            "sections": [{
                "activityTitle": "GitBridge Notification",
                "activitySubtitle": f"Level: {level}",
                "text": message
            }]
        }

        if metadata:
            payload["sections"][0]["facts"] = [
                {"name": k, "value": str(v)}
                for k, v in metadata.items()
            ]

        try:
            response = requests.post(
                self.config["teams"]["webhook_url"],
                json=payload
            )
            return {
                "status": "sent" if response.ok else "failed",
                "status_code": response.status_code
            }
        except requests.RequestException as e:
            return {"error": str(e)}

    def _send_email_notification(
        self,
        message: str,
        level: str,
        channels: Optional[List[str]],
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send email notification."""
        if not self.config["email"].get("smtp_config"):
            return {"error": "Email SMTP not configured"}

        # Email sending logic would be implemented here
        return {"status": "not_implemented"}

class ApprovalWorkflow:
    """Manages custom approval workflows."""

    def __init__(self) -> None:
        """Initialize approval workflow manager."""
        self.logger = MASLogger("approval_workflow")
        self.notification_manager = NotificationManager()

    def create_approval_request(
        self,
        title: str,
        description: str,
        approvers: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create new approval request.

        Args:
            title: Request title
            description: Request description
            approvers: List of required approvers
            metadata: Additional request metadata

        Returns:
            str: Approval request ID
        """
        request_id = f"apr_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Store approval request (would be expanded to use proper storage)
        self._store_approval_request({
            "id": request_id,
            "title": title,
            "description": description,
            "approvers": approvers,
            "status": "pending",
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approvals": {},
            "comments": []
        })

        # Notify approvers
        self.notification_manager.notify_team(
            f"New approval request: {title}",
            level="info",
            channels=approvers,
            metadata={
                "request_id": request_id,
                "approvers": ", ".join(approvers)
            }
        )

        return request_id

    def approve_request(
        self,
        request_id: str,
        approver: str,
        comment: Optional[str] = None
    ) -> bool:
        """
        Approve a request.

        Args:
            request_id: Approval request ID
            approver: Approver username
            comment: Optional approval comment

        Returns:
            bool: True if approval recorded successfully
        """
        request = self._get_approval_request(request_id)
        if not request:
            return False

        if approver not in request["approvers"]:
            self.logger.log_error(
                error_type="invalid_approver",
                message=f"User {approver} not in approvers list",
                context={"request_id": request_id}
            )
            return False

        request["approvals"][approver] = {
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "comment": comment
        }

        if comment:
            request["comments"].append({
                "user": approver,
                "comment": comment,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        # Check if all approvals received
        if len(request["approvals"]) == len(request["approvers"]):
            request["status"] = "approved"
            self.notification_manager.notify_team(
                f"Request {request['title']} fully approved",
                level="info",
                metadata={"request_id": request_id}
            )

        self._store_approval_request(request)
        return True

    def _store_approval_request(self, request: Dict[str, Any]) -> None:
        """Store approval request data."""
        # This would be expanded to use proper storage
        storage_dir = Path("data/approvals")
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        with open(storage_dir / f"{request['id']}.json", "w") as f:
            json.dump(request, f, indent=2)

    def _get_approval_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve approval request data."""
        try:
            with open(f"data/approvals/{request_id}.json") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

class DocumentationManager:
    """Manages automated documentation updates."""

    def __init__(self) -> None:
        """Initialize documentation manager."""
        self.logger = MASLogger("documentation_manager")

    def update_documentation(
        self,
        doc_type: str,
        content: Union[str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update documentation files.

        Args:
            doc_type: Type of documentation to update
            content: New documentation content
            metadata: Additional update metadata

        Returns:
            bool: True if update successful
        """
        try:
            if doc_type == "api":
                return self._update_api_docs(content, metadata)
            elif doc_type == "workflow":
                return self._update_workflow_docs(content, metadata)
            elif doc_type == "release":
                return self._update_release_docs(content, metadata)
            else:
                raise ValueError(f"Unsupported documentation type: {doc_type}")
        except Exception as e:
            self.logger.log_error(
                error_type="documentation_error",
                message=str(e),
                context={
                    "doc_type": doc_type,
                    "metadata": metadata
                }
            )
            return False

    def _update_api_docs(
        self,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Update API documentation."""
        docs_dir = Path("docs/api")
        docs_dir.mkdir(parents=True, exist_ok=True)

        version = metadata.get("version", "latest")
        doc_file = docs_dir / f"api_v{version}.md"

        try:
            # Convert API spec to markdown
            markdown_content = self._convert_api_spec_to_markdown(content)
            
            with open(doc_file, "w") as f:
                f.write(markdown_content)

            self.logger.log_event(
                source="documentation_manager",
                event_type="api_docs_updated",
                payload={"version": version}
            )

            return True
        except Exception as e:
            self.logger.log_error(
                error_type="api_doc_error",
                message=str(e),
                context={"version": version}
            )
            return False

    def _update_workflow_docs(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Update workflow documentation."""
        docs_dir = Path("docs/workflows")
        docs_dir.mkdir(parents=True, exist_ok=True)

        workflow_name = metadata.get("workflow_name", "unnamed")
        doc_file = docs_dir / f"{workflow_name}.md"

        try:
            with open(doc_file, "w") as f:
                f.write(content)

            self.logger.log_event(
                source="documentation_manager",
                event_type="workflow_docs_updated",
                payload={"workflow": workflow_name}
            )

            return True
        except Exception as e:
            self.logger.log_error(
                error_type="workflow_doc_error",
                message=str(e),
                context={"workflow": workflow_name}
            )
            return False

    def _update_release_docs(
        self,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Update release documentation."""
        docs_dir = Path("docs/releases")
        docs_dir.mkdir(parents=True, exist_ok=True)

        version = content.get("version", "unknown")
        doc_file = docs_dir / f"release_{version}.md"

        try:
            markdown_content = self._generate_release_notes(content)
            
            with open(doc_file, "w") as f:
                f.write(markdown_content)

            # Update changelog
            self._update_changelog(version, content)

            self.logger.log_event(
                source="documentation_manager",
                event_type="release_docs_updated",
                payload={"version": version}
            )

            return True
        except Exception as e:
            self.logger.log_error(
                error_type="release_doc_error",
                message=str(e),
                context={"version": version}
            )
            return False

    def _convert_api_spec_to_markdown(self, spec: Dict[str, Any]) -> str:
        """Convert API specification to markdown format."""
        # This would be expanded with full OpenAPI to Markdown conversion
        return "# API Documentation\n\nTo be implemented"

    def _generate_release_notes(self, release_data: Dict[str, Any]) -> str:
        """Generate formatted release notes."""
        template = f"""# Release {release_data.get('version')}

## Release Date
{release_data.get('date', 'TBD')}

## Changes
{self._format_changes(release_data.get('changes', []))}

## Breaking Changes
{self._format_changes(release_data.get('breaking_changes', []))}

## Bug Fixes
{self._format_changes(release_data.get('bug_fixes', []))}
"""
        return template

    def _format_changes(self, changes: List[str]) -> str:
        """Format change list as markdown."""
        if not changes:
            return "None"
        return "\n".join(f"- {change}" for change in changes)

    def _update_changelog(self, version: str, content: Dict[str, Any]) -> None:
        """Update main changelog file."""
        changelog_file = Path("CHANGELOG.md")
        
        if not changelog_file.exists():
            changelog_content = "# Changelog\n\n"
        else:
            with open(changelog_file) as f:
                changelog_content = f.read()

        entry = f"""## [{version}] - {content.get('date', 'TBD')}
{self._format_changes(content.get('changes', []))}\n\n"""

        # Insert after first heading
        parts = changelog_content.split("\n", 1)
        changelog_content = f"{parts[0]}\n\n{entry}{parts[1] if len(parts) > 1 else ''}"

        with open(changelog_file, "w") as f:
            f.write(changelog_content) 