# Submission Next TODO

Last updated: 2026-03-01

## Priority Backlog

1. Add failure-memory + fix retrieval:
   - Store recurring failure signatures.
   - Fetch prior accepted/deferred fixes before proposing new patches.
2. Add richer evaluation for non-scalar outputs:
   - LLM-judge scorer for text answers.
   - JSON schema parsing fallback for typed answer extraction.
3. Keep dual scoring:
   - strict numeric/string exact match
   - judge score for narrative/text tasks
4. Add SFT escalation gate:
   - Trigger SFT when approved iterative fixes plateau.
   - Use persistent `needs_model_training` clusters for dataset curation.

## Near-Term Milestones

1. Run next 100-question slice with dual scoring enabled.
2. Compare strict vs judge score drift by question cluster.
3. Finalize memory-assisted RCA proposal flow.
