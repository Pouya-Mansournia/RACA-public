"""LLM-backed ReasoningBackend. Faithful port of `agent_core.llm_agent.LLMAgent`
under RACA's `ReasoningBackend`/`RobotObservation`/`CognitiveAction` naming.

The LLM only ever proposes a structured, validated `CognitiveAction` - it
never touches motion control directly. Every response goes through:

    LLMClient.complete() -> JSON parse -> schema check -> safety check
                                                                |
                                                    reject -> retry -> fallback

"Safety" concretely means: the proposed `station_name` must be one of the
candidate stations actually offered in the `RobotObservation` - this backend
can never invent a station that doesn't exist or isn't currently free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation
from raca_core.llm_client import LLMClient

_PROMPT_TEMPLATE = """You are the decision-making module for one autonomous warehouse \
robot. You may ONLY respond with a single JSON object matching this exact schema - no \
prose, no markdown fences, nothing else:

{{"action": "BID_FOR_TASK", "station_name": "<one of the candidate station names below>", "cost": <number, lower means more eager>}}

or, if no candidate is worth bidding for right now:

{{"action": "WAIT"}}

Robot state:
  robot_id: {robot_id}
  position: ({x:.2f}, {y:.2f})
  battery_soc: {battery_soc:.2f}
  degradation_risk: {degradation_risk:.2f}
  utilization: {utilization:.2f}

Candidate stations (only these are valid values for "station_name"):
{candidates}

Respond with the JSON object only."""


def _format_candidates(observation: RobotObservation) -> str:
    if not observation.candidate_stations:
        return "  (none currently free)"
    return "\n".join(
        f"  - {c.name} ({c.side}) at ({c.x:.2f}, {c.y:.2f})"
        for c in observation.candidate_stations
    )


def build_prompt(observation: RobotObservation) -> str:
    return _PROMPT_TEMPLATE.format(
        robot_id=observation.robot_id,
        x=observation.x,
        y=observation.y,
        battery_soc=observation.battery_soc,
        degradation_risk=observation.degradation_risk,
        utilization=observation.utilization,
        candidates=_format_candidates(observation),
    )


class SchemaError(ValueError):
    """Response failed structural validation."""


class SafetyError(ValueError):
    """Response was structurally valid but proposed something unsafe (a
    hallucinated/invented station)."""


def _parse_and_validate(
    raw: str, observation: RobotObservation, allowed_actions: FrozenSet[str]
) -> CognitiveAction:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"malformed JSON: {exc}") from exc
    if not isinstance(payload, dict) or "action" not in payload:
        raise SchemaError("response is not a JSON object with an 'action' key")

    action_type = payload["action"]
    if action_type not in allowed_actions:
        raise SchemaError(f"unknown or disallowed action {action_type!r}")

    if action_type == "WAIT":
        return CognitiveAction(action="WAIT")

    station_name = payload.get("station_name")
    cost = payload.get("cost")
    if not isinstance(station_name, str):
        raise SchemaError("BID_FOR_TASK requires a string 'station_name'")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool):
        raise SchemaError("BID_FOR_TASK requires a numeric 'cost'")
    valid_names = {c.name for c in observation.candidate_stations}
    if station_name not in valid_names:
        raise SafetyError(f"station {station_name!r} is not a current candidate (unsafe/hallucinated)")

    return CognitiveAction(action="BID_FOR_TASK", station_name=station_name, cost=float(cost))


@dataclass
class LLMDecisionStats:
    requests: int = 0
    schema_failures: int = 0
    fallbacks_used: int = 0


@dataclass
class DecisionMeta:
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    schema_valid: Optional[bool] = None
    safety_valid: Optional[bool] = None
    fallback_used: bool = False
    retry_count: int = 0


@dataclass
class LocalLLMBackend(ReasoningBackend):
    client: LLMClient
    max_retries: int = 2
    fallback: Optional[ReasoningBackend] = None
    stats: LLMDecisionStats = field(default_factory=LLMDecisionStats)
    last_decision_meta: Optional[DecisionMeta] = field(default=None, init=False, repr=False)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        prompt = build_prompt(observation)
        schema_valid: Optional[bool] = None
        safety_valid: Optional[bool] = None
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        for attempt_idx in range(self.max_retries + 1):
            self.stats.requests += 1
            raw = self.client.complete(prompt)
            prompt_tokens = getattr(self.client, "last_prompt_tokens", None)
            completion_tokens = getattr(self.client, "last_completion_tokens", None)
            try:
                action = _parse_and_validate(raw, observation, allowed_actions)
            except SafetyError:
                self.stats.schema_failures += 1
                schema_valid, safety_valid = True, False
                continue
            except SchemaError:
                self.stats.schema_failures += 1
                schema_valid, safety_valid = False, None
                continue
            self.last_decision_meta = DecisionMeta(
                provider=getattr(self.client, "provider", None),
                model=getattr(self.client, "model", None),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                schema_valid=True,
                safety_valid=True,
                fallback_used=False,
                retry_count=attempt_idx,
            )
            return action

        self.stats.fallbacks_used += 1
        self.last_decision_meta = DecisionMeta(
            provider=getattr(self.client, "provider", None),
            model=getattr(self.client, "model", None),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            schema_valid=schema_valid,
            safety_valid=safety_valid,
            fallback_used=True,
            retry_count=self.max_retries,
        )
        if self.fallback is not None:
            return self.fallback.decide(observation, allowed_actions)
        return CognitiveAction(action="WAIT")
