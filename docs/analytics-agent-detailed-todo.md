# Analytics Agent Detailed TODO

Builds on: `docs/analytics-agent-plan.md`  
Project target: W&B project `jupybot` under entity `shukla-vivek1993-startup`
Supporting references:
- `docs/langgraph-server-research-notes.md`
- `docs/evals-rca-skill-reference.md`

## Project Goals

- [ ] Goal 1 (active now): Build a robust self-improving analytics agent end-to-end.
1. Must run the full eval/improve loop on Spider with measurable metrics.
2. Must have strong observability via W&B runs + Weave traces.
3. Must be stable enough to debug, iterate, and benchmark reliably.

- [ ] Goal 2 (end goal, deferred): Create reusable "skills" that can be plugged into other LangGraph agents.
1. Skills should help a coding agent set up a full self-evolving loop for different agent types.
2. Skills are reference-productization of what we prove in Goal 1.
3. We will not implement skills now.
4. Skills work starts only after Goal 1 is complete and bugs are ironed out.

## Cross-Phase Learning Capture (For Future Skill Extraction)

- [ ] Maintain a learning log during every phase (instead of building skills now).
1. Capture issues, RCA, and fixes as they happen.
2. Capture references used (docs links, examples, API notes).
3. Capture reusable patterns (tracing setup, eval setup, Mistral integration, run metadata mapping).
4. Capture anti-patterns and failed approaches.

- [ ] Standardize log format so it can be converted to skills later:
1. Context (what we tried)
2. Problem
3. Evidence (run IDs, trace IDs, errors)
4. RCA
5. Fix implemented
6. Validation result
7. Reusability notes (candidate future skill)

## 0. Scope Lock And Standards

- [ ] Read and confirm current LangGraph runtime guidance before coding:
1. Review `docs/langgraph-server-research-notes.md`.
2. Decide implementation path: current `create_agent` runtime vs legacy `create_react_agent` pin.
3. Record the explicit version/runtime decision in the implementation README.

- [ ] Confirm fixed architecture:
1. Agent framework is LangGraph runtime with ReAct-style behavior, not a custom tool loop.
2. Tool interface is LangChain/LangGraph tool definitions.
3. Tracing is W&B Weave with full run-level coverage for each agent execution (`@weave.op` optional for non-graph helpers).
4. Experiment tracking is W&B Models runs/artifacts.
5. Benchmark source is Spider dev split with SQLite execution.

- [ ] Confirm required outputs:
1. Baseline accuracy run (50-100 questions).
2. Full per-question traceability (question -> tool calls -> answer -> score).
3. Failure analysis grouped into actionable categories.
4. Repeatable improvement loop.

- [ ] Define repo layout (must match plan before coding):
1. `analytics-agent/phase0_tests/`
2. `analytics-agent/agent/`
3. `analytics-agent/eval/`
4. `analytics-agent/sft/`

## 1. Phase 0 Environment And Integration Validation

- [x] Create `analytics-agent/requirements.txt` with pinned/min-version dependencies:
1. `mistralai`
2. `langgraph`
3. `langchain-core`
4. `wandb`
5. `weave`
6. `python-dotenv`
7. `pandas`, `numpy`, `matplotlib`, `scipy`

- [x] Create `analytics-agent/.env.example`:
1. `MISTRAL_API_KEY=`
2. `WANDB_API_KEY=`
3. `WANDB_PROJECT=jupybot`
4. `WANDB_ENTITY=shukla-vivek1993-startup`
5. Optional `SPIDER_ROOT=analytics-agent/data/spider`

- [x] Implement `analytics-agent/phase0_tests/test_all.py` in one file:
1. Mistral basic chat call.
2. W&B metric log sanity check.
3. Weave trace sanity check.
4. Spider DB and gold SQL execution check.
5. Mistral tool-calling check.
6. Python subprocess execution check.

- [x] Add Phase 0 LangGraph ReAct runtime smoke test:
1. Create a minimal ReAct-style agent callable from Python (single prompt + simple tool).
2. Add LangGraph config (`langgraph.json`) and graph entrypoint for server compatibility.
3. Execute one direct Python invocation of the agent function and verify structured output.
4. Optionally run a local LangGraph server smoke path (if environment supports it), but Python invocation is mandatory.

- [x] Add Phase 0 end-to-end trace + eval smoke test:
1. Run the minimal agent once with full run tracing enabled (root run + child spans).
2. Execute a tiny Weave/W&B evaluation on a micro dataset (1-3 rows) using a basic scorer.
3. Verify run metadata mapping exists: question id -> expected output -> trace id -> eval score.

- [x] Add pass/fail summary and non-zero exit code on any failure.

- [x] Phase 0 learning log update:
1. Record setup gotchas for LangGraph runtime/server config.
2. Record Mistral API integration quirks in agent context.
3. Record W&B/Weave tracing and eval smoke-test lessons.
4. Record final “known-good baseline” commands/checks.

- [x] Approval checkpoint A:
1. All 8 checks pass.
2. User confirms W&B run and Weave trace visible.
3. User confirms minimal LangGraph ReAct run is traced and evaluated end-to-end.

## 2. Phase 1 Agent Core (LangGraph ReAct)

- [x] Implement modular tool package using LangChain tool wrappers:
1. `agent/tools/sql_tool.py` for `execute_sql(sql: str)`.
2. `agent/tools/python_tool.py` for `run_python(code: str)`.
3. `agent/tools/__init__.py` to expose registered tools.
4. Keep tool state/input contracts explicit and testable.

- [x] Implement `agent/prompt.py`:
1. Enforce workflow EXPLORE -> PLAN -> EXECUTE -> ANSWER.
2. Enforce structured final JSON fields:
   `answer_value`, `answer_text`, `sql`, `notebook_cells`.
3. Include SQL-vs-Python split policy from original plan.

- [x] Implement `agent/notebook.py`:
1. Append each SQL/Python tool invocation as notebook cells.
2. Store input code, output preview, and error text if any.

- [x] Implement `agent/agent.py`:
1. Build Mistral chat model adapter usable by LangGraph runtime.
2. Build graph via selected ReAct-compatible runtime path (decision from Section 0).
3. Collect tool-call metrics from execution.
4. Return final structured result + notebook + metrics.

- [ ] Add LangGraph Server deployment files:
1. Add `langgraph.json` with schema/dependencies/graphs/env.
2. Add graph entrypoint module referenced by `langgraph.json`.
3. Add minimal local server run instructions and verification steps.

- [x] Add a single-question smoke runner in `agent/`:
1. Inputs: question + db path.
2. Outputs: answer JSON + notebook JSON.

- [x] Add Phase 1 integration test suite focused on agent-level behavior:
1. `phase1_tests/test_agent_e2e.py` for end-to-end agent output validation.
2. Validate tool-call evidence via notebook/tool metrics, not isolated tool unit tests.
3. Validate trace IDs (`call_id`, `trace_id`) and mapping artifact generation.
4. Validate micro Weave evaluation over agent predictions.

- [x] Approval checkpoint B:
1. One Spider question runs end-to-end through LangGraph ReAct.
2. Final output includes required JSON fields.
3. Notebook cell history is produced.

- [x] Phase 1 learning log update:
1. Record agent architecture decisions and tradeoffs.
2. Record tool interface design choices and failure modes.
3. Record notebook-state model decision and concurrency implications.
4. Record references/examples that proved reliable.

## 3. Phase 1 Observability (W&B + Weave)

- [x] Enable full-run tracing for LangGraph agent execution:
1. Trace each benchmark question as one root agent run.
2. Capture graph/node transitions and tool spans under the root run.
3. Ensure final model output, score payload, and key metadata are attached to that run.
4. Use `@weave.op` selectively for custom non-graph helpers only when needed.

- [x] Add W&B run logging for per-question metrics:
1. `exec_accuracy`
2. `sql_error_rate`
3. `python_error_rate`
4. `tool_calls_count`
5. `cells_generated`
6. `retry_count`
7. `latency_ms`

- [x] Log notebook JSON as artifact per evaluated question batch.
1. Added `--capture-notebooks` flag in `eval/runner.py` to persist notebooks in lean mode when needed.
2. `mode=full` continues to include notebook and trace dumps automatically.

- [x] Add trace metadata capture for each evaluated question:
1. `call_id`
2. `trace_id`
3. status
4. start/end timestamps
5. latency
6. optional tracked cost fields when available

- [x] Keep observability payload lean by default (no heavy dumps unless needed):
1. Always persist `trace_index.jsonl` with `question_id`, `expected_value`, `answer_value`, `correct`, `wandb_run_id`, `trace_id`, `call_id`, `prompt_version`, `agent_version`.
2. Persist `predictions.jsonl` for benchmark result replay.
3. Keep raw full-trace/notebook dumps optional (`mode=full`) and disabled for default runs.

- [x] Ensure tracing is full-run and evaluation-centric:
1. Capture/associate root agent run trace for each benchmark question.
2. Capture child nodes/tools under that root trace.
3. Avoid tool-only evaluation blind spots.

- [x] Persist trace metadata to local JSONL and W&B artifact.

- [x] Add dashboard-friendly observability outputs while keeping defaults lean:
1. Log compact prediction/failure tables (`dashboard/predictions_table`, `dashboard/failures_table`) for run-level review.
2. Keep canonical summary keys under `summary/*` to stabilize workspace panels across runs.
3. Truncate long text fields in logged rows to avoid noisy/heavy payloads.

- [x] Approval checkpoint C:
1. Weave trace tree visible for agent runs.
2. W&B metrics populated for same runs.
3. Trace metadata artifact available (notebook artifact optional in full mode).

- [x] Observability learning log update:
1. Record full-run tracing patterns that work reliably.
2. Record trace metadata schema decisions for benchmark mapping.
3. Record W&B logging conventions (run names, artifact naming, grouping).
4. Record any gaps between LangGraph traces and Weave traces + mitigation.

## 4. Phase 2 Benchmark Runner And Scoring

- [ ] Implement `eval/scorer.py`:
1. Value-first scoring against gold SQL result.
2. Numeric tolerance/rounding handling.
3. Safe handling for empty/NULL outputs.

- [ ] Implement `eval/runner.py`:
1. Load Spider `dev.json` and db paths.
2. Run configurable subset (`--limit`).
3. Run agent output and gold SQL execution.
4. Compute per-question correctness and running accuracy.
5. Log row-level and aggregate metrics to W&B.

- [ ] Add Weave scorer integration (`eval/weave_scorers.py`):
1. Function-based scorer for correctness.
2. Class-based scorer for aggregated operational metrics if needed.
3. Optional `summarize` override for final report metrics.

- [x] Ensure benchmark run outputs include:
1. `predictions.jsonl`
2. `failures.jsonl`
3. `trace_index.jsonl` mapping question ids to trace ids
4. `question_history.jsonl` with one row per `(question_id, run_id)` for cross-run behavior tracking.
5. `fix_judgement.jsonl` linking question outcomes to accepted/rejected fix IDs.
Notes:
- `failures.jsonl` is now emitted by `eval/observability.py` for each run.
- `question_history.jsonl` is generated by `eval/question_history.py`.
- `fix_judgement.jsonl` is managed via `eval/fix_registry.py judge-question`.

- [ ] Implement W&B dashboard structure for benchmark runs:
1. Enforce run naming convention with timestamp + variant (`baseline`, `prompt_iter_n`, `ft_vn`).
2. Add run grouping keys (`phase`, `benchmark_split`, `agent_version`, `prompt_version`).
3. Log canonical summary metrics on every run so panels remain stable over time.
4. Add benchmark panels:
   accuracy trend, exec accuracy, SQL/Python error rates, latency distribution, tool call distribution.
5. Add failure-analysis panels:
   category counts, top failing db_ids, top failing question patterns, RCA status counts.
6. Add evidence-link panels/tables:
   run id, prompt artifact, model artifact, trace index artifact, sample failing trace links.
7. Keep a saved W&B workspace layout template for reproducible review across iterations.
Notes:
- Naming convention is implemented in `eval/runner.py` via `--run-variant` + `--iteration` (default when `--run-name` omitted).

- [ ] Approval checkpoint D:
1. Baseline benchmark completes on at least 50 questions.
2. Accuracy and failure count visible in W&B.
3. Trace index artifact generated.

- [ ] Benchmark/eval learning log update:
1. Record scorer behavior edge cases and normalization rules.
2. Record benchmark orchestration reliability lessons (resume, retry, idempotency).
3. Record best practices for linking eval rows to traces and runs.
4. Record references for W&B eval/scorer APIs used.

## 5. Phase 2 Self-Improvement Loop (W&B Evals + Coding Agent RCA)

- [x] Define and enforce RCA category taxonomy (required per failed question):
1. `prompt_update`
2. `tool_design`
3. `architecture_change`
4. `needs_model_training`
5. Optional secondary tags allowed, but one primary tag is mandatory.
Notes:
- Enforced via `eval/fix_registry.py propose --rca-tag ...` (choices restricted to taxonomy).

- [ ] Add per-question longitudinal tracking across runs:
1. Track each `question_id` across all iterations (`baseline`, `iter_n`, `ft_vn`).
2. Store status transitions: `pass->pass`, `fail->pass`, `pass->fail`, `fail->fail`.
3. Track first-fix version and current-fix version for each question.
4. Add dashboard panel/table: "question behavior across versions".
Notes:
- Data-layer tracking implemented in `eval/question_history.py`.
- Dashboard panel wiring remains pending.

- [x] Add fix registry with versioned evidence:
1. Create `fix_registry.jsonl` with `fix_id`, `rca_tag`, `change_type`, `description`.
2. Link each fix to `agent_version`, `prompt_version`, `toolset_version`, `graph_version`.
3. Link evidence fields: `run_id`, `trace_ids`, affected `question_ids`, before/after metrics.
4. Record decision state: `proposed`, `accepted`, `rejected`, `rolled_back`.
Notes:
- Implemented by `eval/fix_registry.py` (`propose`, `decide`, `link-evidence`, `export-current`).

- [x] Add prompt governance rules to prevent prompt bloat:
1. Define hard prompt budget (`max_prompt_chars` or token budget) and fail CI/check if exceeded.
2. Do not add one-off prompt patches for isolated failures.
3. Only allow prompt additions when a repeated pattern appears across at least `N` failures (default `N=5`, tunable to `10`).
4. If pattern count is below threshold, route fix to tool/architecture/model backlog instead of prompt growth.
5. Log every prompt delta with rationale and impacted question cluster IDs.
Notes:
- Enforced by `eval/prompt_governance.py`.
- Runner logs prompt size/budget metadata (`prompt_chars`, `prompt_tokens_est`, budget limits, `prompt_budget_ok`).

- [ ] Follow operating model in `docs/evals-rca-skill-reference.md`:
1. Use W&B Weave evaluation outputs as the primary evidence layer.
2. Use coding-agent RCA over runs/prompts/graph/traces for fix proposals.
3. Keep custom automation minimal and evidence-driven.

- [ ] Implement RCA artifacts (md/jsonl) per iteration:
1. Failure category and root-cause hypothesis.
2. Evidence links (W&B run IDs + trace IDs).
3. Candidate fixes and risk assessment.
4. Accept/reject/defer decision with rationale.
5. RCA primary tag (`prompt_update` / `tool_design` / `architecture_change` / `needs_model_training`).
6. Prompt-governance decision (`allowed` / `blocked_by_threshold` / `blocked_by_budget`).

- [ ] Implement iterative orchestrator:
1. Evaluate -> RCA -> propose targeted changes -> re-evaluate.
2. Stop on plateau (`accuracy delta < 1%`) or max iterations.
3. Save per-iteration comparison table.
4. For each proposed fix, run targeted validation slice (affected questions) before full benchmark pass.
5. Auto-rollback fix if targeted slice regresses above threshold.

- [ ] Add eval-loop metrics and reporting package (per iteration):
1. Capture agent snapshot before/after each loop (`prompt_version`, `toolset_version`, `graph_version`, key config flags).
2. Log exact change summary for the iteration (what was updated, why, expected impact).
3. Track core deltas: `accuracy`, `exec_accuracy`, `sql_error_rate`, `python_error_rate`, `latency_ms`, `tool_calls_count`, `retry_count`.
4. Track RCA outcome metrics: failure categories addressed, fixes attempted, accepted/rejected/deferred counts.
5. Persist one row per iteration in `improvement_iterations.jsonl/csv` for easy trend analysis.
6. Generate report artifacts: iteration comparison table, trend chart, and "change -> metric impact" summary.
7. Link every iteration row to evidence (`wandb_run_id`, `weave_trace_ids`, prompt artifact/model artifact ids).
8. Track prompt governance metrics: prompt size, delta size, blocked prompt changes, threshold-triggered prompt changes.
9. Track question-level fix efficacy: questions improved, regressed, unchanged per fix.

- [ ] Build Phase 2 improvement dashboard (iteration-centric):
1. One row per iteration with before/after deltas for all core metrics.
2. "Change applied -> metric impact" table with accepted/rejected/deferred labels.
3. Regression guard panel highlighting any metric degradations over threshold.
4. Evidence drill-down links from dashboard rows to traces and RCA notes.
5. Mark and pin current best iteration (best prompt/model combo).
6. Add RCA tag distribution panel (prompt/tool/architecture/model-training).
7. Add question longitudinal outcomes panel (fixed, regressed, unstable, persistent failures).
8. Add prompt growth panel (prompt size over iterations with budget line).

- [ ] Approval checkpoint E:
1. At least 3 iterations run.
2. Accuracy trend chart visible.
3. Best prompt artifact identified.
4. Iteration dashboard supports RCA drill-down without manual ad hoc filtering.

- [ ] Improvement-loop learning log update:
1. Record RCA templates that led to high-quality fixes.
2. Record accepted vs rejected fix patterns and why.
3. Record prompt update strategies that generalized across failures.
4. Record workflow pieces that should become future "RCA skill" components.
5. For each new iteration, reference prior learnings entries before selecting new fixes.

## 6. Phase 3 SFT Preparation And Execution

- [ ] Implement `sft/build_dataset.py`:
1. Build supervised records from successful corrected traces.
2. Include schema context, question, reasoning steps, tool use, final answer.
3. Validate JSONL format expected by Mistral fine-tuning API.

- [ ] Implement `sft/finetune.py`:
1. Upload training/validation files.
2. Launch fine-tune job.
3. Track status polling and terminal state.
4. Log fine-tuned model id as artifact and config.

- [ ] Keep SFT pipeline "skill-ready" while building:
1. Document each repeatable SFT step in reference notes.
2. Avoid hard-coded one-off logic in scripts.
3. Preserve clean boundaries for later skill extraction.

- [ ] Add evaluation pass for fine-tuned model on same benchmark slice.

- [ ] Approval checkpoint F:
1. Fine-tune job completes.
2. Before/after metrics logged in W&B.
3. Model artifact and comparison report saved.

- [ ] SFT learning log update:
1. Record dataset curation rules that improved SFT quality.
2. Record Mistral SFT API workflow details and operational pitfalls.
3. Record evaluation strategy for FT vs prompt-only comparisons.
4. Mark reusable steps for future “SFT pipeline skill”.

## 7. Trace Retrieval And Analysis Utilities (MCP-Aligned)

- [ ] Add `eval/export_traces.py` utility:
1. Export run-linked trace ids and key metadata.
2. Support filtering by run name, time range, status.
3. Emit analysis-ready JSONL/CSV.

- [ ] Add `eval/trace_report.py` utility:
1. Summarize top failing ops.
2. Summarize latency/cost distributions.
3. Link failure categories to trace ids.

- [ ] Ensure outputs are compatible with later MCP queries.

- [ ] Trace-ops learning log update:
1. Record most useful trace query filters and metadata fields.
2. Record practical mapping patterns from traces to eval outcomes.
3. Record export/report formats best suited for RCA automation later.

## 8. Definition Of Done (Full Project)

- [ ] End-to-end run works from clean checkout + `.env`.
- [ ] Phase 0 checks all pass.
- [ ] LangGraph ReAct agent is the production path.
- [ ] Baseline benchmark and metrics are reproducible.
- [ ] Weave traces and W&B artifacts are linked per run.
- [ ] Improvement loop yields measurable change or clear plateau report.
- [ ] SFT workflow is executable and benchmarked.
- [ ] W&B dashboards are stable, comparable across runs, and usable for RCA without custom one-off queries.

## 9. Execution Order

- [x] Step 1: Phase 0 validation.
- [ ] Step 2: Agent core (LangGraph ReAct) + observability.
- [ ] Step 3: Benchmark runner + scorer.
- [ ] Step 4: Improvement loop.
- [ ] Step 5: SFT.
- [ ] Step 6: Trace export/report hardening.

## 10. Post-Goal-1 Roadmap (Reference Only, Not In Current Scope)

- [ ] Convert proven analytics-agent components into reusable skill modules.
- [ ] Define skill templates by agent type (analytics agent, coding agent, eval agent).
- [ ] Package setup + orchestration + scoring + tracing as composable skills.
- [ ] Validate skills by applying them to at least one non-analytics LangGraph agent.
- [ ] Document installation and usage patterns for future reuse.

## 11. Living Skill-Reference (In Scope For Documentation, Not Packaging)

- [ ] Maintain skill-reference docs during implementation:
1. `docs/evals-rca-skill-reference.md`
2. `docs/langgraph-server-research-notes.md`
3. Additional workflow references as needed.
- [ ] Update these references whenever runtime architecture, prompts, or evaluation workflow changes.
- [ ] After Goal 1 is stable, extract these references into formal skills in ordered form.

- [ ] Add dedicated learnings docs and keep them current:
1. `docs/learnings/phase0.md`
2. `docs/learnings/phase1-agent.md`
3. `docs/learnings/phase1-observability.md`
4. `docs/learnings/phase2-benchmark-eval.md`
5. `docs/learnings/phase2-improvement-loop.md`
6. `docs/learnings/phase3-sft.md`
7. `docs/learnings/trace-ops.md`
