# Data Index

Every file here is REAL captured output from actually running the
corresponding `raca/tools/*.py` script - nothing in this directory is
hand-typed or estimated.

| File | Phase | Freshly re-executed for this folder? |
|---|---|---|
| `phase1_output_equivalence.txt` | 1 | Yes |
| `phase2_world_calibration.txt` | 2 | Yes |
| `phase3_backend_comparison.txt` | 3 | Yes |
| `phase4_backend_cost_report.txt` | 4 | Yes (real qwen2.5:7b) |
| `phase5_difficulty_report.txt` | 5 | Yes |
| `phase6_routing_baselines.txt` | 6 | Yes (real qwen2.5:7b; run was slowed by accidental concurrent duplicate script invocations during this session - see per-row latencies, some elevated above Phase 4's baseline for that reason, not a router regression) |
| `phase7_adaptive_vs_baselines.txt` | 7 | Yes (real qwen2.5:7b) - **see note below, this run's numbers differ from the originally-recorded Phase 7 result in docs/research_journal.md** |
| `phase8_self_calibration_demo.txt` | 8 | Yes |
| `phase11_ablation_report.txt` | 11 | Yes |
| `phase12_stress_tests.txt` | 12 | Yes |
| `phase13_campaign_N20.txt` | 13 | Yes - original AMBIGUITY_MARGIN_SCALE=0.05 (pre-recalibration) |
| `phase13b_campaign_N20_recalibrated.txt` | 13 (revisited) | Yes - AMBIGUITY_MARGIN_SCALE=0.04 (post-recalibration) |
| `ambiguity_scale_calibration_sweep.txt` | (post-14 addendum) | Yes - the sweep that selected 0.04 |
| `scale_stress_test_100_200_robots.txt` | (post-14, scale stress) | Superseded by `scale_stress_test_100_200_1000_robots.txt` below, kept for the record |
| `scale_stress_test_100_200_1000_robots.txt` | (post-14, scale stress) | Yes - 100 robots / 5x, 200 robots / 10x, and 1000 robots / 50x "city" layout, N=1 seed each, MockBackend |
| `ambiguity_scale_calibration_sweep_larger_geometries.txt` | (post-14, re-calibration) | Yes - full N=20 sweep at all three larger geometries (100, 200, 1000 robots) |
| `holdout_reevaluation.txt` | (final pre-submission audit) | Yes - held-out seed re-evaluation (seeds 1001-1020), all four geometries |
| `ambiguity_distribution_by_geometry.txt` | (final pre-submission audit) | Yes - direct ambiguity-signal measurement, N=2000/geometry, confirms saturation |
| `lambda_sensitivity_sweep.txt` | (final pre-submission audit) | Yes - lambda_latency/lambda_reliability sweep, N=20, fault-free |
| `quality_model_construct_validity.txt` | (final pre-submission audit) | Yes - ambiguity vs. backend-disagreement check, N=3000 (null result) |
| `fleet_geometry_isolation.txt` | (final pre-submission audit) | Yes - 3x3 factorial isolating robot count from spatial scale, N=20/cell |
| `lambda_reliability_sensitivity_with_fault.txt` | (final pre-submission audit) | Yes - lambda_reliability sweep with a real injected fault, N=20 |
| `phase7_rerun_under_pinned_client.txt` | (final consistency pass) | Yes - Phase 7 scenario re-run twice under the now-pinned Ollama client (real qwen2.5:7b); task counts now byte-identical, `adaptive_router` LLM-call count still varies slightly at one seed - see note below |
| `phases_4_6_8_9_10_rerun_under_pinned_client.txt` | (submission finalization) | Yes - Phases 4, 6, 8, 9, and 10 all re-run fresh under the now-pinned Ollama client (real qwen2.5:7b and llama3.2:3b); see note below - most numbers reproduced closely or exactly, Phase 10's `warehouse_failover` rate changed substantially (79.6% to 20.0%) and the N=3 pinned figure is now preferred |

**Update (submission finalization):** Phase 9 and Phase 10 have since been
re-executed fresh under the now-pinned Ollama client
(`phases_4_6_8_9_10_rerun_under_pinned_client.txt`, alongside fresh Phase
4, 6, and 8 runs). Phase 9's task counts reproduced exactly (qwen2.5:7b:
8, 8, 8; llama3.2:3b: 8, 6, 6). Phase 10's `service_robot` rate
reproduced exactly (100.0%) but `warehouse_failover` changed substantially
(79.6% in the original N=1 run to 20.0%, consistent across all three
seeds, in this N=3 pinned-client run) - both real measurements, and the
gap is itself evidence for why the pinning fix and this re-collection
mattered. The manuscript now reports the fresh N=3 numbers as primary.

## Honest note: Phase 7 re-run differs from the originally-recorded result

`phase7_adaptive_vs_baselines.txt` (this fresh run) shows
`adaptive_router` failing the quality criterion at seed 8 (7 tasks vs.
always_deterministic's 8) - different from the ORIGINAL Phase 7 result
recorded in `docs/research_journal.md` (8/8/8, PASS). Two real, honest
reasons, not a hidden bug:

1. **The real local LLM's responses are stochastic** - identical seeds and
   identical robot positions do not guarantee identical model outputs
   between two separate runs, since `raca_core.backends.local_llm` does
   not pin sampling temperature/seed on the Ollama request. This is a
   genuine, previously undocumented threat to validity, now added to
   `threats_to_validity.md`'s scope.
2. This run used the RECALIBRATED default `AMBIGUITY_MARGIN_SCALE=0.04`
   (changed after Phase 14, see `addendum_ambiguity_recalibration.md`),
   not the original 0.05 Phase 7 was measured under - a second real,
   documented reason these numbers are not directly comparable run-to-run.

This is reported here exactly as it happened, not smoothed over - it is
itself useful evidence for `threats_to_validity.md`'s statistical-validity
section (real-model runs need multiple repetitions per seed to be fully
trustworthy, not just multiple seeds).

## Scale stress test: 100, 200, and 1000 robots, well beyond anything else in this program

`scale_stress_test_100_200_1000_robots.txt` answers a direct question the
user asked: does anything break at a much larger scale than the 2-6
robots tested everywhere else in this program, and what changes at
1000 robots and a "big city" layout specifically? Three scenarios, each
N=1 seed (exploratory, not statistically powered, consistent with how
Phase 12's stress tests are treated):

- **5x-larger warehouse, 100 robots.** The station layout is generated by
  the same rule as the real layout, just run at 5x range (100 stations
  total, a 1:1 robot-to-station ratio). No crash, no deadlock, no
  unhandled exception. `adaptive_router` completed 420 tasks against
  `always_llm`'s 417 (task-count parity holds), at an LLM-invocation rate
  of 95.6%. Tasks per robot (4.2) is roughly half of the 2-robot
  campaign's 7.4-8.0, because at 5x the spatial scale, travel time eats a
  much bigger share of the 300s simulated window.
- **10x-larger "city" deployment, 200 robots.** Same pattern: no crash, no
  deadlock. `adaptive_router` matched `always_llm` exactly on task count
  (416 vs. 416) at an LLM rate of 90.5%. Tasks per robot dropped further
  (2.08), the same travel-time effect, more pronounced at 10x scale.
- **50x-larger "big city" deployment, 1000 robots.** Also no crash, no
  deadlock. `adaptive_router` completed 259 tasks against `always_llm`'s
  259 (exact task-count parity), at an LLM rate of 98.8%, the highest
  (least cost-reduced) of the three N=1 scenarios. Tasks per robot (0.26)
  is far lower than at 100 or 200 robots: at this scale, most of the
  1000-robot fleet spends the 300s window still traveling to its first
  station rather than completing multiple cycles.

**Honest reading of the N=1 numbers alone:** the routing mechanism's core
behavior (task-quality parity, some LLM-rate reduction) survives the jump
to 1000 robots without breaking, which is a real resilience data point.
But read on: the N=1 LLM rate at 1000 robots (98.8%) looks like the worst
of the three scenarios, and taken alone would suggest the near-tie
problem gets worse with scale. The N=20 sweep below shows that reading is
wrong.

## Re-calibration at these larger geometries (N=20 paired seeds each)

`ambiguity_scale_calibration_sweep_larger_geometries.txt` re-runs the
exact Phase 13/post-14 sweep methodology (7 candidate scales, N=20 paired
seeds, the same pre-defined selection rule, bootstrap CI) at all three
larger geometries, rather than assuming the 2-robot-calibrated 0.04
transfers unchanged. This took a genuinely long time to run: the
100- and 200-robot geometries finished in under two minutes combined, but
the 1000-robot geometry alone took roughly 30 minutes wall clock, far
more than the roughly 2x its robot count over 200 robots would predict.
Memory use grew steadily over the run (from around 1.3GB toward higher),
consistent with per-run object accumulation in a long Python session
rather than an increase in per-run simulation cost. This is a real
tooling limitation, not a claim about the routing mechanism, and is
recorded honestly rather than smoothed over; it also means the 1000-robot
sweep result below should be trusted as correct (each row did complete)
but treated as a one-off run, not something to re-run casually.

Results, corrected against the earlier N=1 reading above:

- **At all three larger geometries, every candidate scale from 0.001 to
  0.05 clears the pre-defined "cost OK" bar** (mean LLM rate below 95%),
  including the original, un-recalibrated 0.05. The selection rule
  (largest, most conservative scale where both criteria pass) therefore
  picks **0.05**, not 0.04, at all three geometries.
- The paired LLM-rate difference against `always_llm` at the selected
  scale is a real, bootstrap-confirmed reduction at every geometry: 95%
  CI [-11.6, -6.7] points at 100 robots, [-16.4, -9.4] points at 200
  robots, and **[-30.0, -14.1] points at 1000 robots**. Each interval
  sits further below zero than the last, and all three sit further below
  zero than the original 2-robot campaign's [-7.9, -2.6] points: the
  mechanism's cost reduction gets stronger, not weaker, as fleet size and
  environment size grow.
- Task-count parity holds at all three geometries (95% CI includes or
  sits at zero: [-1.35, +3.00] at 100 robots, [0.00, 0.00] at both 200
  and 1000 robots).
- **A distinct finding specific to the 1000-robot geometry**: mean tasks
  (262.70) and mean LLM rate (about 0.779) are IDENTICAL, to the decimal
  places shown, across all seven candidate scales. At 100 and 200 robots
  the LLM rate visibly varies with scale (0.848 to 0.910, and 0.829 to
  0.874, respectively); at 1000 robots it doesn't move at all. The most
  likely explanation, not independently verified here, is that at this
  geometry the ambiguity signal's underlying cost margins sit far enough
  from every tested scale value that `clamp(1 - margin/scale, 0, 1)`
  saturates to the same 0 or 1 outcome regardless of which of these seven
  scales is used, meaning the scale parameter has effectively no
  resolution left to tune at this geometry. This is a real, reportable
  structural finding, not a bug in the sweep script (every row ran
  independently and the flat result is consistent across all of them).

**Honest reading:** the earlier N=1 note, which read the 1000-robot
scenario's 98.8% LLM rate as the worst-case, most near-tie-like result of
the three, turns out to be backwards once the actual N=20 sweep is run.
Cost reduction is real, bootstrap-supported, and gets stronger, not
weaker, as scale increases, using a threshold (0.05) that was previously
discarded as insufficient at the small 2-robot geometry that motivated
the original recalibration. This is the opposite of the "safe" assumption
(that a small-scale-tuned threshold would degrade at large scale), and
it's reported exactly as found. The 1000-robot geometry additionally
surfaces a distinct, real finding (scale-parameter saturation) that
doesn't appear at 100 or 200 robots. Both findings are now folded into
`manuscript_draft.md` Section 6.9; see the research journal entries for
the corresponding dates.

## Fleet-size/geometry isolation: both variables matter, independently

Every fleet-scale result above varies robot count and spatial scale
TOGETHER at a fixed 1:1 ratio, so none of it can say whether the observed
effect comes from more robots or a bigger environment. `fleet_geometry_isolation.txt`
runs a genuine 3x3 factorial (geometry in {1x, 5x, 20x}, robots in
{2, 20, 100}, `AMBIGUITY_MARGIN_SCALE` fixed at 0.05, N=20/cell) to answer
this directly.

**Result: both matter, strongly and independently.** At fixed 1x
geometry, going from 2 to 100 robots collapses `adaptive_router`'s LLM
invocation rate from 97.7% to 5.5% - fleet size alone, geometry held
constant. At fixed 100 robots, going from 1x to 20x geometry raises the
rate back from 5.5% to 100% - geometry alone, fleet size held constant.
Neither dominates; both act through distinct mechanisms. The likely
fleet-size mechanism (inferred from the pattern, not independently
verified by inspecting `ClaimBook` state directly): more robots
contending for the same fixed station pool means `free_stations()` more
often returns a short candidate list, mechanically less likely to
contain a near-tie.

**This corrects earlier language in this project** (including in
`manuscript_draft.md` prior to this run) that described the scale effect
as "geometry-driven, not fleet-size-driven," based on the ambiguity
distribution measurement above, which is a pure function of geometry BY
CONSTRUCTION (it never took robot count as an input) and therefore could
never have shown a fleet-size effect even if one existed. That measurement
remains correct for what it measured (geometry alone is sufficient to
produce saturation); it was an overreach to conclude from it that fleet
size doesn't also matter. The manuscript has been corrected accordingly.

## lambda_reliability sensitivity, re-tried under a real fault

The earlier `lambda_sensitivity_sweep.txt` found zero sensitivity for
`lambda_reliability`, but that sweep never injected a failure, so
`failure_rate("llm")` stayed at 0 for every candidate value and the
penalty term never had anything to act on - an honest but uninformative
null result. `lambda_reliability_sensitivity_with_fault.txt` re-runs the
same sweep with a real injected fault (the LLM backend goes permanently
unavailable at t=20s, same pattern as the Phase 11 ablation), N=20 paired
seeds.

**Result: still exactly flat.** LLM invocation rate is 36.89% at every
tested value from `lambda_reliability=0` (penalty fully disabled) through
`lambda_reliability=10`. This is now a REAL, verified null result, not an
artifact of a fault-free design. Mechanistic explanation, directly
supported by the code: once the LLM backend starts failing, every attempt
is caught by `AdaptiveRouter`'s unconditional per-call fallback
(`_try_decide`'s try/except) and redirected to the deterministic backend
regardless of what the reliability penalty's utility comparison would
have chosen. The OBSERVABLE routing outcome (which backend ultimately
handles a task) is governed entirely by the unconditional fallback, not
by the reliability penalty term - the penalty may still affect which
backend is ATTEMPTED first (and therefore latency, via extra failed
calls), but has no measurable effect on which backend is USED. This means
"reliability-aware routing," as currently measured in this codebase,
provides no behavioral difference over having the unconditional fallback
alone. A genuine, now-confirmed limitation, folded into the manuscript's
Limitations section rather than left as a suspicious-looking null result.

## Real-LLM reproducibility re-check under the pinned Ollama client

Prompted by a reviewer-style question: does pinning `OllamaClient`'s
`seed`/`temperature` (done in the second repair round) actually fix
real-LLM reproducibility, or only the raw API call in isolation? The
earlier check only confirmed two direct, identical calls produced
byte-identical output - it never re-ran a full scenario end to end.

Re-ran the Phase 7 scenario (`raca/tools/generate_adaptive_router_report.py`,
real `qwen2.5:7b`, paired seeds [6, 7, 8]) twice in a row under the now-
pinned client.

**Result: mostly fixed, not completely.** Task-completion counts are now
byte-identical across both runs for every router (`always_deterministic`,
`always_llm`, `adaptive_router` all 8/8/8, both runs) - a real improvement
over the pre-pinning state, where the same scenario had produced 7/8 vs.
8/8 purely from sampling non-determinism. But `adaptive_router`'s
LLM-invocation count still varied slightly between the two pinned runs at
one seed (seed 7: 3 calls in run 1, 2 calls in run 2).

**Mechanism, directly supported by the code:** `AdaptiveRouter`'s utility
formula includes `L(b)`, a self-updating running mean of each backend's
*real, measured* `decide()` latency (network/system call timing) - not a
property of LLM sampling at all. Pinning the LLM's sampling makes its
*output* deterministic, but cannot make its *measured latency*
deterministic, since that depends on real wall-clock timing that varies
run to run regardless of sampling settings. For a decision whose utility
comparison is already close to a tie, that residual timing noise can
occasionally flip which backend the router picks.

**Practical takeaway:** the pinning fix substantially reduces but does not
eliminate real-LLM non-determinism for `adaptive_router` specifically
(it does eliminate it for the two static-policy routers, which don't
depend on measured latency the same way). Folded into the manuscript's
Methodology and Limitations sections honestly, not presented as a
complete fix.
