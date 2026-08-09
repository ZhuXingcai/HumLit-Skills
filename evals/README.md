# HumLit Skills Skill Evaluations

`skill-routing-cases.json` is the stable behavior set for Skill discovery and
routing. It has two evaluation layers.

`capability-contract.json` is the release contract for advertised capability
groups. Every registered command must be covered by a maturity level, positive
and negative usage boundary, input preconditions, output contract, failure
modes, and smoke evidence.

## Hard Checks

Run:

```bash
python -m pytest tests/test_skill_behavior.py tests/test_capability_contract.py -q
python scripts/smoke_test.py --mode offline
```

The hard checks verify that every positive case points to an existing fragment
and registered command, that the router documents the route, and that positive
and negative cases are both present. The offline smoke creates and consumes real
local artifacts; it does not call external services.

## Independent LLM Semantic Review

Generate a traceable request bundle before giving the task to an evaluator
outside the implementation session:

```bash
python scripts/evaluate_routing.py prepare \
  --output evals/results/routing-evaluation-request.json
```

The bundle records SHA-256 hashes for `SKILL.md`, the case list, and this
rubric. Give those exact inputs to an external evaluator model. The evaluator
must judge each case independently without executing tools:

1. Whether HumLit Skills should trigger.
2. Which task fragment should be loaded first.
3. Which CLI command is the first deterministic action, if any.
4. Whether clarification is required before execution.

Required JSONL output:

```json
{"id":"search-cnki","trigger":true,"task":"search","fragment":"static/fragments/task/search.md","command":"search","clarify":false,"reason":"..."}
```

A release passes only when:

- Trigger accuracy is 100%.
- Fragment accuracy is 100% for positive cases.
- Command accuracy is at least 90%; a documented clarification decision may
  replace a command when the prompt is intentionally ambiguous.
- No negative case triggers HumLit Skills.
- Agent-assisted cases state the script boundary instead of presenting a signal
  as a final academic judgment.

Validate the returned JSONL and create an auditable summary:

```bash
python scripts/evaluate_routing.py verify \
  --request evals/results/routing-evaluation-request.json \
  --results /path/to/external-results.jsonl \
  --provider <provider> --model <model> --run-id <external-run-id> \
  --output evals/results/v1.0.2-independent-summary.json

python scripts/verify_release.py --version 1.0.2 \
  --require-independent-routing-eval
```

The validator requires exact case coverage and records evaluator provenance,
input hashes, request hash, result hash, and timestamp. A summary with
`independent_evaluator: false` is self-review evidence only and cannot satisfy
the independent gate. Store evaluator output as a CI or release artifact. Do
not commit model credentials or private manuscript content.
