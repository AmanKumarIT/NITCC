"""
CrisisCommand Agent — AI Action Plan Generator
PRD FR-06.2: LLM-generated action plan within 60 seconds of incident declaration.
Configurable LLM: openai | google | anthropic (set in .env)
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import settings
from shared.mongodb import incidents_col

logger = logging.getLogger(__name__)


class ActionPlanGenerator:
    """
    Uses LLM (configurable via .env) to generate structured action plans
    for NITCC incidents within 60 seconds (FR-06.2).
    """

    def __init__(self):
        self._llm_client = None
        self._provider = settings.llm_provider
        self._model = settings.llm_model

    async def initialize(self) -> None:
        """Initialize the LLM client based on configured provider."""
        if not settings.llm_api_key:
            logger.warning("LLM API key not set — using template-based fallback action plans")
            return

        try:
            if self._provider == "openai":
                from openai import AsyncOpenAI
                self._llm_client = AsyncOpenAI(api_key=settings.llm_api_key)
            elif self._provider == "google":
                import google.generativeai as genai
                genai.configure(api_key=settings.llm_api_key)
                self._llm_client = genai.GenerativeModel(self._model)
            elif self._provider == "anthropic":
                from anthropic import AsyncAnthropic
                self._llm_client = AsyncAnthropic(api_key=settings.llm_api_key)
            logger.info(f"LLM client initialized: {self._provider}/{self._model}")
        except ImportError as e:
            logger.warning(f"LLM library not installed ({e}). Using fallback.")

    async def generate_action_plan(
        self, incident: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a structured Action Plan for an incident.
        Must complete within 60 seconds (FR-06.2).
        """
        incident_type = incident.get("type", "Unknown")
        severity = incident.get("severity", "P2")
        location = incident.get("location", {})
        affected_trains = incident.get("affectedTrains", [])
        affected_segments = incident.get("affectedSegments", [])

        # Try LLM generation first, fallback to template
        if self._llm_client:
            try:
                plan = await asyncio.wait_for(
                    self._generate_with_llm(incident),
                    timeout=55.0,  # Leave 5s buffer before 60s deadline
                )
                return plan
            except asyncio.TimeoutError:
                logger.warning("LLM timed out — using template fallback")
            except Exception as e:
                logger.error(f"LLM generation error: {e} — using template fallback")

        # Template-based fallback
        return self._generate_template_plan(incident)

    async def _generate_with_llm(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Generate action plan using configured LLM."""
        prompt = self._build_prompt(incident)

        if self._provider == "openai":
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)

        elif self._provider == "google":
            import google.generativeai as genai
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._llm_client.generate_content(
                    f"{self._system_prompt()}\n\n{prompt}",
                    generation_config=genai.GenerationConfig(
                        temperature=settings.llm_temperature,
                        max_output_tokens=settings.llm_max_tokens,
                    )
                )
            )
            return json.loads(response.text)

        elif self._provider == "anthropic":
            response = await self._llm_client.messages.create(
                model=self._model,
                max_tokens=settings.llm_max_tokens,
                system=self._system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(response.content[0].text)

        raise ValueError(f"Unsupported LLM provider: {self._provider}")

    def _system_prompt(self) -> str:
        return """You are the CrisisCommand AI of India's National Intelligent Transportation Command Center (NITCC).
Your role is to generate structured, actionable emergency response plans for transportation incidents.
Always respond with valid JSON matching exactly the schema provided.
Your plans must be specific, realistic, and actionable for Indian railway operations context.
Never hallucinate agency names or resources. Use standard Indian emergency agencies: NDRF, SDRF, GRP, RPF, NHAI."""

    def _build_prompt(self, incident: Dict[str, Any]) -> str:
        return f"""Generate a comprehensive emergency action plan for this incident:

INCIDENT DETAILS:
- Type: {incident.get('type')}
- Severity: {incident.get('severity')} (P1=Catastrophic, P2=Major, P3=Moderate, P4=Minor)
- Location: {incident.get('location')}
- Affected Trains: {incident.get('affectedTrains', [])}
- Affected Track Segments: {incident.get('affectedSegments', [])}
- Detection Time: {incident.get('createdAt')}

Respond with JSON matching this exact schema:
{{
  "immediate_actions": ["Action 1", "Action 2", ...],
  "agency_contacts": [
    {{"agency": "NDRF", "contact": "011-24363260", "role": "Primary responder"}},
    ...
  ],
  "resource_list": [
    {{"resource": "Medical team", "quantity": 2, "deployment_point": "Nearest station", "eta_minutes": 30}},
    ...
  ],
  "evacuation_routes": ["Route 1 description", ...],
  "communication_template": "NITCC ALERT: [Full communication template text]",
  "priority_actions_0_to_5min": ["Critical immediate steps"],
  "priority_actions_5_to_30min": ["Near-term response steps"],
  "priority_actions_30min_plus": ["Extended response steps"]
}}"""

    def _generate_template_plan(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Template-based action plan when LLM is unavailable.
        FR-06.2: Ensures 60-second SLA is always met.
        """
        severity = incident.get("severity", "P2")
        incident_type = incident.get("type", "Unknown")

        return {
            "immediate_actions": [
                f"Halt all trains within 10 km of incident location",
                f"Contact Zone Railway Control: Emergency line activated",
                "Dispatch nearest Railway Protection Force (RPF) unit",
                "Notify District Emergency Operations Center (DEOC)",
                f"Set corridor to CRITICAL status: affected segments isolated",
            ],
            "agency_contacts": [
                {"agency": "NDRF", "contact": "011-24363260", "role": "Primary disaster response"},
                {"agency": "Zone Railway Control", "contact": "Railway emergency: 139", "role": "Operations coordination"},
                {"agency": "RPF Control Room", "contact": "1800-111-322", "role": "Security and crowd control"},
                {"agency": "Medical Emergency", "contact": "108", "role": "Medical response"},
                {"agency": "SDRF", "contact": "State control room", "role": "State disaster response"},
            ],
            "resource_list": [
                {"resource": "ARV (Accident Relief Van)", "quantity": 1, "deployment_point": "Nearest divisional HQ", "eta_minutes": 45},
                {"resource": "Medical team", "quantity": 2, "deployment_point": "Incident site", "eta_minutes": 30},
                {"resource": "Engineering gang", "quantity": 1, "deployment_point": "Track repair", "eta_minutes": 60},
                {"resource": "Crane/Equipment", "quantity": 1, "deployment_point": "Incident site", "eta_minutes": 90},
            ],
            "evacuation_routes": [
                "Primary: Nearest station platform via track-side path",
                "Secondary: Access road via nearest level crossing",
                "Medical evacuation: Helicopter landing zone at nearest open ground",
            ],
            "communication_template": (
                f"NITCC EMERGENCY ALERT — Severity: {severity}\n"
                f"Incident Type: {incident_type}\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
                "All field units are requested to proceed to incident coordinates immediately.\n"
                "Incident Commander: [Name to be designated]\n"
                "Next update in 15 minutes."
            ),
            "priority_actions_0_to_5min": [
                "Stop all trains in affected corridor",
                "Activate emergency communication protocol",
                "Dispatch RPF/GRP to site",
            ],
            "priority_actions_5_to_30min": [
                "Medical teams en route",
                "Engineering assessment begins",
                "Agency coordination call initiated",
            ],
            "priority_actions_30min_plus": [
                "Full incident command established",
                "Relief operations underway",
                "Regular status updates to NITCC command dashboard",
            ],
            "generatedAt": datetime.utcnow().isoformat(),
            "generatedBy": "template_fallback",
            "versions": [],
        }

    async def update_incident_with_plan(self, incident_id: str, plan: Dict[str, Any]) -> None:
        """Write action plan back to the incident document."""
        await incidents_col().update_one(
            {"incidentId": incident_id},
            {
                "$set": {
                    "actionPlan": plan,
                    "status": "active",
                },
                "$push": {
                    "timeline": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "AI Action Plan generated by CrisisCommand Agent",
                        "actor": "crisiscommand-agent",
                        "metadata": {"generatedBy": plan.get("generatedBy", settings.llm_model)},
                    }
                }
            }
        )
        logger.info(f"Action plan written for incident: {incident_id}")
