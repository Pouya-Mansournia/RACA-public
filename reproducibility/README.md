# Reproducibility package

Raw data captures and analysis scripts needed to reproduce the manuscript's
figures and statistical results ("The Cost and Limits of Proactive
Reasoning Allocation in Multi-Robot Coordination"). Added to the public
repository so the paper's reproducibility claim holds for readers without
access to the private research repository.

- `data/*.txt` — real captured stdout from actually running the
  corresponding `raca/tools/*.py` script; nothing here is hand-typed or
  estimated. See `data/README.md` for what each file is and which
  script produced it.
- `figures/*.png` — reference output of `raca/tools/generate_figures.py`
  run against `data/`, matching the manuscript's figures.

## Regenerating the figures

```bash
python raca/tools/generate_figures.py
```

Reads `reproducibility/data/*.txt`, writes to `reproducibility/figures/`.

## Regenerating the statistics

Every N=20 result uses `raca_core.stats.compute_metric_statistics`
(percentile bootstrap, 2000 resamples, seeded). The scripts under
`raca/tools/` that produced each `data/*.txt` file can be re-run directly,
for example:

```bash
python raca/tools/isolate_fleet_size_from_geometry.py
python raca/tools/holdout_reevaluate_ambiguity_scale.py
python raca/tools/measure_ambiguity_distribution.py
python raca/tools/sensitivity_lambda_sweep.py
python raca/tools/sensitivity_lambda_reliability_with_fault.py
```

Scripts using `MockBackend` or `DeterministicBackend` reproduce
byte-identical results. Scripts that call a real local LLM
(`local_llm`/`DegradableBackend` wrapping it) require a reachable Ollama
server and are not guaranteed byte-identical run to run, as disclosed in
the manuscript's Methods and Limitations sections.

## Not included

The manuscript itself, the internal pre-submission audit trail, the
literature review working notes, and the full chronological research
journal are kept in the private research repository and are not part of
this public release; they are not required to reproduce the reported
results.
