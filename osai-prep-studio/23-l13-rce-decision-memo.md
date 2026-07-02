# L13 "MCP → RCE" — Realism Decision Memo

> **Decision: keep L13 deferred as a contained mock/structural lab.** Do **not** add
> Ollama realism now, and treat a *real* execution simulator as **out of scope
> indefinitely** absent a separately-approved infrastructure epic. This memo records the
> threat-model reasoning so the decision is auditable. Companion:
> [02-lab-range.md](02-lab-range.md), [13-platform-threat-model.md](13-platform-threat-model.md),
> the Ollama realism arc ([`spine/deploy/docker-compose.ollama.yml`](spine/deploy/docker-compose.ollama.yml)).

## Context

L13 exercises **MCP → remote code execution on the tool surface**: OWASP **LLM05**
(Improper Output Handling), detector `improper_output_handling`, agentic threat **T11**
(Unexpected RCE & Code Attacks). Its manifest lists a `flag` plus a `container_exec_log`
evidence token and an "isolated execution container" authorized scope.

**Current state (important):** L13 is **already a working, contained lab.** It routes to
the deterministic mock target and grades **structurally** — the `improper_output_handling`
detector fires on a transcript where model output reaches an unsafe sink (an
*active-content payload*), plus the planted flag. `test_l13_active_content_to_sink_passes`
proves a passing loop; `test_l13_plain_output_no_signal_a` proves benign output does not.
**No real execution exists today**, and none is required for the lesson.

The Ollama realism arc (merged) added lab-specific realism where **model behavior itself
was the lesson**: L03–L07 (chat), L09 (RAG write-poisoning), L12/L16 (MCP tool
shadowing / excessive agency). L13 is a different risk class, so it was held for this memo.

## The eight questions

**1. Does L13 need Ollama realism at all?** Marginally at best. The lesson is about the
**sink and output-handling boundary**, not the model's phrasing. A real model would only
make the active-content payload less deterministic — low value-add versus the chat/RAG/MCP
labs where model behavior *was* the point.

**2. Can the objective be met with the current mock/structural target?** **Yes — it
already is.** The detector-based grade loop teaches *recognize and exploit model output
flowing into an unsafe exec sink* with no model and no execution.

**3. If we add realism, can it remain string-only?** Yes, and this is the **only**
acceptable form: a model (real or mock) emits an active-content payload **string**, and a
**simulated exec sink** *synthesizes* a `container_exec_log` entry and returns the flag.
The output is text; the "execution" is a recorded string — exactly the L12/L16
`simulate_tool_call` containment pattern applied to a sink.

**4. What would a "safe execution-simulator" mean without real side effects?** A pure
function `payload → synthetic exec-log entry + flag` that reproduces the *shape* of an RCE
(command captured, sink reached) as **fabricated audit data** matching the manifest's
`container_exec_log` token — never a real process, shell, container, or file.

**5. Abuse risks — why this is a different risk class.** The danger is not the simulator;
it is **drift toward realism.** "To feel real, just run it in a throwaway container" is the
slippery slope: a real exec sink executes arbitrary learner-supplied commands — real
RCE-as-a-service. Even sandboxed, it adds container-escape surface, egress-control burden,
resource-exhaustion / denial-of-wallet vectors, and a weaponization path the other labs do
not have. The chat/RAG/MCP labs **never execute anything**; L13-with-real-exec would.

**6. Containment controls *if* real execution were ever pursued (not recommended).**
Ephemeral per-attempt container; seccomp / AppArmor; `cap_drop: ALL`; read-only rootfs;
no-new-privileges; egress-denied network namespace; hard CPU / memory / wall-time / PID
limits; non-root uid; no host mounts; per-learner isolation; output-size caps; an
independent kill-switch. That is a **standing infrastructure project**, not a lab PR —
which is exactly why it must be a separate, separately-approved epic.

**7. Tests that would prove no real execution exists (for the string-only path).**
- **Source guard:** the sink module contains no `subprocess / os.system / os.popen /
  socket / pty / ctypes / exec( / eval(` (the same guard used for `simulate_tool_call`).
- **Behavioral:** a payload that *would* run (`touch /tmp/pwned`, `curl …`) leaves **no**
  filesystem or network artifact — assert the sentinel file is absent and the exec-log
  entry is synthetic.
- **Grade loop:** `improper_output_handling` fires and the flag is captured, with the
  `container_exec_log` a fabricated string.

**8. Should L13 remain deferred?** **Yes.** L13 already delivers its lesson contained and
gradable. If revisited, the **only** sanctioned form is a **string-only simulated exec
sink** (§3–4) as its own small, threat-modeled PR; a **real execution simulator stays out
of scope** absent an explicit, separately-approved infrastructure epic.

## Decision

- **Keep L13 as-is** (contained mock/structural). No Ollama realism now.
- If prioritized later, scope a **string-only simulated exec-sink** PR under this memo's
  guardrails (§3, §4, §7). **Never real execution.**
- A real execution simulator (real shell / container / file / network side effects) is a
  **separate infrastructure epic** requiring its own threat model and explicit approval —
  not a drive-by inside a lab PR.

## Cross-references
[02-lab-range.md](02-lab-range.md) · [13-platform-threat-model.md](13-platform-threat-model.md) · [04-evaluation-harness.md](04-evaluation-harness.md) · [11-safety-legal-ethics.md](11-safety-legal-ethics.md)
