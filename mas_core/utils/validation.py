"""
MAS Validation Utility Module.

This module provides validation functions for MAS Lite Protocol v2.1 data structures,
ensuring compliance with protocol specifications and data integrity.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

# Constants for validation
TASK_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
PRIORITY_LEVELS = {'low', 'medium', 'high'}
CONSENSUS_STATES = {'pending', 'approved', 'rejected'}
AGENT_ROLES = {'generate_draft', 'review_draft', 'validate', 'approve'}

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def validate_task_id(task_id: str) -> bool:
    """
    Validate task ID format.

    Args:
        task_id: Task identifier to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return bool(TASK_ID_PATTERN.match(task_id))

def validate_timestamp(timestamp: str) -> bool:
    """
    Validate ISO format timestamp.

    Args:
        timestamp: ISO format timestamp string

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        datetime.fromisoformat(timestamp)
        return True
    except ValueError:
        return False

def validate_task(task: Dict[str, Any]) -> None:
    """
    Validate task structure according to MAS Lite Protocol v2.1.

    Args:
        task: Task dictionary to validate

    Raises:
        ValidationError: If task is invalid
    """
    required_fields = {
        'task_id': str,
        'timestamp': str,
        'description': str,
        'priority_level': str,
        'consensus': str,
        'agent_assignment': dict
    }

    # Check required fields and types
    for field, field_type in required_fields.items():
        if field not in task:
            raise ValidationError(f"Missing required field: {field}")
        if not isinstance(task[field], field_type):
            raise ValidationError(f"Invalid type for {field}")

    # Validate specific fields
    if not validate_task_id(task['task_id']):
        raise ValidationError("Invalid task_id format")
    
    if not validate_timestamp(task['timestamp']):
        raise ValidationError("Invalid timestamp format")

    if task['priority_level'] not in PRIORITY_LEVELS:
        raise ValidationError(f"Invalid priority_level: {task['priority_level']}")

    if task['consensus'] not in CONSENSUS_STATES:
        raise ValidationError(f"Invalid consensus state: {task['consensus']}")

def validate_agent_assignment(assignment: Dict[str, str]) -> None:
    """
    Validate agent assignment structure.

    Args:
        assignment: Agent assignment dictionary

    Raises:
        ValidationError: If assignment is invalid
    """
    if not assignment:
        raise ValidationError("Empty agent assignment")

    for agent, role in assignment.items():
        if not isinstance(agent, str) or not agent.strip():
            raise ValidationError(f"Invalid agent identifier: {agent}")
        if role not in AGENT_ROLES:
            raise ValidationError(f"Invalid agent role: {role}")

def validate_consensus_vote(vote: Dict[str, Any]) -> None:
    """
    Validate consensus vote structure.

    Args:
        vote: Consensus vote dictionary

    Raises:
        ValidationError: If vote is invalid
    """
    required_fields = {
        'task_id': str,
        'agent_id': str,
        'vote': str,
        'timestamp': str
    }

    for field, field_type in required_fields.items():
        if field not in vote:
            raise ValidationError(f"Missing required field in vote: {field}")
        if not isinstance(vote[field], field_type):
            raise ValidationError(f"Invalid type for vote field: {field}")

    if not validate_task_id(vote['task_id']):
        raise ValidationError("Invalid task_id in vote")

    if not validate_timestamp(vote['timestamp']):
        raise ValidationError("Invalid timestamp in vote")

    if vote['vote'] not in {'approve', 'reject'}:
        raise ValidationError(f"Invalid vote value: {vote['vote']}")

def generate_task_id() -> str:
    """
    Generate a protocol-compliant task ID.

    Returns:
        str: Valid task ID
    """
    return f"task_{uuid.uuid4().hex[:16]}" 