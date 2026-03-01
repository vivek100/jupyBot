# Evals + RCA + Skill Reference Plan

Last updated: 2026-03-01

## Intent

This file defines how we improve the analytics agent without writing an over-customized autonomous fixer too early.

## Core principle

Use W&B Weave evaluations and scorers as the primary evaluation engine.  
Use the coding agent for RCA and fix proposal decisions on top of run and trace evidence.

## Phase 2 operating model (replaces custom clustering-first plan)

1. Run benchmark evaluation with Weave `Evaluation` and project scorers.
2. Collect run-level outputs:
   - correctness metrics
   - failure rows
   - trace index (question/run -> trace ids)
3. Coding agent performs RCA from:
   - prompt version
   - agent graph structure
   - tool behavior
   - full run traces
4. Coding agent proposes candidate fixes and expected impact.
5. Re-run benchmark and compare deltas in W&B.
6. Accept/reject fixes using evidence, not heuristic guessing.

## RCA output template (required per iteration)

1. Failure category
2. Evidence links (W&B run + trace ids)
3. Root-cause hypothesis
4. Candidate fix
5. Risk of regression
6. Validation plan
7. Final decision (accept/reject/defer)

## Decision rubric for fix acceptance

1. Improves accuracy or stability on target category.
2. Does not degrade overall benchmark beyond agreed threshold.
3. Keeps agent/runtime complexity manageable.
4. Preserves traceability and reproducibility.

## W&B-first evaluation coverage

Use Weave as much as possible for:

1. row-level correctness scoring
2. aggregated score summarization
3. programmatic scorer output persistence
4. run-to-run comparability in W&B

Keep custom code focused on:

1. data loading and benchmark orchestration
2. adapter glue for trace metadata mapping
3. output packaging and artifact persistence

## SFT workflow intent (future but code should be reusable)

1. Build repeatable data extraction from accepted-fix traces.
2. Launch and track Mistral SFT jobs with minimal bespoke logic.
3. Keep this pipeline ready to move into a reusable skill later.

## Living skill-reference policy (active now, extraction later)

During implementation of Goal 1:

1. Maintain small reference docs for each repeatable workflow:
   - eval run setup
   - trace export + mapping
   - RCA iteration
   - SFT launch + validation
2. Keep steps explicit and toolable so they can become skills later.
3. Do not package/install skills yet.

After Goal 1 stabilization:

1. Extract these references into reusable skill modules.
2. Standardize ordering and parameterization by agent type.

## Sources

- W&B Weave scoring overview: https://docs.wandb.ai/weave/guides/evaluation/scorers
- W&B Weave evaluations intro: https://docs.wandb.ai/weave/guides/core-types/evaluations
- W&B Weave traces and ops: https://docs.wandb.ai/weave/guides/tracking/ops

