from __future__ import annotations

import pytest

from raca_core.backends.deterministic import DeterministicBackend
from raca_core.backends.local_llm import LocalLLMBackend
from raca_core.backends.mock import MockBackend
from raca_core.backends.replay import ReplayBackend
from raca_core.config import build_backend
from raca_core.contracts import ALLOWED_ACTIONS, CognitiveAction, RobotObservation, StationCandidate


def _observation():
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=1.0,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=(
            StationCandidate(name="output_station_1", side="output", x=3.0, y=0.0),
        ),
    )


def test_build_deterministic_backend():
    backend = build_backend({"backend": "deterministic"})
    assert isinstance(backend, DeterministicBackend)


def test_build_mock_backend():
    backend = build_backend({"backend": "mock", "fixed_cost": 0.9})
    assert isinstance(backend, MockBackend)
    assert backend.fixed_cost == 0.9


def test_build_replay_backend():
    script = [CognitiveAction(action="WAIT")]
    backend = build_backend({"backend": "replay", "script": script})
    assert isinstance(backend, ReplayBackend)
    assert backend.script == script


def test_build_local_llm_backend_with_deterministic_fallback():
    backend = build_backend({"backend": "local_llm"})
    assert isinstance(backend, LocalLLMBackend)
    assert isinstance(backend.fallback, DeterministicBackend)


def test_unknown_backend_name_rejected():
    with pytest.raises(ValueError):
        build_backend({"backend": "quantum_oracle"})


def test_every_backend_answers_the_same_observation_without_crashing():
    # Phase 3's own acceptance criterion: the SAME experimental scenario
    # (here, one observation) runs successfully with every backend, and
    # backend-specific code stays isolated inside build_backend() - this
    # test never imports a concrete backend class to drive the call.
    observation = _observation()
    for config in (
        {"backend": "deterministic"},
        {"backend": "mock"},
        {"backend": "replay", "script": [CognitiveAction(action="WAIT")]},
        # local_llm: no real Ollama server in this test environment, so this
        # only proves it falls back gracefully to deterministic rather than
        # crashing - the pipeline works even when the backend is unreachable.
        {"backend": "local_llm"},
    ):
        backend = build_backend(config)
        action = backend.decide(observation, ALLOWED_ACTIONS)
        assert action.action in ALLOWED_ACTIONS
