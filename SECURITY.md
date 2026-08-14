# Security Policy

## Reporting a vulnerability

This is a research/simulation platform, not production infrastructure,
it has no network-facing service beyond an optional local Ollama LLM
server. If you find a security
issue (e.g. an unsafe deserialization path, an injection vector in
experiment configuration parsing, or a credential-handling problem),
please report it privately to the maintainer
(p.mansournia@gmail.com) rather than opening a public issue, so a fix
can be prepared first.

## Scope notes

- No cloud credentials or API keys are used by default, the LLM
  backend is a local Ollama server. If you configure a cloud LLM
  provider, keep its API key in an environment variable (see
  `.env.example`), never committed to the repository.
- LLM-backed decisions pass through a schema validator with a
  deterministic fallback (see `raca/raca_core/contracts.py` and
  `raca/raca_core/backends/local_llm.py`). Vulnerabilities in that
  validation path are considered high priority.
