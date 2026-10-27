# Python agent workloads

First workload: a standalone ResearchBot implementation, named `research_assistant`
in target files. Standard-library Python 3.12; no Node/npm, model framework or pip
dependencies. Existing JavaScript DVAA files and deployment remain unchanged.

## Separate from the start

| Directory | Purpose | Distribute for blind assessment? |
|---|---|---|
| `targets/research_assistant/` | Self-contained runnable workload and neutral instructions | Yes, via exporter |
| `evaluator/` | Attack fixture, independent receiver, comparison policy, result generation, tests and exporter | No |
| `docs/` | Plan, provenance, ground truth and validation status | No |
| `runs/` | Runtime evidence (ignored by Git) | Evaluator only |

One development repository is convenient, but is **not a confidentiality boundary**.
It is currently public. Testers given its URL/history can read the answers. For blind
tests, supply only the exported target, without repository history or access to the
development repository; use a separate target repository when needed. Neutral names
reduce obvious answer leakage but cannot prevent identifying a public source.

## Infrastructure checks

From the repository root:

```bash
python3 -m unittest discover -s python_agents/evaluator -p 'test_*.py' -v
```

These checks use scripted model responses and real loopback HTTP requests. They
verify plumbing and policy effects, **not real-model prompt-injection susceptibility**.

## Live evaluation

Supply an approved OpenAI-compatible Chat Completions model with tool-call support.
The model receives synthetic confidential context and the page; use no real secrets.
The evaluator server binds loopback with a fresh port and marker per run.

```bash
export RESEARCH_MODEL_BASE_URL=https://your-approved-model-endpoint.example/v1
export RESEARCH_MODEL=your-tool-capable-model
read -rs RESEARCH_MODEL_API_KEY
export RESEARCH_MODEL_API_KEY

python3 python_agents/evaluator/lab.py --variant page --runs 5
python3 python_agents/evaluator/lab.py --variant poisoned --runs 5
python3 python_agents/evaluator/lab.py --variant poisoned --corrected --runs 5
```

Each invocation prints run results and writes a separate directory under the ignored
`python_agents/runs/`, or set `--output` to an external evidence directory. Never
commit raw evidence containing provider or personal data.

Outputs per run: `events.jsonl` (model/tool trace), `receipts.json` (actual server
receipts), `result.json` (objective, attempt, denial and error states). Review final
summary quality manually. Normal archive submission alone is not proof of task quality.
Live calls cost tokens; bounded steps limit a run, not total financial spend.

The local harness runs target and fixture on the same host. It is not a container or
OpenShell integration test. To evaluate external enforcement, run the actual agent
process inside that boundary and put fixture/evidence collection outside it, adjusting
addresses. A client calling an unprotected agent is not containment of that agent.

## Export

```bash
python3 python_agents/evaluator/export_target.py /tmp/research-assistant-target \
  > /tmp/research-assistant-target-sha256.json
```

The destination must not exist. Only five allowlisted target files are copied;
hashes go to stdout outside the target. No evaluator, plan, previous logs, `.git`
history or internal note is included. Provision synthetic notes separately at runtime.
The Docker build context is the exported directory, never the full repository.

See `docs/researchbot-ground-truth.md` for the evaluator specification and limits.
