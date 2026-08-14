# Contributing

Thanks for your interest in this project. It began as a solo research
platform, so the process below is intentionally lightweight.

## Reporting bugs / requesting features

Open a GitHub issue. For bugs, include: Python version, the exact
command run, and the relevant test/error output.

## Proposing changes

1. Fork and branch from `main`.
2. Keep changes focused, one logical change per pull request.
3. Add or update tests for any behavior change
   (`python3 -m pytest raca/tests -q` must pass).
4. Follow the existing code style (plain, dependency-free Python; no
   ROS 2 dependency at the `raca_core`/`raca_worlds` level).
5. Do not introduce fabricated or estimated results into documentation:
   report `not measured` rather than a plausible-looking number.

## Research contributions

If you'd like to extend an experiment family (e.g. run a larger seed
count, add a coordination mode), please open an issue first to discuss
scope, this keeps experiment provenance and seed/config choices
traceable.

## Code of conduct

Be respectful and constructive. Reports of abusive behavior can be
sent to the maintainer directly (see `README.md`'s Contact section).
