"""
GitHub Commit Router.

This module processes GitHub webhook payloads and creates corresponding MAS tasks.
It handles both push events and pull request events.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone

from mas_core.utils.logging import MASLogger
from mas_core.task_chain import TaskChainManager, TaskSource, TaskState

class CommitRouter:
    """Routes GitHub events to MAS tasks."""

    def __init__(self) -> None:
        """Initialize commit router."""
        self.logger = MASLogger("commit_router")
        self.task_manager = TaskChainManager()

    def handle_push_event(self, event_data: Dict[str, Any]) -> List[str]:
        """
        Handle GitHub push event.

        Args:
            event_data: Push event payload

        Returns:
            List[str]: Created task IDs
        """
        repository = event_data.get("repository", {})
        ref = event_data.get("ref", "")
        commits = event_data.get("commits", [])

        # Log event processing
        self.logger.log_event(
            source="GitHub",
            event_type="push_processing",
            payload={
                "repository": repository.get("full_name"),
                "ref": ref,
                "commit_count": len(commits)
            }
        )

        task_ids = []
        parent_task_id = None

        # Create main push task if multiple commits
        if len(commits) > 1:
            parent_task_id = self.task_manager.create_task(
                title=f"Process push to {ref}",
                description=f"Process {len(commits)} commits pushed to {ref}",
                source=TaskSource.GITHUB_PUSH,
                metadata={
                    "repository": repository.get("full_name"),
                    "ref": ref,
                    "commit_count": len(commits),
                    "pusher": event_data.get("pusher", {}).get("name")
                }
            )
            task_ids.append(parent_task_id)

        # Process each commit
        for commit in commits:
            task_id = self.task_manager.create_task(
                title=f"Review commit: {commit.get('message', '')[:50]}",
                description=commit.get("message", ""),
                source=TaskSource.GITHUB_PUSH,
                metadata={
                    "repository": repository.get("full_name"),
                    "ref": ref,
                    "commit": commit.get("id"),
                    "author": commit.get("author", {}).get("name"),
                    "url": commit.get("url")
                },
                parent_tasks=[parent_task_id] if parent_task_id else None
            )
            task_ids.append(task_id)

            # Update task state
            self.task_manager.update_task_state(
                task_id,
                TaskState.WEBHOOK_RECEIVED,
                {"event": "push", "commit": commit.get("id")}
            )

        return task_ids

    def handle_pr_event(self, event_data: Dict[str, Any]) -> List[str]:
        """
        Handle GitHub pull request event.

        Args:
            event_data: Pull request event payload

        Returns:
            List[str]: Created task IDs
        """
        action = event_data.get("action")
        pr = event_data.get("pull_request", {})
        repository = event_data.get("repository", {})

        # Log event processing
        self.logger.log_event(
            source="GitHub",
            event_type="pr_processing",
            payload={
                "repository": repository.get("full_name"),
                "pr_number": pr.get("number"),
                "action": action
            }
        )

        # Only process certain PR actions
        if action not in ["opened", "reopened", "synchronize"]:
            return []

        task_id = self.task_manager.create_task(
            title=f"Review PR #{pr.get('number')}: {pr.get('title', '')[:50]}",
            description=pr.get("body", "No description provided"),
            source=TaskSource.GITHUB_PR,
            metadata={
                "repository": repository.get("full_name"),
                "pr_number": pr.get("number"),
                "author": pr.get("user", {}).get("login"),
                "url": pr.get("html_url"),
                "branch": pr.get("head", {}).get("ref"),
                "commits": pr.get("commits"),
                "changed_files": pr.get("changed_files")
            },
            consensus_required=True,
            assignees=self._get_pr_reviewers(pr)
        )

        # Update task state
        self.task_manager.update_task_state(
            task_id,
            TaskState.WEBHOOK_RECEIVED,
            {"event": "pull_request", "action": action}
        )

        return [task_id]

    def _get_pr_reviewers(self, pr: Dict[str, Any]) -> List[str]:
        """
        Get list of PR reviewers.

        Args:
            pr: Pull request data

        Returns:
            List[str]: Reviewer usernames
        """
        reviewers = set()
        
        # Add requested reviewers
        reviewers.update(
            user.get("login")
            for user in pr.get("requested_reviewers", [])
            if user.get("login")
        )

        # Add existing reviewers
        reviewers.update(
            review.get("user", {}).get("login")
            for review in pr.get("reviews", [])
            if review.get("user", {}).get("login")
        )

        return list(reviewers) 