"""Provider-independent LLM transport. Faithful port of
`agent_core.llm_client` - see that module's docstring for the full design
rationale (unchanged here): one method, raw string in, raw string out, so a
real provider only ever implements `complete()` and is never trusted to
have gotten the response format right.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class FakeLLMClient(LLMClient):
    """Returns `responses[i]` on the i-th call; repeats the last response once
    exhausted (or "" if never given any) - deterministic, no network."""

    responses: List[str] = field(default_factory=list)
    _calls: int = field(default=0, init=False, repr=False)

    def complete(self, prompt: str) -> str:
        if not self.responses:
            response = ""
        elif self._calls < len(self.responses):
            response = self.responses[self._calls]
        else:
            response = self.responses[-1]
        self._calls += 1
        return response
