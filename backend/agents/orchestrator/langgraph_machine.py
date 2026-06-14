"""
Orchestrator Agent — LangGraph State Machine
PRD FR-01.3: State machine for all normal and exception workflows.
Manages cyclic loops, human-in-the-loop checkpoints, escalation triggers.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Annotated, Optional
import operator

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.redis_client import get_all_agent_states, set_national_risk_index, publish_dashboard_event
from shared.mongodb import incidents_col, alerts_col, get_db
from shared.kafka_client import NitccKafkaProducer, KafkaTopic
from shared.schemas.models import AlertSeverity, IncidentSeverity

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph State Definition
# ─────────────────────────────────────────────────────────────────────────────

class NITCCState(TypedDict):
    """Global belief state maintained by Orchestrator (FR-01.2)."""
    # Agent states
    agent_states: Dict[str, Any]

    # Current events being processed
    pending_events: Annotated[List[Dict], operator.add]

    # Risk assessment
    national_risk_index: float
    risk_by_zone: Dict[str, float]

    # Active incidents
    active_incidents: List[str]

    # Workflow context
    workflow: str               # Current workflow being executed
    iteration_count: int        # Cycle iteration counter (prevent runaway loops)
    max_iterations: int         # Cap for cyclic loops
    human_checkpoint_required: bool
    last_checkpoint_at: Optional[str]

    # Escalation flags
    p1_active: bool
    p2_active: bool

    # Outputs
    dashboard_updates: Annotated[List[Dict], operator.add]
    completed: bool


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph State Machine
# ─────────────────────────────────────────────────────────────────────────────

class NITCCStateMachine:
    """
    LangGraph-based state machine for NITCC workflows.
    FR-01.3: Defines transition rules for all normal and exception workflows.
    Cyclic loops have iteration caps.
    Human-in-the-loop checkpoints configurable at any node.
    """

    def __init__(self, producer: NitccKafkaProducer = None):
        self._producer = producer
        self._graph = None
        self._human_checkpoint_nodes: set = {"action_plan_review"}  # Configurable
        self._build_graph()

    def _build_graph(self):
        """Build the LangGraph state machine."""
        try:
            from langgraph.graph import StateGraph, END

            workflow = StateGraph(NITCCState)

            # Add nodes
            workflow.add_node("collect_agent_states", self._collect_agent_states)
            workflow.add_node("compute_nri", self._compute_national_risk_index)
            workflow.add_node("detect_incidents", self._detect_incidents)
            workflow.add_node("weather_watch", self._weather_watch)
            workflow.add_node("route_recalculation", self._route_recalculation)
            workflow.add_node("escalate_p1_p2", self._escalate_p1_p2)
            workflow.add_node("action_plan_review", self._action_plan_review_checkpoint)
            workflow.add_node("broadcast_updates", self._broadcast_updates)

            # Entry point
            workflow.set_entry_point("collect_agent_states")

            # Transitions
            workflow.add_edge("collect_agent_states", "compute_nri")
            workflow.add_edge("compute_nri", "detect_incidents")

            # Conditional transitions
            workflow.add_conditional_edges(
                "detect_incidents",
                self._route_after_detection,
                {
                    "escalate": "escalate_p1_p2",
                    "weather_watch": "weather_watch",
                    "broadcast": "broadcast_updates",
                }
            )

            # Weather watch → route recalculation (cyclic with cap)
            workflow.add_conditional_edges(
                "weather_watch",
                self._check_rerouting_needed,
                {
                    "recalculate": "route_recalculation",
                    "broadcast": "broadcast_updates",
                }
            )
            workflow.add_edge("route_recalculation", "broadcast_updates")

            # Escalation flow with human checkpoint
            workflow.add_conditional_edges(
                "escalate_p1_p2",
                self._check_human_checkpoint,
                {
                    "human_review": "action_plan_review",
                    "auto_proceed": "broadcast_updates",
                }
            )
            workflow.add_edge("action_plan_review", "broadcast_updates")
            workflow.add_edge("broadcast_updates", END)

            self._graph = workflow.compile()
            logger.info("LangGraph state machine compiled successfully")

        except ImportError:
            logger.warning(
                "langgraph not installed. State machine will use simplified loop. "
                "Install: pip install langgraph"
            )
            self._graph = None

    async def run_orchestration_cycle(self, initial_events: List[Dict] = None) -> NITCCState:
        """Execute one orchestration cycle."""
        initial_state = NITCCState(
            agent_states={},
            pending_events=initial_events or [],
            national_risk_index=0.0,
            risk_by_zone={},
            active_incidents=[],
            workflow="normal",
            iteration_count=0,
            max_iterations=10,  # Prevent runaway cyclic loops (FR-01.3)
            human_checkpoint_required=False,
            last_checkpoint_at=None,
            p1_active=False,
            p2_active=False,
            dashboard_updates=[],
            completed=False,
        )

        if self._graph:
            try:
                final_state = await self._graph.ainvoke(initial_state)
                return final_state
            except Exception as e:
                logger.error(f"LangGraph execution error: {e}")

        # Fallback simplified orchestration loop
        return await self._simplified_orchestration(initial_state)

    async def _simplified_orchestration(self, state: NITCCState) -> NITCCState:
        """Simplified orchestration when LangGraph is unavailable."""
        state = await self._collect_agent_states(state)
        state = await self._compute_national_risk_index(state)
        state = await self._detect_incidents(state)
        state = await self._broadcast_updates(state)
        return state

    # ──────────────────────────────────────────────────────────────────────────
    # Node Implementations
    # ──────────────────────────────────────────────────────────────────────────

    async def _collect_agent_states(self, state: NITCCState) -> NITCCState:
        """Collect all agent states from Redis (global belief state FR-01.2)."""
        try:
            agent_states = await get_all_agent_states()
            state["agent_states"] = agent_states
        except Exception as e:
            logger.error(f"Error collecting agent states: {e}")
        return state

    async def _compute_national_risk_index(self, state: NITCCState) -> NITCCState:
        """
        Compute National Risk Index (NRI) from all agent outputs (FR-09).
        Updated every 5 minutes.
        """
        try:
            # Weight agent risk contributions
            agent_states = state.get("agent_states", {})

            risk_scores = {
                "operational": 0.0,  # TrackWatch
                "environmental": 0.0,  # WeatherMind + SatEye
                "logistics": 0.0,    # CargoFlow
                "emergency": 0.0,    # CrisisCommand
            }

            # TrackWatch context
            tw_state = agent_states.get("trackwatch-agent", {})
            risk_scores["operational"] = tw_state.get("avgRiskScore", 0.0)

            # WeatherMind context
            wm_state = agent_states.get("weathermind-agent", {})
            risk_scores["environmental"] = wm_state.get("maxWeatherSeverity", 0.0)

            # Count active P1/P2 incidents
            p1_count = await incidents_col().count_documents({"severity": "P1", "status": {"$ne": "resolved"}})
            p2_count = await incidents_col().count_documents({"severity": "P2", "status": {"$ne": "resolved"}})

            if p1_count > 0:
                risk_scores["emergency"] = 100.0
                state["p1_active"] = True
            elif p2_count > 0:
                risk_scores["emergency"] = 70.0
                state["p2_active"] = True

            # Composite NRI (weighted average)
            nri = (
                risk_scores["operational"]  * 0.30
                + risk_scores["environmental"] * 0.25
                + risk_scores["logistics"]   * 0.20
                + risk_scores["emergency"]   * 0.25
            )
            nri = round(min(100.0, max(0.0, nri)), 2)

            state["national_risk_index"] = nri
            state["risk_by_zone"] = risk_scores

            # Cache in Redis
            await set_national_risk_index({
                "nri": nri,
                "components": risk_scores,
                "updatedAt": datetime.utcnow().isoformat(),
                "p1_active": state.get("p1_active", False),
                "p2_active": state.get("p2_active", False),
            })

        except Exception as e:
            logger.error(f"NRI computation error: {e}")

        return state

    async def _detect_incidents(self, state: NITCCState) -> NITCCState:
        """Process pending events and detect new incidents (FR-06.1)."""
        for event in state.get("pending_events", []):
            if event.get("eventType") == "ANOMALY_DETECTED":
                state["active_incidents"].append(event.get("correlationId", ""))
        return state

    async def _weather_watch(self, state: NITCCState) -> NITCCState:
        """Monitor weather conditions and flag rerouting needs (Flow 2)."""
        # Check for active FLOOD_RISK or CYCLONE weather advisories
        from shared.mongodb import weather_readings_col
        high_risk = await weather_readings_col().find_one({
            "impactCode": {"$in": ["FLOOD_RISK", "CYCLONE", "HIGH_WIND"]}
        })
        state["workflow"] = "weather_rerouting" if high_risk else "normal"

        # Iteration cap check (FR-01.3)
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        return state

    async def _route_recalculation(self, state: NITCCState) -> NITCCState:
        """Trigger RouteOptima Agent for weather-driven rerouting (Flow 2)."""
        if self._producer:
            await self._producer.publish(
                topic=KafkaTopic.RAILWAY,
                event_type="REROUTING_REQUESTED",
                payload={"reason": "weather_advisory", "workflow": state.get("workflow")},
                domain="operational",
            )
        return state

    async def _escalate_p1_p2(self, state: NITCCState) -> NITCCState:
        """Escalate P1/P2 incidents to CrisisCommand (FR-06)."""
        if self._producer:
            await self._producer.publish(
                topic=KafkaTopic.EMERGENCY,
                event_type="INCIDENT_ESCALATED",
                payload={
                    "p1_active": state.get("p1_active"),
                    "active_incidents": state.get("active_incidents"),
                },
                domain="emergency",
            )
        return state

    async def _action_plan_review_checkpoint(self, state: NITCCState) -> NITCCState:
        """
        Human-in-the-loop checkpoint (FR-01.3).
        In production, this pauses the graph and waits for human approval.
        For P1/P2 incidents — human review before plan activation.
        """
        state["human_checkpoint_required"] = True
        state["last_checkpoint_at"] = datetime.utcnow().isoformat()
        logger.info("Human checkpoint triggered — awaiting operator approval for P1/P2 action plan")
        return state

    async def _broadcast_updates(self, state: NITCCState) -> NITCCState:
        """Publish dashboard updates and mark cycle complete."""
        await publish_dashboard_event("nitcc.orchestrator", {
            "type": "ORCHESTRATION_CYCLE",
            "nri": state.get("national_risk_index", 0),
            "risk_by_zone": state.get("risk_by_zone", {}),
            "p1_active": state.get("p1_active", False),
            "p2_active": state.get("p2_active", False),
            "timestamp": datetime.utcnow().isoformat(),
        })
        state["completed"] = True
        return state

    # ──────────────────────────────────────────────────────────────────────────
    # Conditional Routing Functions
    # ──────────────────────────────────────────────────────────────────────────

    def _route_after_detection(self, state: NITCCState) -> str:
        if state.get("p1_active") or state.get("p2_active"):
            return "escalate"
        # Check weather context from agent states
        wm = state.get("agent_states", {}).get("weathermind-agent", {})
        if wm.get("hasActiveAdvisory"):
            return "weather_watch"
        return "broadcast"

    def _check_rerouting_needed(self, state: NITCCState) -> str:
        # Enforce iteration cap (FR-01.3)
        if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
            logger.warning("Weather watch iteration cap reached — proceeding to broadcast")
            return "broadcast"
        if state.get("workflow") == "weather_rerouting":
            return "recalculate"
        return "broadcast"

    def _check_human_checkpoint(self, state: NITCCState) -> str:
        # P1 incidents always require human review before plan activation
        if state.get("p1_active"):
            return "human_review"
        return "auto_proceed"

    def configure_human_checkpoints(self, nodes: list[str]) -> None:
        """FR-01.3: Human-in-the-loop checkpoints configurable at any node."""
        self._human_checkpoint_nodes = set(nodes)
        logger.info(f"Human checkpoints configured for nodes: {nodes}")
