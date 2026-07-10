<!--
GENERATED FILE — DO NOT EDIT BY HAND
Generator: cognition_inventory
Inputs:
  - .cognition/memory/MEMORY.md
  - .cognition/memory/MEMORY.template.md
  - .cognition/friction/friction_log.jsonl
  - .cognition/friction/friction_log.example.jsonl
  - .cognition/ci-governance/gates.yml
  - .cognition/ci-governance/gates.example.yml
  - .cognition/codebase-index/cognition_inventory_generator.py
  - .cognition/codebase-index/example_generator.py
  - .cognition/active-work/claims_cli.py
Regenerate:
  python cli.py --write --only cognition_inventory
Check (CI gate):
  python cli.py --check --only cognition_inventory
-->

# Cognition OS Toolkit Inventory

5/5 subsystems instantiated (marker file present) vs. still template-only, for this project's `.cognition/` toolkit.

| Subsystem | Status | Marker |
|---|---|---|
| memory | INSTANTIATED | `memory/MEMORY.md` |
| friction | INSTANTIATED | `friction/friction_log.jsonl` |
| ci-governance | INSTANTIATED | `ci-governance/gates.yml` |
| codebase-index | INSTANTIATED | `codebase-index/cognition_inventory_generator.py` |
| active-work | INSTANTIATED | `active-work/claims_cli.py` |

A subsystem is INSTANTIATED when its marker file exists -- a real content file, not the template/example the toolkit ships with. See each subsystem's own README.md for what "instantiated" means in more depth.
