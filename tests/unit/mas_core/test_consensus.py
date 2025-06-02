"""Unit tests for MAS consensus module."""

import pytest
from datetime import datetime, timezone
from mas_core.consensus import (
    ConsensusManager, ConsensusState, VoteType, ValidationError
)

@pytest.fixture
def consensus_manager():
    """Provide a fresh consensus manager instance."""
    return ConsensusManager(required_votes=2)

@pytest.fixture
def valid_task():
    """Provide a valid task ID."""
    return "task_001"

@pytest.fixture
def valid_agents():
    """Provide a list of valid agent IDs."""
    return ["agent_001", "agent_002", "agent_003"]

def test_start_consensus(consensus_manager, valid_task, valid_agents):
    """Test starting a new consensus round."""
    result = consensus_manager.start_consensus(valid_task, valid_agents)
    assert result is True
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert state["state"] == ConsensusState.IN_PROGRESS.value
    assert state["votes"] == {}
    assert state["total_rounds"] == 1

def test_invalid_task_id(consensus_manager, valid_agents):
    """Test handling of invalid task ID."""
    with pytest.raises(ValidationError):
        consensus_manager.start_consensus("invalid#task", valid_agents)

def test_submit_vote(consensus_manager, valid_task, valid_agents):
    """Test vote submission."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    result = consensus_manager.submit_vote(
        valid_task,
        valid_agents[0],
        VoteType.APPROVE,
        "Looks good"
    )
    assert result is True
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert len(state["votes"]) == 1
    assert state["votes"][valid_agents[0]]["vote"] == VoteType.APPROVE.value
    assert state["votes"][valid_agents[0]]["comment"] == "Looks good"

def test_consensus_resolution_approve(consensus_manager, valid_task, valid_agents):
    """Test consensus resolution with approval."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    # Submit approving votes
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.APPROVE)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.APPROVE)
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert state["state"] == ConsensusState.APPROVED.value
    assert state["resolution"] == "Approved by majority"

def test_consensus_resolution_reject(consensus_manager, valid_task, valid_agents):
    """Test consensus resolution with rejection."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    # Submit rejecting votes
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.REJECT)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.REJECT)
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert state["state"] == ConsensusState.REJECTED.value
    assert state["resolution"] == "Rejected by majority"

def test_consensus_deadlock(consensus_manager, valid_task, valid_agents):
    """Test consensus deadlock handling."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    # Submit split votes
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.APPROVE)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.REJECT)
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert state["state"] == ConsensusState.DEADLOCKED.value
    assert state["resolution"] == "No majority achieved"

def test_ineligible_voter(consensus_manager, valid_task, valid_agents):
    """Test handling of ineligible voter."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    with pytest.raises(ValidationError):
        consensus_manager.submit_vote(
            valid_task,
            "ineligible_agent",
            VoteType.APPROVE
        )

def test_consensus_history(consensus_manager, valid_task, valid_agents):
    """Test consensus history tracking."""
    # First round
    consensus_manager.start_consensus(valid_task, valid_agents)
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.APPROVE)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.REJECT)
    
    # Second round
    consensus_manager.start_consensus(valid_task, valid_agents)
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.APPROVE)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.APPROVE)
    
    history = consensus_manager.get_consensus_history(valid_task)
    assert len(history) == 2
    assert history[0]["state"] == ConsensusState.DEADLOCKED.value
    assert history[1]["state"] == ConsensusState.APPROVED.value

def test_abstain_votes(consensus_manager, valid_task, valid_agents):
    """Test handling of abstain votes."""
    consensus_manager.start_consensus(valid_task, valid_agents)
    
    consensus_manager.submit_vote(valid_task, valid_agents[0], VoteType.ABSTAIN)
    consensus_manager.submit_vote(valid_task, valid_agents[1], VoteType.APPROVE)
    consensus_manager.submit_vote(valid_task, valid_agents[2], VoteType.APPROVE)
    
    state = consensus_manager.get_consensus_state(valid_task)
    assert state["state"] == ConsensusState.APPROVED.value

def test_invalid_consensus_state_query(consensus_manager):
    """Test querying invalid consensus state."""
    with pytest.raises(ValueError):
        consensus_manager.get_consensus_state("nonexistent_task")

def test_invalid_consensus_history_query(consensus_manager):
    """Test querying invalid consensus history."""
    with pytest.raises(ValueError):
        consensus_manager.get_consensus_history("nonexistent_task")

def test_consensus_manager_init():
    """Test ConsensusManager initialization"""
    manager = ConsensusManager()
    assert manager is not None

def test_consensus_manager_basic_flow():
    """Test basic consensus flow"""
    manager = ConsensusManager()
    assert manager.get_status() == "PENDING" 