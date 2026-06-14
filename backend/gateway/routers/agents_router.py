"""
Agents Router — Admin only
GET /agents/status
"""
from fastapi import APIRouter, Depends
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.redis_client import get_all_agent_states
from shared.mongodb import agent_state_col
from shared.auth import require_admin, CurrentUser
from shared.schemas.models import APIResponse

router = APIRouter()

@router.get("/status", summary="Health and state of all AI agents (Admin only)")
async def agents_status(user: CurrentUser = Depends(require_admin)):
    """
    Returns live state of all 7 NITCC agents from MongoDB + Redis.
    FR-01.1: Each agent exposes /health; orchestrator aggregates here.
    """
    cursor = agent_state_col().find({}, {"_id": 0}).sort("agentName", 1)
    agents = await cursor.to_list(length=20)
    redis_states = await get_all_agent_states()
    
    # Merge Redis real-time state
    for agent in agents:
        agent_id = agent.get("agentId")
        if agent_id in redis_states:
            agent["liveContext"] = redis_states[agent_id]
    
    return APIResponse(data=agents)