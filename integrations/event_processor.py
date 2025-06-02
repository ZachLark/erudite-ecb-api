"""
Advanced Event Processor for GitHub Webhooks.

This module handles various GitHub events including Actions, Issues,
Discussions, and Release events with advanced processing capabilities.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from mas_core.utils.logging import MASLogger
from mas_core.task_chain import TaskChainManager, TaskSource, TaskState

class EventProcessor:
    """Advanced event processor for GitHub events."""

    def __init__(self) -> None:
        """Initialize event processor."""
        self.logger = MASLogger("event_processor")
        self.task_manager = TaskChainManager()

    def process_workflow_event(self, payload: Dict[str, Any]) -> str:
        """
        Process GitHub Actions workflow events.

        Args:
            payload: Workflow event payload

        Returns:
            str: Created task ID
        """
        workflow = payload.get("workflow", {})
        run = payload.get("workflow_run", {})

        task_id = self.task_manager.create_task(
            title=f"Monitor workflow: {workflow.get('name')}",
            description=f"Workflow run #{run.get('run_number')} - {run.get('status')}",
            source=TaskSource.GITHUB_WORKFLOW,
            metadata={
                "workflow_id": workflow.get("id"),
                "run_id": run.get("id"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "repository": payload.get("repository", {}).get("full_name")
            }
        )

        self.logger.log_event(
            source="event_processor",
            event_type="workflow_processed",
            payload={"task_id": task_id, "workflow_id": workflow.get("id")}
        )

        return task_id

    def process_issue_event(self, payload: Dict[str, Any]) -> str:
        """
        Process GitHub issue events.

        Args:
            payload: Issue event payload

        Returns:
            str: Created task ID
        """
        issue = payload.get("issue", {})
        action = payload.get("action")

        # Auto-label based on content
        labels = self._generate_issue_labels(issue.get("title", ""), issue.get("body", ""))

        task_id = self.task_manager.create_task(
            title=f"Handle issue #{issue.get('number')}: {issue.get('title')}",
            description=issue.get("body", "No description provided"),
            source=TaskSource.GITHUB_ISSUE,
            metadata={
                "issue_number": issue.get("number"),
                "action": action,
                "labels": labels,
                "repository": payload.get("repository", {}).get("full_name")
            }
        )

        # Auto-assign based on content and labels
        assignees = self._get_suggested_assignees(issue, labels)
        if assignees:
            self.task_manager.update_task_state(
                task_id,
                TaskState.ASSIGNED,
                {"assignees": assignees}
            )

        return task_id

    def process_discussion_event(self, payload: Dict[str, Any]) -> str:
        """
        Process GitHub discussion events.

        Args:
            payload: Discussion event payload

        Returns:
            str: Created task ID
        """
        discussion = payload.get("discussion", {})
        
        task_id = self.task_manager.create_task(
            title=f"Review discussion: {discussion.get('title')}",
            description=discussion.get("body", "No content provided"),
            source=TaskSource.GITHUB_DISCUSSION,
            metadata={
                "discussion_id": discussion.get("id"),
                "category": discussion.get("category", {}).get("name"),
                "repository": payload.get("repository", {}).get("full_name")
            }
        )

        # Auto-categorize and route based on content
        category_updates = self._analyze_discussion_category(discussion)
        if category_updates:
            self.task_manager.update_task_state(
                task_id,
                TaskState.CATEGORIZED,
                {"category_updates": category_updates}
            )

        return task_id

    def process_release_event(self, payload: Dict[str, Any]) -> str:
        """
        Process GitHub release events.

        Args:
            payload: Release event payload

        Returns:
            str: Created task ID
        """
        release = payload.get("release", {})
        
        task_id = self.task_manager.create_task(
            title=f"Process release: {release.get('tag_name')}",
            description=release.get("body", "No release notes provided"),
            source=TaskSource.GITHUB_RELEASE,
            metadata={
                "release_id": release.get("id"),
                "tag": release.get("tag_name"),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "repository": payload.get("repository", {}).get("full_name")
            }
        )

        # Generate release documentation
        if not release.get("draft"):
            self._generate_release_docs(release, task_id)

        return task_id

    def _generate_issue_labels(self, title: str, body: str) -> List[str]:
        """Generate labels based on issue content."""
        labels = []
        
        # Priority labels
        if any(word in title.lower() for word in ["urgent", "critical", "emergency"]):
            labels.append("priority:high")
        
        # Type labels
        if "bug" in title.lower() or "error" in body.lower():
            labels.append("type:bug")
        elif "feature" in title.lower() or "enhancement" in body.lower():
            labels.append("type:feature")
        elif "doc" in title.lower() or "documentation" in body.lower():
            labels.append("type:documentation")

        return labels

    def _get_suggested_assignees(
        self,
        issue: Dict[str, Any],
        labels: List[str]
    ) -> List[str]:
        """Suggest assignees based on issue content and labels."""
        assignees = []
        
        # Add based on mention
        mentions = re.findall(r"@(\w+)", issue.get("body", ""))
        assignees.extend(mentions)

        # Add based on labels (would be expanded based on team structure)
        if "type:bug" in labels:
            assignees.append("debug-team")
        elif "type:documentation" in labels:
            assignees.append("docs-team")

        return list(set(assignees))

    def _analyze_discussion_category(
        self,
        discussion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze and suggest discussion category updates."""
        title = discussion.get("title", "").lower()
        body = discussion.get("body", "").lower()
        current_category = discussion.get("category", {}).get("name")

        updates = {}
        
        # Simple category detection
        if any(word in title + body for word in ["help", "question", "how"]):
            updates["suggested_category"] = "Q&A"
        elif any(word in title + body for word in ["idea", "proposal", "suggest"]):
            updates["suggested_category"] = "Ideas"
        elif any(word in title + body for word in ["announce", "release"]):
            updates["suggested_category"] = "Announcements"

        if updates.get("suggested_category") != current_category:
            updates["reason"] = "Content analysis suggests different category"
            
        return updates

    def _generate_release_docs(self, release: Dict[str, Any], task_id: str) -> None:
        """Generate release documentation."""
        # This would be expanded to generate actual documentation
        self.task_manager.update_task_state(
            task_id,
            TaskState.DOCUMENTATION_PENDING,
            {
                "version": release.get("tag_name"),
                "type": "release_notes",
                "status": "pending"
            }
        ) 