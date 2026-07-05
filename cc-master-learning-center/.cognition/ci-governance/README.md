# ci-governance

A portable CI/CD gate-governance system: **one declarative file generates your
local test runner and your GitHub Actions workflow**, so the two can never
silently drift apart.

## The problem this replaces

The original design (extracted and redesigned from a production trading
system) had **three independently hand-edited, coupled surfaces** that had to
agree by convention:

1. A **local CI runner script** — one `run_check "<gate>" <command>` line per
   gate.
2. A **GitHub Actions workflow file** — one job block per gate, hand-keyed to
   (hopefully) the same name.
3. A **parity checker** — a Python dict mapping gate names to CI job names,
   used to verify local pytest invocations actually cover what CI covers.

A **dedicated deletion-guard script** diffed the gate-name *set* across all
three surfaces (current branch vs. a base ref) and failed if a gate silently
vanished from any one of them during a merge/rebase, with an allowlist for
intentional temporary removals.

This worked, but it was **reactive**: drift was *detected* after the fact by a
guard script, not made *structurally impossible*. It already caused a real
near-miss — two PRs both touching all three files, one nearly silently
dropping the other's gate on merge, caught only because the guard happened to
run before the bad merge landed.

## The fix: one source of truth, generated outward

```
gates.yml  --(gen_ci.py)-->  local CI runner section
                         \-->  GitHub Actions workflow job section
```

Each gate is declared **once**, in `gates.yml`. Its `name` is used as both the
local `run_check` label and the CI job key — there is no second name to drift
from the first, because there is no second name. `gen_ci.py` deterministically
regenerates both output sections from that single file. You do not hand-edit
the generated sections; you edit `gates.yml` and re-run the generator.

This reduces the four original pieces to:

| Old surface | New equivalent |
|---|---|
| Local runner script (hand-edited gate lines) | **Generated** by `gen_ci.py` into a marked region of your existing script |
| GitHub Actions workflow (hand-edited job blocks) | **Generated** by `gen_ci.py` into a marked region of your existing workflow |
| Parity checker (gate name -> job name dict) | **Eliminated for the common case** — a generated job's key IS the gate name, by construction. `check_gate_semantic_drift.py` covers only the residual case: gates whose `ci_command` legitimately differs from `command`, checking test-path coverage in that narrow set. |
| Deletion guard (3-way surface diff) | **Collapsed to a 1-way diff**: `check_gate_deletion.py` now only needs to watch `gates.yml` itself, since the two generated surfaces can no longer independently lose a gate — regeneration always covers every declared gate. |

The system is **not** claimed to be 100% generated. `extra_yaml` is an
intentional escape hatch for the rare CI-only need (a Postgres `services:`
block, a matrix strategy) that would otherwise force contorting the schema to
cover every possible GitHub Actions feature. Roughly 90% generated, with a
clean, auditable 10% escape hatch, beats 100% generated with an escape hatch
so awkward people bypass the generator entirely.

## Files

| File | Purpose |
|---|---|
| `gates.schema.json` | JSON Schema for `gates.yml`. Defines the gate entry shape. |
| `gates.example.yml` | Worked example covering all 5 gate patterns (plain pytest, non-pytest+sibling, local-only+requires, CI-diverging command, extra_yaml). |
| `gen_ci.py` | The codegen: `gates.yml` -> local runner section + CI workflow section. |
| `check_gate_semantic_drift.py` | Residual check: for gates with an explicit `ci_command` override, asserts local pytest coverage is a superset of CI's. |
| `check_gate_deletion.py` | Deletion guard: diffs `gates.yml`'s gate-name set against a base ref; enforces the allowlist. |
| `gate_deletion_allowlist.template.txt` | Empty allowlist template — copy to `gate_deletion_allowlist.txt` and fill in as needed. |
| `tests/test_gen_ci_self.py` | Self-test proving all of the above actually works (schema validation, codegen correctness, idempotency, real git-backed deletion detection). |

## Quickstart

```bash
pip install pyyaml jsonschema

# Validate + generate (first run bootstraps markers into your files)
python gen_ci.py --gates gates.yml \
  --local-ci-out scripts/local_ci.sh \
  --ci-yml-out .github/workflows/ci.yml \
  --write

# In CI, or before committing, prove nothing has hand-drifted:
python gen_ci.py --gates gates.yml \
  --local-ci-out scripts/local_ci.sh \
  --ci-yml-out .github/workflows/ci.yml \
  --check
```

`--check` regenerates in memory and diffs against the committed marked
region: exit 0 silently on match, exit 1 with a unified diff on any mismatch.
Wire this into your own CI as a "codegen is in sync" gate — ironically, it's
the one gate you still hand-write, once, and it never needs to change again
as you add/remove other gates.

### First-time bootstrap note

`gen_ci.py` does not create a runner script or workflow file from *nothing* —
it expects **some** existing scaffolding:

- **Local runner** (`local_ci.sh` or similar): needs a shebang and,
  conventionally, a `run_check` shell function defined above the marker
  region (the generated `run_check "<name>" <command>` lines call it). If the
  target file does not exist at all, an empty one with a shebang and the
  markers is created — you still need to add your own `run_check` function
  before the markers for the generated calls to do anything.
- **CI workflow** (`ci.yml`): needs a valid GitHub Actions document with a
  top-level `jobs:` key. If the target file does not exist at all, a minimal
  valid workflow (`name`/`on`/`jobs`) is created with the markers nested
  under `jobs:`.

If the target file **exists** but has no markers yet, `gen_ci.py` inserts the
marker pair on first run (at the end of the file for the local runner; as the
last entries under `jobs:` for the workflow) — everything else in the file is
left untouched.

## Marker-delimited regions: why hand-authored content survives

Both output files are written **only** between:

```
# === BEGIN GENERATED GATES (generated by gen_ci.py --write; do not hand-edit below) ===
...generated content...
# === END GENERATED GATES ===
```

Everything **outside** the markers — a `run_check` function definition,
`concurrency:` blocks, path filters, permissions blocks, checkout steps
outside the gate jobs, custom preamble comments — is preserved **byte for
byte** across every regeneration. This is proven by
`test_marker_region_preserves_surrounding_handauthored_content` in the test
suite: hand-authored preamble goes in, `gen_ci.py --write` runs, and the
preamble comes back out unchanged, with the generated section updated
alongside it.

## Worked walkthrough: add a new gate

1. Edit `gates.yml`, add an entry:

   ```yaml
     - name: lint-imports
       description: "Import-order lint"
       group: "lint"
       command: "python -m isort --check-only ."
   ```

2. Regenerate:

   ```bash
   python gen_ci.py --gates gates.yml \
     --local-ci-out scripts/local_ci.sh \
     --ci-yml-out .github/workflows/ci.yml \
     --write
   ```

3. Review the diff (`git diff`) — you'll see a new `run_check "lint-imports"`
   block in the local runner and a new `lint-imports:` job in the workflow,
   both derived from the one entry you just wrote. Commit all three files
   (`gates.yml` + the two regenerated outputs) together.

That's it — there is no second file to remember to update, because the
generator already updated it.

## Worked walkthrough: intentionally remove a gate

1. Delete the entry from `gates.yml`.

2. Add a line to `gate_deletion_allowlist.txt` (copy from the `.template.txt`
   if you don't have one yet):

   ```
   lint-imports | superseded by ruff, redundant with lint-ruff gate | expires=2026-09-01 | ref=#123
   ```

3. Regenerate:

   ```bash
   python gen_ci.py --gates gates.yml \
     --local-ci-out scripts/local_ci.sh \
     --ci-yml-out .github/workflows/ci.yml \
     --write
   ```

4. Commit `gates.yml`, the two regenerated outputs, and the allowlist change
   together. `check_gate_deletion.py` (run against your base branch in CI)
   will see `lint-imports` disappeared, find the allowlist entry, confirm
   it isn't expired, and print a `PASS` note instead of hard-failing.

5. **Before `2026-09-01`**, either finish removing every trace of
   `lint-imports` and delete the allowlist line (cleanest — the allowlist
   should not accumulate permanent entries), or renew the `expires=` date
   with a fresh justification if the removal genuinely needs more runway.
   After the expiry passes, the guard hard-fails again until you do one of
   these — an allowlist entry is a temporary permission slip, not a permanent
   exemption.

## Edge cases carried over, unchanged in spirit, from the original design

This redesign is a **strict improvement**, not a regression with fewer
features. Every edge case the original 3-surface system handled is still
handled here:

- **Per-gate allowlist with expiry** — `check_gate_deletion.py` requires an
  `expires=YYYY-MM-DD` for confidence a removal isn't permanently
  grandfathered in; an expired entry is a hard fail, forcing cleanup or
  renewal, exactly as before.
- **Base-ref-aware comparison for release/hotfix branches** — `--base` is
  fully configurable (defaults to `origin/main`, override for any branch
  topology); the deletion guard was never hardcoded to a single ref.
- **Fail-open `BASE_UNAVAILABLE` sentinel** — if the base ref can't be
  resolved locally (no fetch), the guard prints
  `GATE_DELETION_BASE_UNAVAILABLE` and exits 0 rather than either false
  hard-failing or silently passing without saying so. Real enforcement
  happens in CI, where the base ref is always fetched.
- **Environment-gated local-only checks** — the `requires: [tool]` field
  reproduces the "skip cleanly if a required local tool is absent" behavior
  (`command -v <tool> || skip`), and `allow_ci: false` reproduces "this check
  only makes sense on a developer machine, don't even try it in CI."
- **A structured (not free-text) sibling-test cross-reference** —
  `sibling_test_gate` replaces what was previously a hand-maintained
  exceptions dict mapping non-pytest lints to the test files that cover their
  own logic. It's now validated: `gen_ci.py` fails loudly if a
  `sibling_test_gate` name doesn't match a real gate, instead of silently
  tolerating a stale free-text reference.
- **A soft-warn, not hard-fail, for missing traceability metadata** — a
  missing `ref=#NNN` on an allowlist entry is a WARN, exactly as a missing
  reference was previously non-blocking; only a missing/expired allowlist
  *entry* is a hard fail.
- **Stale-allowlist detection** — an allowlist entry for a gate that is
  actually still present (not removed) prints a WARN so the allowlist doesn't
  quietly accumulate dead entries over time.

## What changed in the CI surface area vs. the old system

The **only** thing that got smaller here is *how many places you hand-edit
when a gate changes* (one, not three) and *how much bespoke parsing logic
existed to reconcile three hand-maintained formats* (a full dual-format
parser -> a targeted pytest-path regex over the small number of gates that
still legitimately diverge). Nothing about **enforcement strength** was
traded away to get there.

## Running the self-test

```bash
pip install pyyaml jsonschema pytest
python -m pytest tests/test_gen_ci_self.py -v
```

The self-test builds a temp `gates.yml`, runs `gen_ci.py --write` against
temp output files, asserts the generated content is correct, runs `--write`
a second (and third) time to prove byte-identical idempotency, runs `--check`
to prove it passes cleanly against its own output, and spins up a real
scratch git repository to prove `check_gate_deletion.py` genuinely detects a
real gate removal across two commits and correctly respects (or rejects) an
allowlist entry, including the expired-entry, stale-entry, and
base-unavailable cases.
