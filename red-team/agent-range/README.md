# Agent Range — multi-step tool-using agent security

Where [`../assessment/`](../assessment/) attacks a single-turn assistant, this range attacks a
**RAG + tool-using agent** that runs a multi-step loop — which is where the failures that matter to
agent security live: an instruction planted in a *retrieved* document propagates through the agent's
reasoning into **tool calls** that access credentials, delete data, escape the sandbox, and
exfiltrate. Credential access, unsafe delegation, tool misuse — the whole point of securing agents.

```
poisoned RAG doc → kb_search → [agent obeys retrieved instruction] → db_query / read_file → send_email / http_post
                    (trusted task in)        (untrusted content drives the plan)      (privileged tool)   (data leaves)
```

## What it demonstrates
- **Cross-step taint / attack paths.** The injection enters at retrieval (step 1) and only becomes
  damage several tool calls later. The harness records **every step** with its provenance and draws
  the path, so you can point at exactly where trust was lost.
- **Detection on the whole path.** The flagship detectors grade the retrieved content (indirect
  injection) *and* every tool observation (secret disclosure / exfil) — same OWASP/ATLAS taxonomy.
- **Two defense layers, and a kill point.** The hardened agent (1) quarantines retrieved content the
  detectors flag at ingest, and (2) enforces a **provenance gate** — untrusted retrieved content may
  never drive a privileged tool. The evidence names the **kill point** for each attack. S1/S2 die at
  ingest (detector); S3 shows the layered value — the detector misses at ingest, and the provenance
  gate breaks the chain anyway.

## Scenarios (see [`scenarios.py`](./scenarios.py))
| ID | Chain | Outcome | Maps to |
|----|-------|---------|---------|
| S1 | retrieve → `db_query` (creds) → `send_email` | credential exfil | LLM02 / AML.T0057 |
| S2 | retrieve → `delete_records` | unsafe delegation / destruction | LLM06 / AML.T0053 |
| S3 | retrieve → `read_file` (secrets) → `http_post` | sandbox-escape exfil | LLM05 / AML.T0024 |
| S4 | retrieve only | benign control (no tools, no flags) | — |

## Run it
```bash
python3 red-team/agent-range/run_range.py     # regenerates EVIDENCE.md + results.json
```
Std-lib only, no network/keys. Latest run — **3/3 attacks exploited the vulnerable agent, 3/3
detected, 3/3 broken on the hardened agent, 0 false positives** on the control. The script exits
non-zero if any invariant fails, so it doubles as a self-test. Full paths + per-step detail:
[`EVIDENCE.md`](./EVIDENCE.md).

## Honest scope
The agent, its retrieval, and its tools are deterministic mocks — so exploit success is ground truth,
the run reproduces anywhere, and the focus is the *architecture* failure (provenance across steps) and
its mitigation, not a novel model jailbreak. Planted secrets are fake fixtures (AWS-docs example key,
a fake JWT). The hardened provenance gate is the durable fix; the detector layer inherits the same
heuristic limits noted in the root `README.md` (needs model-based classifiers at production scale).
