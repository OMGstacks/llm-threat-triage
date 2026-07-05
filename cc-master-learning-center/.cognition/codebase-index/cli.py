#!/usr/bin/env python3
"""cli.py — EXAMPLE entrypoint wiring.

COPY THIS FILE into your project and replace the example generator below with
your own. This file should stay short: import your generator class(es),
instantiate them (pointing at YOUR project's paths), and hand the list to
`framework.run_cli()`. All the actual logic (--check / --write / --list /
--only, diffing, the unregistered-file warning) lives in framework.py, which
you should NOT need to edit.
"""

import sys
from pathlib import Path

from example_generator import EnvVarIndexGenerator
from framework import run_cli

REPO_ROOT = Path(__file__).parent
OUT_DIR = REPO_ROOT / "docs" / "codebase_index"

GENERATORS = [
    EnvVarIndexGenerator(source_root=REPO_ROOT, output_dir=OUT_DIR),
    # Add your own generators here, e.g.:
    # MyCustomIndexGenerator(source_root=REPO_ROOT, output_dir=OUT_DIR),
]

if __name__ == "__main__":
    sys.exit(run_cli(GENERATORS, sys.argv[1:]))
