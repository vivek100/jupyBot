# Skills Index

This is the main entrypoint for the skills package.

## Purpose

This package teaches any coding agent how to run a full self-improving eval loop:
1. setup project context,
2. run tracked evaluations,
3. generate and review RCA,
4. apply human-gated fixes,
5. map versions to outcomes,
6. prepare submission artifacts.

## When To Use

Use these skills when you need repeatable, evidence-driven iteration for an analytics agent, with W&B/Weave observability and trace-linked RCA.

## How To Use

1. Start with this file.
2. Pick the skill that matches your current step.
3. Execute the step in order for a full loop, or use only the needed module.
4. Keep run labels, version mapping, and RCA records consistent across all runs.

Recommended sequence:
1. `01-mcp-project-bootstrap`
2. `02-tracing-artifacts`
3. `08-wandb-evals-setup`
4. `03-eval-dashboard`
5. `04-rca-human-gate`
6. `05-version-mapping`
7. `06-submission-packaging`
8. `07-next-iteration-evals`

## Available Skills

1. [01-mcp-project-bootstrap](./01-mcp-project-bootstrap/SKILL.md)  
Resolve correct W&B entity/project context via env + MCP before any run.

2. [02-tracing-artifacts](./02-tracing-artifacts/SKILL.md)  
Enforce trace/prediction/failure artifact coverage per run.

3. [03-eval-dashboard](./03-eval-dashboard/SKILL.md)  
Execute benchmark slices, label runs, publish canonical dashboard outputs.

4. [04-rca-human-gate](./04-rca-human-gate/SKILL.md)  
Perform RCA with mandatory human approval before new eval iterations.

5. [05-version-mapping](./05-version-mapping/SKILL.md)  
Map agent SHA + prompt version + run labels for reproducibility.

6. [06-submission-packaging](./06-submission-packaging/SKILL.md)  
Prepare final submission narrative and evidence links from run artifacts.

7. [07-next-iteration-evals](./07-next-iteration-evals/SKILL.md)  
Plan memory, LLM-judge, JSON parsing, and SFT escalation workflow.

8. [08-wandb-evals-setup](./08-wandb-evals-setup/SKILL.md)  
Configure W&B/Weave eval setup, scorer strategy, and run-level eval logging schema.

## Demo Data Convention

For judge/demo usability, maintain run data in:
1. `analytics-agent/outputs/runs/run_1/`
2. `analytics-agent/outputs/runs/run_2/`
3. `analytics-agent/outputs/runs/run_3/`
