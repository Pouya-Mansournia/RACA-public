"""Real, free, local LLM provider: an `LLMClient` backed by Ollama.

Faithful port of `agent_core.ollama_client` - unchanged behavior, only the
import path moved (`raca_core.llm_client` instead of `agent_core.llm_client`).
See the original module's docstring for the full rationale (no account, no
API key, no per-token cost, standard-library-only `urllib`).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from raca_core.llm_client import LLMClient

PROVIDER_NAME = "ollama"


@dataclass
class OllamaClient(LLMClient):
    model: str = "qwen2.5:7b"
    host: str = "http://127.0.0.1:11434"
    timeout_sec: float = 30.0
    # Final pre-submission red-team audit, Critical Audit 9: prior to this,
    # no sampling options were sent at all, so Ollama used its own defaults
    # and repeated calls with identical input were not reproducible (see
    # docs/research_journal.md's Phase 7 re-run discrepancy). Pinning these
    # makes `complete()` deterministic for a given prompt+model+seed;
    # `seed=None` (the previous, implicit behavior) is still selectable by
    # constructing with `seed=None` explicitly if non-determinism is wanted.
    seed: Optional[int] = 0
    temperature: float = 0.0
    provider: str = field(default=PROVIDER_NAME, init=False)
    last_prompt_tokens: Optional[int] = field(default=None, init=False, repr=False)
    last_completion_tokens: Optional[int] = field(default=None, init=False, repr=False)

    def complete(self, prompt: str) -> str:
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        options = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed
        body = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": options}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return ""
        self.last_prompt_tokens = payload.get("prompt_eval_count")
        self.last_completion_tokens = payload.get("eval_count")
        return payload.get("response", "")
