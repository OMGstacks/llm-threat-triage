"""Make ``osai_spine`` (and the co-located ``osai-narrate`` package) importable when
pytest runs from the spine/ directory."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# The shared narration renderer lives in a sibling package; add it so tests can import it.
_NARRATE = os.path.abspath(os.path.join(_HERE, "..", "packages", "osai-narrate"))
if os.path.isdir(_NARRATE):
    sys.path.insert(0, _NARRATE)
