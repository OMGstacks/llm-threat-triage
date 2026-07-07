#!/usr/bin/env python3
"""cli.py — project entrypoint wiring for osai-prep-studio.

Copied from the toolkit's example `cli.py` and filled in with this project's
own generator (`cognition_inventory_generator.py`), alongside the toolkit's
worked-example generator (kept registered so `--only env_var_index` still
works as a reference/demo). This file should stay short: import your
generator class(es), instantiate them (pointing at YOUR project's paths),
and hand the list to `framework.run_cli()`. All the actual logic (--check /
--write / --list / --only, diffing, the unregistered-file warning) lives in
framework.py, which you should NOT need to edit.
"""

import sys
from pathlib import Path

# Explicit, so a sibling project's cli.py can be invoked from any cwd (or a
# harness that runs it as `python3 path/to/cli.py` without the normal
# script-directory sys.path[0] behavior) and still resolve `framework` --
# without this, importing the one shared framework.py from a project other
# than the one physically holding this cli.py silently breaks.
sys.path.insert(0, str(Path(__file__).parent))

from cognition_inventory_generator import CognitionInventoryGenerator  # noqa: E402
from example_generator import EnvVarIndexGenerator  # noqa: E402
from framework import run_cli  # noqa: E402

TOOLKIT_ROOT = Path(__file__).parent
PROJECT_ROOT = TOOLKIT_ROOT.parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "codebase_index"

GENERATORS = [
    CognitionInventoryGenerator(source_root=TOOLKIT_ROOT.parent, output_dir=OUT_DIR),
    EnvVarIndexGenerator(source_root=PROJECT_ROOT, output_dir=OUT_DIR),
    # Add your own generators here, e.g.:
    # MyCustomIndexGenerator(source_root=PROJECT_ROOT, output_dir=OUT_DIR),
]

# NOTE: only `cognition_inventory`'s generated output is committed and
# gated in CI (`--only cognition_inventory`). `env_var_index` is left
# registered as a reference/demo (`--list`, `--only env_var_index` still
# work) but its generated-header bakes in an ABSOLUTE path derived from
# PROJECT_ROOT -- `--write`/`--check` on a different checkout location
# (e.g. a CI runner) will never byte-match a copy committed from this
# sandbox. Fixing that is a toolkit-level change (framework.py's
# `generated_header`/example_generator.py both do this), out of scope here.

if __name__ == "__main__":
    sys.exit(run_cli(GENERATORS, sys.argv[1:]))
