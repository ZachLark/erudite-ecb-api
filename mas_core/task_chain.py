"""
Task chain management for GitBridge.

This module provides task chain management functionality for GitBridge's event processing
system, handling task state transitions and consensus requirements.

MAS Lite Protocol v2.1 References:
- Section 3.2: Task Chain Requirements
- Section 3.3: State Transitions
- Section 3.4: Error Handling
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from .consensus import ConsensusManager, ConsensusState
from .metrics import MetricsCollector
from .error_handler import ErrorHandler
from .utils.logging import MASLogger

logger = MASLogger(__name__)
metrics_collector = MetricsCollector()

class TaskState(str, Enum):
    """Task states."""
    Created = "Created"
    Queued = "Queued"
    ConsensusPending = "ConsensusPending"
    Resolved = "Resolved"
    Failed = "Failed"

class TaskError(Exception):
    """Base class for task errors."""
    pass

class TaskNotFoundError(TaskError):
    """Raised when task is not found."""
    pass

class InvalidStateTransitionError(TaskError):
    """Raised when state transition is invalid."""
    pass

class Task(BaseModel):
    """Task model."""
    id: str
    state: TaskState
    payload: Dict[str, Any]
    created_at: str
    updated_at: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TaskChain:
    """Task chain manager."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize task chain.
        
        Args:
            config: Configuration dictionary containing task chain settings
                   Required keys:
                   - task_chain.states: List of valid states
                   - task_chain.max_concurrent: Maximum concurrent tasks
                   - task_chain.consensus_required: Whether consensus is required
        """
        self.states = config["task_chain"]["states"]
        self.max_concurrent = config["task_chain"]["max_concurrent"]
        self.consensus_required = config["task_chain"]["consensus_required"]
        self.tasks: Dict[str, Task] = {}
        self.consensus_manager = ConsensusManager(config)
        self.error_handler = ErrorHandler()
        
    @metrics_collector.track_task_timing
    async def create_task(self, payload: Dict[str, Any]) -> Task:
        """Create a new task.
        
        Args:
            payload: Task payload
            
        Returns:
            Task: Created task
            
        Raises:
            ValueError: If task creation fails
        """
        try:
            task = Task(
                id=str(len(self.tasks) + 1),
                state=TaskState.Created,
                payload=payload,
                created_at="2025-06-02T12:00:00Z",
                updated_at="2025-06-02T12:00:00Z"
            )
            self.tasks[task.id] = task
            return task
            
        except Exception as e:
            logger.error(f"Task creation error: {str(e)}")
            raise ValueError(f"Task creation failed: {str(e)}")
            
    @metrics_collector.track_task_timing
    async def transition_task(self, task_id: str, target_state: TaskState) -> Task:
        """Transition task to target state.
        
        Args:
            task_id: Task identifier
            target_state: Target state
            
        Returns:
            Task: Updated task
            
        Raises:
            TaskNotFoundError: If task not found
            InvalidStateTransitionError: If transition is invalid
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")
            
        task = self.tasks[task_id]
        current_state = task.state
        
        if target_state not in TaskState:
            raise InvalidStateTransitionError(f"Invalid target state: {target_state}")
            
        if self.consensus_required:
            consensus = await self.consensus_manager.get_consensus(task_id, target_state)
            if not consensus:
                raise InvalidStateTransitionError("Consensus not achieved")
                
        task.state = target_state
        task.updated_at = "2025-06-02T12:00:00Z"
        return task
        
    async def get_task(self, task_id: str) -> Task:
        """Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task: Task instance
            
        Raises:
            TaskNotFoundError: If task not found
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return self.tasks[task_id]
        
    async def list_tasks(self, state: Optional[TaskState] = None) -> List[Task]:
        """List tasks, optionally filtered by state.
        
        Args:
            state: Optional state filter
            
        Returns:
            List[Task]: List of tasks
        """
        if state:
            return [t for t in self.tasks.values() if t.state == state]
        return list(self.tasks.values())
        
    async def cleanup(self) -> None:
        """Clean up task chain resources."""
        await self.consensus_manager.cleanup() 